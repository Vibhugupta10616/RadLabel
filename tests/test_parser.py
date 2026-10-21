"""Parser (README §6.1) and run_pipeline wiring."""

import json
from pathlib import Path

from test_extractor import answer

from radlabel.llm import FakeLLM
from radlabel.pipeline import run_pipeline
from radlabel.preprocess.parser import parse_report


def test_standard_headers_inline_and_on_lines() -> None:
    p = parse_report("INDICATION: Cough. COMPARISON: None. FINDINGS: Heart is normal. IMPRESSION: No acute disease.")
    assert (p.indication, p.comparison, p.findings, p.impression) == (
        "Cough.", "None.", "Heart is normal.", "No acute disease.")
    assert p.sections_identified and p.headers == ["INDICATION", "COMPARISON", "FINDINGS", "IMPRESSION"]
    p = parse_report("Findings\nLungs are clear.\nNo effusion.\n\nImpression\nNormal chest.")
    assert (p.findings, p.impression) == ("Lungs are clear. No effusion.", "Normal chest.")


def test_header_variants_case_and_punctuation() -> None:
    p = parse_report("Clinical history - chest pain\nreason for exam: fever\nfindings : Small effusion.\n"
                     "Conclusion: Effusion.")
    assert (p.indication, p.findings, p.impression) == ("chest pain fever", "Small effusion.", "Effusion.")
    for h in ("Opinion:", "SUMMARY:", "impression:"):
        assert parse_report(f"FINDINGS: x. {h} y.").impression == "y."


def test_header_words_inside_text_are_not_headers() -> None:
    p = parse_report("FINDINGS: History of smoking. Stable compared with prior findings: no change.")
    assert p.findings == "History of smoking. Stable compared with prior findings: no change." and not p.impression


def test_no_headers_is_one_block_read_as_findings() -> None:
    p = parse_report("Heart size normal. Lungs clear.")
    assert not p.sections_identified and p.findings == "Heart size normal. Lungs clear." and not p.impression


def test_preamble_goes_to_findings_only_without_a_findings_header() -> None:
    assert parse_report("Heart is enlarged. IMPRESSION: Cardiomegaly.").findings == "Heart is enlarged."
    p = parse_report("Chest 2 views. FINDINGS: Clear. IMPRESSION: Normal.")
    assert p.findings == "Clear." and p.unassigned == "Chest 2 views."


def test_run_pipeline_parse_tag_verify(tmp_path: Path) -> None:
    seen: list[str] = []

    def responder(messages: list[dict]) -> str:
        seen.append(json.dumps(messages))
        return answer(Cardiomegaly=("present", ["F1"]), Pleural_Effusion=("absent", ["I1"]))

    r = run_pipeline("INDICATION: dyspnea. FINDINGS: Borderline cardiomegaly. IMPRESSION: No pleural effusion.",
                     FakeLLM(responder, tmp_path))
    assert [s.id for s in r.sentences] == ["F1", "I1"]
    assert r.labels.status("Cardiomegaly") == "present"  # M6 hedge fix: "borderline" is not a hedge here
    assert r.labels.status("No Finding") == "not_mentioned" and r.sections_identified
    r = run_pipeline("Indication dyspnea. Borderline cardiomegaly.", FakeLLM(responder, tmp_path))
    assert not r.sections_identified  # no headers: visible in the output (the tagger also read the indication)
    assert "dyspnea" not in seen[0]  # the indication is never a tagger input


def test_run_pipeline_content_filter_falls_back_to_rules(tmp_path: Path) -> None:
    llm = FakeLLM(lambda m: "", tmp_path)
    real = llm._call

    def filtered(*a: object, **k: object) -> object:
        return real(*a, **k).model_copy(update={"filtered": True})  # type: ignore[arg-type]
    llm._call = filtered  # type: ignore[method-assign]
    r = run_pipeline("FINDINGS: Small left pleural effusion.", llm)
    assert r.content_filtered and r.tagger is None and r.labels.status("Pleural Effusion") == "present"
