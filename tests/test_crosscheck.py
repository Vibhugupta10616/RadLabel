import json
from pathlib import Path

import pytest

import data_prep.crosscheck_mapping as cc
from radlabel.llm import FakeLLM


def test_crosscheck_reports_only_disagreements(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "expert_labels.jsonl").write_text("\n".join(json.dumps({"major": m}) for m in [
        ["normal"], ["Cardiomegaly/mild"], ["Cysts/humerus/right"], ["No Indexing"]]), encoding="utf-8")
    monkeypatch.setattr(cc, "PROC", tmp_path)
    monkeypatch.setattr("radlabel.results.RESULTS_DIR", tmp_path / "results")
    answers = {"normal": "No Finding", "Cardiomegaly/mild": "Cardiomegaly", "Cysts/humerus": "Lung Lesion",
               "No Indexing": "ignore"}

    def responder(msgs: list[dict[str, str]]) -> str:
        pats = msgs[1]["content"].splitlines()[1:]
        return json.dumps({"assignments": [{"pattern": p, "label": answers[p]} for p in pats]})

    out = cc.main(FakeLLM(responder, tmp_path / "cache"))
    assert out["patterns"] == 4
    assert [(d["pattern"], d["rule"], d["llm"]) for d in out["disagreements"]] == [
        ("Cysts/humerus", ["Other Abnormality"], "Lung Lesion")]


def test_quote_check() -> None:
    from data_prep.crosscheck_context import quote_ok

    sents = ["Slight blunting at the left base is unchanged."]
    assert quote_ok('Blunting is not an effusion: "Slight blunting at the left base".', sents)
    assert not quote_ok('Invented: "large pleural effusion".', sents)
    assert not quote_ok("No quote at all.", sents)
