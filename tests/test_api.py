"""Website session API (SPEC §6.5, M10a): every endpoint, the frontend contract shapes, limits, the citation check,
the daily cap, and privacy (only aggregate cost-ledger rows written, no report or question text in logs). FakeLLM
and a fake encoder: no network, no model download."""

import builtins
import hashlib
import io
import json
import logging
import re
import zlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from test_extractor import answer

from radlabel.api import app as api_app
from radlabel.api import ask as ask_mod
from radlabel.api import sample
from radlabel.api import session as session_mod
from radlabel.config import get_settings
from radlabel.labels import LABELS
from radlabel.llm import FakeLLM

REPORT = ("INDICATION: zqcough for two weeks.\nFINDINGS: Small left pleural effusion. The heart size is normal.\n"
          "IMPRESSION: Small left pleural effusion.")
QUESTION = "zqwhat happened to the effusion?"
ASK_REPORT_SHA = "94138874cd5b19a81fc0a65bb450fc05b6dee982960ea269105744b09f9469a5"  # ask-report-v1, frozen
ASK_ALL_SHA = "386200d77723973b7ea581948c26c518b9e1d58a52e8911df651c058fe17489a"  # ask-all-v1, frozen


@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch: Any) -> None:
    def enc(texts: list[str], batch_size: int = 64) -> np.ndarray:
        m = np.zeros((len(texts), 256))
        for k, t in enumerate(texts):
            for w in re.findall(r"[a-z]+", t.lower()):
                m[k, zlib.crc32(w.encode()) % 256] += 1
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
    monkeypatch.setattr(session_mod, "search_encode", enc)


def responder(messages: list[dict[str, Any]]) -> Any:
    system, user = messages[0]["content"], messages[-1]["content"]
    if system.startswith("You label chest X-ray reports"):  # tagger: effusion present where a sentence states it
        ids = [m.group(1) for m in re.finditer(r"^([FI]\d+): (?!No )[^\n]*effusion", user, re.M)]
        return answer(Pleural_Effusion=("present", ids)) if ids else answer()
    if system.startswith("You answer questions"):  # ask: cite the first sentence given, plus a made-up one
        m = re.search(r"\[report (\d+), (\w+),", user)
        if "antibiotics" in user:
            return json.dumps({"answer": None, "refusal": "I can't give treatment advice.", "citations": []})
        cites = [{"report_no": int(m.group(1)), "sentence_id": m.group(2)}] if m else []
        return json.dumps({"answer": "It is stated.", "refusal": None,
                           "citations": cites + [{"report_no": 99, "sentence_id": "F9"}]})
    return "{}"  # verifier agent: no tool call -> its labels end unverified


def client(tmp_path: Path, cap: float | None = None, **env: str) -> tuple[TestClient, FakeLLM]:
    llm = FakeLLM(responder, tmp_path, memory_cache=True, daily_cap_usd=cap)
    return TestClient(api_app.create_app(llm)), llm


def session(c: TestClient) -> str:
    r = c.post("/api/session")
    assert r.status_code == 200
    return str(r.json()["session_id"])


def test_session_lifecycle_and_expiry(tmp_path: Path) -> None:
    c, _ = client(tmp_path)
    sid = session(c)
    assert c.get(f"/api/session/{sid}/timeline").json() == {"timeline": []}
    assert c.delete(f"/api/session/{sid}").status_code == 204
    r = c.get(f"/api/session/{sid}/timeline")
    assert r.status_code == 404 and "expired" in r.json()["detail"]
    store = session_mod.SessionStore(ttl_s=-1)  # every session is past its idle limit
    s = store.create()
    store.sweep()
    assert store.get(s.id) is None  # idle expiry


def test_upload_text_matches_the_frontend_contract(tmp_path: Path) -> None:
    c, _ = client(tmp_path)
    sid = session(c)
    r = c.post(f"/api/session/{sid}/reports", data={"text": REPORT})
    assert r.status_code == 200
    rep = r.json()["reports"][0]
    assert set(rep) == {"report_no", "filename", "sections", "sections_identified", "labels", "rules_only"}
    assert rep["report_no"] == 1 and rep["sections_identified"] and rep["rules_only"] is False
    assert set(rep["sections"]) == {"indication", "comparison", "findings", "impression"}
    assert rep["sections"]["comparison"] == [] and rep["sections"]["indication"][0]["id"] == "N1"
    assert [x["label"] for x in rep["labels"]] == list(LABELS)
    eff = next(x for x in rep["labels"] if x["label"] == "Pleural Effusion")
    assert set(eff) == {"label", "status", "verification", "corroboration", "evidence", "reason"}
    assert eff["status"] == "present" and eff["corroboration"] == "both"
    assert eff["evidence"] == [{"sentence_id": "F1", "text": "Small left pleural effusion."},
                               {"sentence_id": "I1", "text": "Small left pleural effusion."}]


def _pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            b"/Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % x for x in offs)
    return out + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)


def test_upload_files_txt_and_pdf_and_order(tmp_path: Path) -> None:
    c, _ = client(tmp_path)
    sid = session(c)
    files = [("files", ("a.txt", REPORT.encode(), "text/plain")),
             ("files", ("b.pdf", _pdf("FINDINGS: Small right pleural effusion."), "application/pdf"))]
    reps = c.post(f"/api/session/{sid}/reports", data={"text": REPORT}, files=files).json()["reports"]
    assert [(r["report_no"], r["filename"]) for r in reps] == [(1, "Pasted report"), (2, "a.txt"), (3, "b.pdf")]
    assert reps[2]["sections"]["findings"][0]["text"] == "Small right pleural effusion."
    bad = c.post(f"/api/session/{sid}/reports", files=[("files", ("x.docx", b"x", "application/octet-stream"))])
    assert bad.status_code == 400 and ".txt and .pdf" in bad.json()["detail"]


def test_limits_and_errors_never_echo_input(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("WEB_MAX_REPORTS", "2")
    monkeypatch.setenv("WEB_MAX_TEXT_CHARS", "200")
    get_settings.cache_clear()
    try:
        c, _ = client(tmp_path)
        sid = session(c)
        assert c.post(f"/api/session/{sid}/reports").status_code == 400  # nothing given
        long = c.post(f"/api/session/{sid}/reports", data={"text": "x" * 201})
        assert long.status_code == 413 and "x" * 20 not in long.text
        assert c.post(f"/api/session/{sid}/reports", data={"sample": "true"}).status_code == 400  # 5 > 2
        r = c.post(f"/api/session/{sid}/ask", json={"scope": "all", "question": "q" * 501})
        assert r.status_code == 422 and "q" * 20 not in r.text and set(r.json()) == {"detail"}
    finally:
        get_settings.cache_clear()


def test_sample_loads_without_llm_calls(tmp_path: Path) -> None:
    c, llm = client(tmp_path)
    sid = session(c)
    reps = c.post(f"/api/session/{sid}/reports", data={"sample": "true"}).json()["reports"]
    assert [r["filename"] for r in reps] == list(sample.FILES)
    if sample.PRECOMPUTED.exists():
        assert llm.calls == 0  # precomputed: loading the sample costs nothing
    rows = c.get(f"/api/session/{sid}/timeline").json()["timeline"]
    assert all(set(r) == {"label", "statuses"} and set(r["statuses"]) == {"1", "2", "3", "4", "5"} for r in rows)
    assert "No Finding" not in {r["label"] for r in rows}


def test_ask_report_and_all_keep_only_given_citations(tmp_path: Path) -> None:
    c, _ = client(tmp_path)
    sid = session(c)
    c.post(f"/api/session/{sid}/reports", data={"text": REPORT})
    one = c.post(f"/api/session/{sid}/ask", json={"scope": "report", "report_no": 1, "question": "effusion?"}).json()
    assert set(one) == {"answer", "refusal", "citations", "retrieved_sentences", "retrieved_reports"}
    assert one["answer"] and one["citations"] == [{"report_no": 1, "sentence_id": "N1"}]  # made-up citation dropped
    assert one["retrieved_reports"] == 1 and one["retrieved_sentences"] == 4
    allr = c.post(f"/api/session/{sid}/ask", json={"scope": "all", "question": "pleural effusion size"}).json()
    assert allr["answer"] and len(allr["citations"]) == 1 and allr["retrieved_reports"] == 1
    no = c.post(f"/api/session/{sid}/ask", json={"scope": "report", "report_no": 1,
                                                 "question": "Should the patient start antibiotics?"}).json()
    assert no["answer"] is None and "treatment" in no["refusal"]
    bad = c.post(f"/api/session/{sid}/ask", json={"scope": "report", "report_no": 7, "question": "x"})
    assert bad.status_code == 400


def test_answer_without_valid_citation_becomes_not_stated() -> None:
    e = [session_mod.Entry(1, "F1", "findings", "x")]
    assert ask_mod.check(json.dumps({"answer": "yes", "refusal": None,
                                     "citations": [{"report_no": 2, "sentence_id": "F1"}]}), e) == \
        (None, ask_mod.NOT_STATED, [])
    assert ask_mod.check("not json", e) == (None, ask_mod.NOT_STATED, [])


def test_daily_cap_gives_rules_only_labels_and_unavailable_answers(tmp_path: Path) -> None:
    c, llm = client(tmp_path, cap=0.0)
    sid = session(c)
    rep = c.post(f"/api/session/{sid}/reports", data={"text": REPORT}).json()["reports"][0]
    assert rep["rules_only"] is True and llm.calls == 0
    assert {x["verification"] for x in rep["labels"]} == {"unverified"}
    r = c.post(f"/api/session/{sid}/ask", json={"scope": "all", "question": "effusion?"}).json()
    assert r["answer"] is None and "temporarily unavailable" in r["refusal"]


def test_daily_cap_reads_the_ledger_so_it_survives_restarts(tmp_path: Path) -> None:
    from datetime import UTC, datetime
    row = {"ts": datetime.now(UTC).isoformat(timespec="seconds"), "source": "web", "endpoint": "ask",
           "model": "fake", "input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1, "cost_usd": 0.6}
    rows = [row, {**row, "source": None}]  # the second (an owner run) does not count toward the website cap
    (tmp_path / "ledger.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    assert FakeLLM(responder, tmp_path, memory_cache=True, daily_cap_usd=1.0).spent_today == pytest.approx(0.6)
    c, llm = client(tmp_path, cap=0.5)  # a restarted server: today's web spend 0.6 >= cap 0.5
    assert llm.daily_cap_reached() and c.get("/ready").json()["daily_cap_reached"] is True


def test_rate_limit_per_ip(tmp_path: Path, monkeypatch: Any) -> None:
    monkeypatch.setenv("API_RATE_LIMIT", "3/minute")
    get_settings.cache_clear()
    try:
        c, _ = client(tmp_path)
        codes = [c.post("/api/session").status_code for _ in range(4)]
        assert codes == [200, 200, 200, 429]
        assert c.get("/health").status_code == 200  # only /api is limited
    finally:
        get_settings.cache_clear()


def test_health_and_ready(tmp_path: Path) -> None:
    c, _ = client(tmp_path)
    assert c.get("/health").json() == {"status": "ok"}
    assert set(c.get("/ready").json()) == {"status", "search_model", "llm_configured", "daily_cap_reached", "sessions"}


def test_uploads_and_questions_are_written_nowhere(tmp_path: Path, monkeypatch: Any,
                                                   caplog: pytest.LogCaptureFixture) -> None:
    c, _ = client(tmp_path)
    writes: list[str] = []
    real = io.open

    def spy(file: Any, mode: str = "r", *a: Any, **k: Any) -> Any:
        if any(m in mode for m in "wax+"):
            writes.append(str(file))
        return real(file, mode, *a, **k)
    monkeypatch.setattr(io, "open", spy)
    monkeypatch.setattr(builtins, "open", spy)
    caplog.set_level(logging.DEBUG)
    sid = session(c)
    c.post(f"/api/session/{sid}/reports", data={"text": REPORT})
    c.post(f"/api/session/{sid}/ask", json={"scope": "all", "question": QUESTION})
    c.post(f"/api/session/{sid}/ask", json={"scope": "report", "report_no": 1, "question": QUESTION})
    ledger = tmp_path / "ledger.jsonl"
    assert {Path(w) for w in writes} == {ledger}  # only the cost ledger is written (no cache, no upload)
    assert [p for p in tmp_path.rglob("*")] == [ledger]
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    assert rows and {r["endpoint"] for r in rows} == {"reports", "ask"}
    for r in rows:  # aggregate entries only: never report or question text
        assert set(r) == {"ts", "source", "endpoint", "model", "input_tokens", "cached_input_tokens",
                          "output_tokens", "cost_usd"}
    text = ledger.read_text(encoding="utf-8")
    assert "zq" not in text and "effusion" not in text
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "request" in logged and "zqcough" not in logged and "zqwhat" not in logged and "effusion" not in logged


def test_api_imports_no_eval_or_ground_truth() -> None:
    import subprocess
    import sys

    code = "import sys, json; import radlabel.api.app; print(json.dumps(sorted(sys.modules)))"
    mods = json.loads(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                                     cwd=Path(__file__).resolve().parents[1]).stdout)
    assert not [m for m in mods if m.split(".")[0] in ("eval", "data_prep", "training")]


def test_ask_prompts_frozen() -> None:
    prompts = ((ask_mod.ASK_REPORT_VERSION, ask_mod.REPORT_SYSTEM), (ask_mod.ASK_ALL_VERSION, ask_mod.ALL_SYSTEM))
    h = {v: hashlib.sha256((s + json.dumps(ask_mod.SCHEMA, sort_keys=True)).encode()).hexdigest() for v, s in prompts}
    pinned = {"ask-report-v1": ASK_REPORT_SHA, "ask-all-v1": ASK_ALL_SHA}
    if "PIN" in pinned.values():
        pytest.skip(f"ask prompts not pinned yet: {h}")
    assert h == pinned, "ask prompt changed: needs owner OK and a new version"
