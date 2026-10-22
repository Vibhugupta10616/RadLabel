"""Website session API (SPEC §6.5, M10a). Contract: `web/README.md` and `web/src/contract.ts` on branch
m9c-frontend.

- Everything in process memory: uploads, labels, the session index and the LLM cache (radlabel.llm with
  memory_cache=True). No report or question text is written to disk, logs, the evaluation cache or the IU index;
  the only disk write is one aggregate cost-ledger row per fresh LLM call (ts, endpoint, model, tokens, cost).
- Labels only through run_pipeline (the evaluated v2 configuration).
- Limits: WEB_MAX_REPORTS per session, WEB_MAX_TEXT_CHARS per report, WEB_MAX_FILE_BYTES per file, questions of at
  most 500 characters, API_RATE_LIMIT per client IP, WEB_DAILY_CAP_USD of LLM spend per day (then rules-only labels
  and "temporarily unavailable" answers) on top of the global stop.
- Errors are {"detail": "..."} in plain language and never echo the request.

Run: uvicorn radlabel.api.app:app --port 8000
"""

from __future__ import annotations

import io
import json
import logging
import threading
import time
import uuid
from collections import deque
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from radlabel.api import sample
from radlabel.api.ask import AskResult, ask_all, ask_report
from radlabel.api.session import ReportOut, Session, SessionStore, to_report
from radlabel.config import get_settings
from radlabel.embeddings import search_model_name
from radlabel.labels import LABELS
from radlabel.llm import LLMClient
from radlabel.pipeline import run_pipeline

log = logging.getLogger("radlabel.api")
MAX_QUESTION_CHARS = 500
PIPELINE_WORKERS = 4


class AskIn(BaseModel):
    scope: Literal["report", "all"]
    report_no: int | None = None
    question: str = Field(min_length=1, max_length=MAX_QUESTION_CHARS)
    report_nos: list[int] | None = None  # optional filters for scope "all" (additive to the contract)
    labels: list[str] | None = None


class RateLimiter:
    """Sliding window per client IP, in memory ("30/minute")."""

    def __init__(self, spec: str) -> None:
        n, per = spec.split("/")
        self.n, self.window = int(n), {"second": 1, "minute": 60, "hour": 3600}[per.strip()]
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            while q and now - q[0] > self.window:
                q.popleft()
            if len(q) >= self.n:
                return False
            q.append(now)
            return True


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "unknown")


def extract_text(name: str, data: bytes) -> str:
    """Plain text of a .txt or .pdf upload (pypdf text layer; no OCR)."""
    suffix = Path(name).suffix.lower()
    if suffix == ".txt":
        return data.decode("utf-8", errors="replace")
    if suffix == ".pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            return "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
        except (PdfReadError, ValueError) as e:
            raise HTTPException(400, f"{name} could not be read as a PDF.") from e
    raise HTTPException(400, f"{name}: only .txt and .pdf files are supported.")


def create_app(llm: LLMClient | None = None) -> FastAPI:
    s = get_settings()
    web_llm = llm or LLMClient(memory_cache=True, daily_cap_usd=s.web_daily_cap_usd)
    store = SessionStore(ttl_s=s.web_session_ttl_minutes * 60)
    limiter = RateLimiter(s.api_rate_limit)
    app = FastAPI(title="RadLabel API", docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in s.web_cors_origins.split(",") if o.strip()],
                       allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

    @app.middleware("http")
    async def frame(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        rid, t0 = uuid.uuid4().hex[:12], time.monotonic()
        if request.url.path.startswith("/api/") and not limiter.allow(_client_ip(request)):
            response: Response = JSONResponse({"detail": "Too many requests. Please wait a minute and try again."},
                                              status_code=429)
        else:
            response = await call_next(request)
        route = request.scope.get("route")
        log.info(json.dumps({"event": "request", "request_id": rid, "method": request.method,
                             "route": getattr(route, "path", "unmatched"), "status": response.status_code,
                             "ms": round(1000 * (time.monotonic() - t0))}))  # no report or question text
        response.headers["X-Request-ID"] = rid
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(x) for x in e.get("loc", ())[1:]) or "body" for e in exc.errors()})
        return JSONResponse({"detail": f"Invalid request ({', '.join(fields)})."}, status_code=422)

    @app.exception_handler(Exception)
    async def failed(request: Request, exc: Exception) -> JSONResponse:
        log.error(json.dumps({"event": "error", "type": type(exc).__name__}))  # the type only, never the message
        return JSONResponse({"detail": "Something went wrong on our side. Please try again."}, status_code=500)

    def session_or_404(sid: str) -> Session:
        sess = store.get(sid)
        if sess is None:
            raise HTTPException(404, "This session has expired. Please upload the reports again.")
        return sess

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        key = s.azure_openai_api_key.get_secret_value() or s.openai_api_key.get_secret_value()
        return {"status": "ready", "search_model": search_model_name(), "llm_configured": bool(key),
                "daily_cap_reached": web_llm.daily_cap_reached(), "sessions": len(store)}

    @app.post("/api/session")
    def new_session() -> dict[str, str]:
        return {"session_id": store.create().id}

    @app.delete("/api/session/{sid}", status_code=204)
    def delete_session(sid: str) -> Response:
        if not store.delete(sid):
            raise HTTPException(404, "This session does not exist.")
        return Response(status_code=204)

    @app.post("/api/session/{sid}/reports")
    async def upload(sid: str, text: Annotated[str | None, Form()] = None,
                     files: Annotated[list[UploadFile] | None, File()] = None,
                     sample_: Annotated[bool, Form(alias="sample")] = False) -> dict[str, list[ReportOut]]:
        sess = session_or_404(sid)
        items: list[tuple[str, str]] = []
        if not sample_:
            if text and text.strip():
                items.append(("Pasted report", text))
            for f in files or []:
                data = await f.read(s.web_max_file_bytes + 1)
                if len(data) > s.web_max_file_bytes:
                    raise HTTPException(413, f"{f.filename} is larger than {s.web_max_file_bytes // 1_000_000} MB.")
                body = extract_text(f.filename or "file", data)
                if not body.strip():
                    raise HTTPException(400, f"No text found in {f.filename} (scanned PDFs are not supported).")
                items.append((f.filename or "file", body))
            if not items:
                raise HTTPException(400, "Paste a report, choose .txt or .pdf files, or load the sample.")
        n_new = len(sample.FILES) if sample_ else len(items)
        if len(sess.reports) + n_new > s.web_max_reports:
            raise HTTPException(400, f"A session holds at most {s.web_max_reports} reports.")
        for name, body in items:
            if len(body) > s.web_max_text_chars:
                raise HTTPException(413, f"{name} is longer than {s.web_max_text_chars:,} characters.")
        start = len(sess.reports) + 1
        if sample_:
            results = sample.results(web_llm)
            names = list(sample.FILES)
        else:
            with ThreadPoolExecutor(PIPELINE_WORKERS) as ex:
                results = list(ex.map(lambda nb: run_pipeline(nb[1][1], web_llm, str(start + nb[0])),
                                      enumerate(items)))
            names = [n for n, _ in items]
        for k, (name, r) in enumerate(zip(names, results, strict=True)):
            sess.add(to_report(start + k, name, r))
        return {"reports": sorted(sess.reports, key=lambda r: r.report_no)}

    @app.post("/api/session/{sid}/ask")
    def ask(sid: str, body: AskIn) -> AskResult:
        sess = session_or_404(sid)
        if body.scope == "report":
            if body.report_no is None or sess.report(body.report_no) is None:
                raise HTTPException(400, "Choose one of the uploaded reports for this question.")
            return ask_report(web_llm, sess, body.report_no, body.question)
        if not sess.reports:
            raise HTTPException(400, "Upload reports before asking about them.")
        bad = [x for x in body.labels or [] if x not in LABELS]
        if bad:
            raise HTTPException(400, "Unknown label in the filter.")
        return ask_all(web_llm, sess, body.question, body.report_nos, body.labels)

    @app.get("/api/session/{sid}/timeline")
    def timeline(sid: str) -> dict[str, Any]:
        return {"timeline": session_or_404(sid).timeline()}

    return app


app = create_app()
