import json
from pathlib import Path

import pytest

from radlabel.config import Settings
from radlabel.llm import BudgetExceeded, FakeLLM, LLMClient, LLMResponse
from radlabel.llm.client import cost

MSG = [{"role": "user", "content": "hi"}]


def test_cache_makes_reruns_free(tmp_path: Path) -> None:
    llm = FakeLLM(lambda m: '{"ok": true}', tmp_path)
    a = llm.complete(MSG, purpose="t")
    b = llm.complete(MSG, purpose="t")
    assert (a.cached, b.cached, llm.calls) == (False, True, 1)
    assert b.json_obj() == {"ok": True}
    assert llm.complete(MSG, temperature=None).cached is False  # params are part of the key


def test_budget_stops_at_half_of_max(tmp_path: Path) -> None:
    s = Settings(_env_file=None, max_llm_usd=2.0)  # type: ignore[call-arg]
    (tmp_path / "ledger.jsonl").write_text(json.dumps({"cost_usd": 1.0}) + "\n")
    llm = LLMClient(s, tmp_path)
    with pytest.raises(BudgetExceeded):
        llm._call("gpt-4.1-mini", MSG, None, None, 0.0)


def test_unpriced_deployment_refused(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="no verified price"):
        LLMClient(Settings(_env_file=None), tmp_path)._call("gpt-9", MSG, None, None, 0.0)  # type: ignore[call-arg]


def test_cost_formula() -> None:
    assert cost("gpt-4.1-mini", 1_000_000, 0, 1_000_000) == pytest.approx(2.0)
    assert cost("gpt-4.1-mini", 1_000_000, 1_000_000, 0) == pytest.approx(0.1)


def test_offline_without_key_fails_clearly(tmp_path: Path) -> None:
    llm = LLMClient(Settings(_env_file=None, azure_openai_endpoint="https://x"), tmp_path)  # type: ignore[call-arg]
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        llm.complete(MSG)
    assert LLMResponse(text="", deployment="d", model="m").cost_usd == 0
