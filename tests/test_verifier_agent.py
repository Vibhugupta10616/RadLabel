"""Verifier agent (README §6.2, M7): every tool, the caps, the evidence string check, the label merge, the freeze."""

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from test_free_checks import tagged
from test_repair_agent import call, script

from radlabel.labelling import verifier_agent as va
from radlabel.labelling.free_checks import escalations
from radlabel.llm import FakeLLM
from radlabel.preprocess.sentences import report_sentences

FROZEN_SHA256 = "614d6b64037421e18bab602c68ea6b02ef8e49f22a9422d7012f0f3e87216fcc"  # verifier-v2, frozen 2026-10-22


@pytest.fixture(autouse=True)
def fake_encoder(monkeypatch: Any) -> None:
    """Bag-of-words stand-in for the sentence-embedding model (no download in tests)."""
    def enc(texts: list[str]) -> np.ndarray:
        vocab = sorted({w for t in texts for w in t.lower().split()})
        m = np.array([[t.lower().split().count(w) for w in vocab] for t in texts], float)
        return m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
    monkeypatch.setattr(va, "encode", enc)


SENTS = report_sentences("Heart size is normal. Small left pleural effusion. [REDACTED] in the right lung.",
                         "Effusion.")


def test_tools() -> None:
    t = va.tool_impls(SENTS, {"Pleural Effusion": "not_mentioned"})
    assert {m["sentence_id"] for m in t["find_by_alias"]("Pleural Effusion")["mentions"]} == {"F2", "I1"}
    assert len(t["find_by_meaning"]("Pleural Effusion")["sentences"]) == min(va.MEANING_TOP_K, len(SENTS))
    assert t["check_negation"]("F1")["mentions"][0]["negated"] and "error" in t["check_negation"]("F9")
    assert t["compare_sections"]("Pleural Effusion")["section_rule"] is not None
    assert t["check_redaction"]("F3")["contains_redacted"] and not t["check_redaction"]("F1")["contains_redacted"]
    assert "enlarged heart" in t["get_label_definition"]("Cardiomegaly")["definition"]
    assert t["normal_check"]()["covered"]["heart"] == ["F1"]


def test_evidence_is_string_checked() -> None:
    ev = [va.Evidence(sentence_id="F2", quote="small LEFT pleural  effusion"),
          va.Evidence(sentence_id="F2", quote="large effusion"), va.Evidence(sentence_id="F9", quote="x")]
    assert va.valid_evidence(ev, SENTS) == ["F2"]


def run(responder: Any, tmp_path: Path, findings: str = "Small left pleural effusion.", impression: str = "",
        **over: tuple[str, list[str]]) -> tuple[va.AgentResult, list[va.FinalLabel]]:
    v, s = tagged(findings, impression, **over)
    esc = escalations(v, s)
    r = va.run_agent(FakeLLM(responder, tmp_path), "1", s, v, esc)
    return r, va.final_labels(v, s, esc, r)


def by(final: list[va.FinalLabel]) -> dict[str, va.FinalLabel]:
    return {x.label: x for x in final}


def test_suggested_when_the_agent_finds_a_missed_finding(tmp_path: Path) -> None:
    sub = call("submit", labels=[{"label": "Pleural Effusion", "status": "present", "reason": "stated",
                                  "evidence": [{"sentence_id": "F1", "quote": "pleural effusion"}]}])
    r, f = run(script([call("find_by_alias", label="Pleural Effusion")], [sub]), tmp_path)
    x = by(f)["Pleural Effusion"]
    assert r.stop == "submitted" and r.tool_calls == 2
    assert (x.status, x.verification, x.evidence) == ("present", "suggested", ["F1"])
    assert by(f)["No Finding"].status == "not_mentioned"
    assert by(f)["Cardiomegaly"].verification == "verified_rules"  # not escalated


def test_verified_corrected_and_unverified(tmp_path: Path) -> None:
    ev = [{"sentence_id": "F1", "quote": "No pleural effusion"}]
    sub = call("submit", labels=[{"label": "Pleural Effusion", "status": "present", "reason": "x", "evidence": ev}])
    _, f = run(script([sub]), tmp_path, "No pleural effusion.", Pleural_Effusion=("present", ["F1"]))
    assert by(f)["Pleural Effusion"].verification == "verified"
    sub = call("submit", labels=[{"label": "Pleural Effusion", "status": "absent", "reason": "x", "evidence": ev}])
    _, f = run(script([sub]), tmp_path / "b", "No pleural effusion.", Pleural_Effusion=("present", ["F1"]))
    assert (by(f)["Pleural Effusion"].status, by(f)["Pleural Effusion"].verification) == ("absent", "corrected")
    bad = call("submit", labels=[{"label": "Pleural Effusion", "status": "absent", "reason": "x",
                                  "evidence": [{"sentence_id": "F1", "quote": "invented text"}]}])
    _, f = run(script([bad]), tmp_path / "c", "No pleural effusion.", Pleural_Effusion=("present", ["F1"]))
    x = by(f)["Pleural Effusion"]
    assert (x.status, x.verification) == ("present", "unverified") and "string check" in x.reason


def test_tool_cap_leaves_escalated_labels_unverified(tmp_path: Path) -> None:
    r, f = run(script([call("normal_check")]), tmp_path)
    assert r.stop == "tool_cap" and r.tool_calls == va.MAX_TOOL_CALLS
    assert by(f)["Pleural Effusion"].verification == "unverified" and "tool_cap" in by(f)["Pleural Effusion"].reason


def test_no_finding_withheld_and_findings_suggested(tmp_path: Path) -> None:
    sub = call("submit", labels=[
        {"label": "No Finding", "status": "not_mentioned", "reason": "granuloma", "evidence": []},
        {"label": "Other Abnormality", "status": "present", "reason": "granuloma",
         "evidence": [{"sentence_id": "F1", "quote": "Calcified granuloma"}]}])
    _, f = run(script([call("normal_check")], [sub]), tmp_path, "Calcified granuloma.", "No acute disease.")
    assert (by(f)["No Finding"].status, by(f)["No Finding"].verification) == ("not_mentioned", "corrected")
    assert by(f)["Other Abnormality"].verification == "suggested"


def test_no_finding_confirmed_from_impression_only(tmp_path: Path) -> None:
    sub = call("submit", labels=[{"label": "No Finding", "status": "present", "reason": "normal",
                                  "evidence": [{"sentence_id": "I1", "quote": "No acute disease"}]}])
    _, f = run(script([sub]), tmp_path, "", "No acute disease.")
    assert (by(f)["No Finding"].status, by(f)["No Finding"].verification) == ("present", "verified_impression_only")


def test_non_escalated_labels_can_only_be_added(tmp_path: Path) -> None:
    sub = call("submit", labels=[{"label": "Cardiomegaly", "status": "absent", "reason": "x",
                                  "evidence": [{"sentence_id": "F1", "quote": "Heart size is normal"}]}])
    _, f = run(script([sub]), tmp_path, "Heart size is normal. Small left pleural effusion.")
    assert by(f)["Cardiomegaly"].verification == "verified_rules"


def test_prompt_and_tools_frozen() -> None:
    h = hashlib.sha256((va.SYSTEM + json.dumps(va.TOOLS, sort_keys=True)).encode()).hexdigest()
    if FROZEN_SHA256 == "TO-BE-PINNED":
        pytest.skip(f"verifier prompt not frozen yet (sha256 {h})")
    assert h == FROZEN_SHA256, "verifier-agent prompt or tools changed: needs owner OK + new PROMPT_VERSION"
