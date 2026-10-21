"""LLM client: cache -> budget check -> call (429 back-off) -> cost ledger.

- Cache key = (deployment, pinned version, messages, schema, params); hits cost $0, so reruns are free
  and CI needs no API calls. Cache files hold report text: `LLM_CACHE_DIR` is git-ignored.
- Ledger (`<cache>/ledger.jsonl`): one line per fresh call with tokens, cost and the `model` field the
  API returned. A changed `model` for a deployment logs a warning (silent upgrades).
- Budget: fresh calls stop at 50% of MAX_LLM_USD (SPEC §7.1); the owner raises it explicitly.
- 429: wait (Retry-After if given, else exponential) and retry; never surfaces as a failed label.
- Deployments without a verified price are refused (SPEC §7.1).
"""

from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from radlabel.config import Settings, get_settings

log = logging.getLogger(__name__)

Role = Literal["tier1", "fallback", "repair", "cheap"]

# USD per 1M tokens (input, cached input, output), Azure Global Standard, from the Azure Retail
# Prices API (prices.azure.com, eastus2) on 2026-10-20.
PRICES: dict[str, tuple[float, float, float]] = {
    "gpt-4.1-mini": (0.40, 0.10, 1.60),
    "gpt-5-mini": (0.25, 0.025, 2.00),
    "gpt-5.4-mini": (0.75, 0.075, 4.50),
    "gpt-5.4-nano": (0.20, 0.02, 1.25),
}
BUDGET_FRACTION = 0.5  # fresh calls stop at 50% of MAX_LLM_USD; the owner raises it explicitly
MAX_RATE_LIMIT_WAIT_S = 3600
MAX_CONNECTION_RETRIES = 8  # ~6 min of back-off before the caller sees the error


class BudgetExceeded(RuntimeError):
    pass


class CacheMiss(RuntimeError):
    """Raised in cache_only mode instead of making a fresh (paid) call."""


class LLMResponse(BaseModel):
    text: str
    deployment: str
    model: str  # as returned by the API
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cached: bool = False
    filtered: bool = False  # Azure content filter refused the prompt (HTTP 400 content_filter); text is ""
    tool_calls: list[dict[str, str]] = []  # native tool calls: {"id", "name", "arguments" (JSON string)}

    def json_obj(self) -> Any:
        return json.loads(self.text)


def deployment_for(role: Role, s: Settings) -> tuple[str, str]:
    return {
        "tier1": (s.azure_openai_deployment, s.azure_openai_deployment_version),
        "fallback": (s.azure_openai_fallback_deployment, s.azure_openai_fallback_deployment_version),
        "repair": (s.azure_openai_repair_deployment, s.azure_openai_repair_deployment_version),
        "cheap": (s.azure_openai_cheap_deployment, s.azure_openai_cheap_deployment_version),
    }[role]


def cost(deployment: str, inp: int, cached: int, out: int) -> float:
    p_in, p_cached, p_out = PRICES[deployment]
    return ((inp - cached) * p_in + cached * p_cached + out * p_out) / 1e6


def spent_usd(cache_dir: Path) -> float:
    ledger = cache_dir / "ledger.jsonl"
    if not ledger.exists():
        return 0.0
    return sum(json.loads(line)["cost_usd"] for line in ledger.open(encoding="utf-8"))


class LLMClient:
    def __init__(self, settings: Settings | None = None, cache_dir: Path | None = None,
                 cache_only: bool = False) -> None:
        self.cache_only = cache_only
        self.s = settings or get_settings()
        self.cache_dir = Path(cache_dir or self.s.llm_cache_dir)
        self._sdk: Any = None
        self._models: dict[str, str] = {}
        self._lock = threading.Lock()  # thread-safe ledger and running spend (callers may use a thread pool)
        self._spent = spent_usd(self.cache_dir)

    @property
    def spent(self) -> float:
        return self._spent

    # ---- public
    def complete(
        self,
        messages: list[dict[str, Any]],
        role: Role = "tier1",
        *,
        deployment: str | None = None,
        json_schema: dict[str, Any] | None = None,
        max_tokens: int | None = None,
        temperature: float | None = 0.0,
        reasoning_effort: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        purpose: str = "",
    ) -> LLMResponse:
        dep, version = deployment_for(role, self.s)
        if deployment:  # e.g. the Tier 1 pilot; version unknown -> recorded from the response
            dep, version = deployment, ""
        params: dict[str, Any] = {"max_tokens": max_tokens, "temperature": temperature, "json_schema": json_schema}
        if reasoning_effort is not None:  # only in the key when used, so earlier cache entries stay valid
            params["reasoning_effort"] = reasoning_effort
        if tools is not None:  # same rule: only in the key when used
            params["tools"] = tools
        key = hashlib.sha256(
            json.dumps([dep, version, messages, params], sort_keys=True).encode()
        ).hexdigest()
        path = self.cache_dir / dep / f"{key}.json"
        if path.exists():
            return LLMResponse(**json.loads(path.read_text(encoding="utf-8")), cached=True)
        if self.cache_only:
            raise CacheMiss(f"{dep}: no cached response for this request (cache_only mode)")

        resp = self._call(dep, messages, json_schema, max_tokens, temperature, reasoning_effort, tools)
        self._ledger(resp, purpose)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(resp.model_dump_json(exclude={"cached"}), encoding="utf-8")
        return resp

    # ---- internals
    def _call(self, dep: str, messages: list[dict[str, Any]], json_schema: dict[str, Any] | None,
              max_tokens: int | None, temperature: float | None, reasoning_effort: str | None = None,
              tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        if dep not in PRICES:
            raise RuntimeError(f"no verified price for deployment {dep!r}; add it to PRICES first")
        budget = self.s.max_llm_usd * BUDGET_FRACTION
        if self._spent >= budget:
            raise BudgetExceeded(f"LLM spend reached ${budget:.2f} (50% of MAX_LLM_USD): owner approval needed")
        kw: dict[str, Any] = {"model": dep, "messages": messages}
        if max_tokens is not None:
            kw["max_completion_tokens"] = max_tokens
        if temperature is not None:
            kw["temperature"] = temperature
        if reasoning_effort is not None:
            kw["reasoning_effort"] = reasoning_effort
        if tools is not None:
            kw["tools"] = tools
        if json_schema is not None:
            kw["response_format"] = {"type": "json_schema",
                                     "json_schema": {"name": "output", "schema": json_schema, "strict": True}}
        import openai

        try:
            r = self._with_backoff(lambda: self.sdk.chat.completions.create(**kw))
        except openai.BadRequestError as e:
            if getattr(e, "code", None) != "content_filter":
                raise
            # deterministic refusal for this prompt: returned (and cached) as a filtered response, not a crash
            log.warning("content filter refused a %s request", dep)
            return LLMResponse(text="", deployment=dep, model="content_filter", filtered=True)
        u = r.usage
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0
        msg = r.choices[0].message
        return LLMResponse(
            text=msg.content or "", deployment=dep, model=r.model,
            tool_calls=[{"id": t.id, "name": t.function.name, "arguments": t.function.arguments}
                        for t in (msg.tool_calls or [])],
            input_tokens=u.prompt_tokens, cached_input_tokens=cached, output_tokens=u.completion_tokens,
            cost_usd=cost(dep, u.prompt_tokens, cached, u.completion_tokens),
        )

    def _with_backoff(self, fn: Callable[[], Any]) -> Any:
        import openai

        waited, attempt, errors = 0.0, 0, 0
        while True:
            try:
                return fn()
            except openai.RateLimitError as e:  # 429: wait, never fail the report
                ra = e.response.headers.get("retry-after") if e.response is not None else None
                delay = float(ra) if ra else min(60.0, 2.0**attempt) + random.random()
                attempt += 1
                waited += delay
                if waited > MAX_RATE_LIMIT_WAIT_S:
                    raise
                log.warning("429 from Azure, waiting %.1fs", delay)
                time.sleep(delay)
            except (openai.APIConnectionError, openai.InternalServerError):
                errors += 1
                if errors > MAX_CONNECTION_RETRIES:
                    raise
                log.warning("connection/5xx error, retry %d", errors)
                time.sleep(min(60.0, 2.0**errors) + random.random())

    def _ledger(self, r: LLMResponse, purpose: str) -> None:
        prev = r.model if r.filtered else self._models.setdefault(r.deployment, r.model)
        if prev != r.model:
            log.warning("deployment %s returned model %s (was %s): silent upgrade?", r.deployment, r.model, prev)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        row = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "purpose": purpose,
               **r.model_dump(exclude={"text", "cached", "tool_calls"})}
        with self._lock:
            self._spent += r.cost_usd
            with (self.cache_dir / "ledger.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(row) + "\n")

    @property
    def sdk(self) -> Any:
        if self._sdk is None:
            self.s.require_llm()
            import openai

            key = self.s.azure_openai_api_key.get_secret_value()
            if self.s.llm_provider == "openai":
                self._sdk = openai.OpenAI(api_key=self.s.openai_api_key.get_secret_value(), max_retries=0)
            elif self.s.azure_openai_api_version:
                self._sdk = openai.AzureOpenAI(azure_endpoint=self.s.azure_openai_endpoint, api_key=key,
                                               api_version=self.s.azure_openai_api_version, max_retries=0)
            else:  # Azure GA v1 API: no api-version parameter
                base = self.s.azure_openai_endpoint.rstrip("/")
                base = base if base.endswith("/openai/v1") else base + "/openai/v1"
                self._sdk = openai.OpenAI(base_url=base + "/", api_key=key, max_retries=0)
        return self._sdk


class FakeLLM(LLMClient):
    """Deterministic stand-in for tests/offline builds: `responder(messages) -> text`, or a list of tool calls
    ({"name", "arguments"}). No cost, no network."""

    def __init__(self, responder: Callable[[list[dict[str, Any]]], str | list[dict[str, str]]], cache_dir: Path,
                 settings: Settings | None = None) -> None:
        super().__init__(settings or Settings(_env_file=None), cache_dir)  # type: ignore[call-arg]
        self.responder = responder
        self.calls = 0

    def _call(self, dep: str, messages: list[dict[str, Any]], json_schema: dict[str, Any] | None,
              max_tokens: int | None, temperature: float | None, reasoning_effort: str | None = None,
              tools: list[dict[str, Any]] | None = None) -> LLMResponse:
        self.calls += 1
        out = self.responder(messages)
        if isinstance(out, list):
            calls = [{"id": f"call_{self.calls}_{i}", **c} for i, c in enumerate(out)]
            return LLMResponse(text="", deployment=dep, model="fake", tool_calls=calls)
        return LLMResponse(text=out, deployment=dep, model="fake")
