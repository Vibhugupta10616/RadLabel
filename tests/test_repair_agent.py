import json
from pathlib import Path
from typing import Any

from radlabel.labelling.repair_agent import MAX_TOOL_CALLS, repair
from radlabel.labelling.schema import LabelOut, ReportLabels
from radlabel.labelling.verifier import verify
from radlabel.labels import LABELS
from radlabel.llm import FakeLLM
from radlabel.preprocess.sentences import report_sentences

SENTS = report_sentences("Heart is large. No pleural effusion.", "Cardiomegaly.")


def tier1(**over: tuple[str, list[str]]) -> ReportLabels:
    labs = {lab: LabelOut(label=lab, status="not_mentioned") for lab in LABELS}
    for k, (st, ev) in over.items():
        labs[k.replace("_", " ")] = LabelOut(label=k.replace("_", " "), status=st, evidence=ev)
    return verify(ReportLabels(report_id="1", labels=list(labs.values())), SENTS)


def script(*steps: list[dict[str, Any]]) -> Any:
    def responder(messages: list[dict[str, Any]]) -> Any:
        return steps[min(sum(m["role"] == "assistant" for m in messages), len(steps) - 1)]
    return responder


def call(name: str, **args: Any) -> dict[str, str]:
    return {"name": name, "arguments": json.dumps(args)}


# Cardiomegaly cites F1 "Heart is large." (no alias) -> evidence_mentions_label fail
FAILING = tier1(Cardiomegaly=("present", ["F1"]), Pleural_Effusion=("absent", ["F2"]))


def test_fixture_fails() -> None:
    assert [m.label for m in FAILING.verifier_messages if m.level == "fail"] == ["Cardiomegaly"]


def test_accepted_fix_passes_reverification(tmp_path: Path) -> None:
    llm = FakeLLM(script([call("check_negation", sentence_id="I1")],
                         [call("submit_fix", labels=[{"label": "Cardiomegaly", "status": "present",
                                                      "evidence": ["F1", "I1"]}], reason="I1 names it")]), tmp_path)
    r = repair(llm, "1", SENTS, FAILING)
    assert r.accepted and r.route == "repaired" and r.final.tier == 2 and r.stop == "submitted"
    assert r.final.status("Cardiomegaly") == "present" and r.tool_names == ["check_negation", "submit_fix"]
    again = repair(llm, "1", SENTS, FAILING)  # cached: no new calls, same result
    assert llm.calls == 2 and again.final == r.final and again.cached_calls == 2


def test_unchanged_correct_label_goes_to_review_with_tier1_labels(tmp_path: Path) -> None:
    llm = FakeLLM(script([call("submit_fix", labels=[{"label": "Cardiomegaly", "status": "present",
                                                      "evidence": ["F1"]}], reason="heart is large = enlarged")]),
                  tmp_path)
    r = repair(llm, "1", SENTS, FAILING)
    assert not r.accepted and r.route == "review" and r.final.labels == FAILING.labels


def test_changes_to_non_failing_labels_are_ignored(tmp_path: Path) -> None:
    llm = FakeLLM(script([call("submit_fix", reason="x", labels=[
        {"label": "Cardiomegaly", "status": "present", "evidence": ["I1"]},
        {"label": "Pleural Effusion", "status": "present", "evidence": ["F2"]}])]), tmp_path)
    r = repair(llm, "1", SENTS, FAILING)
    assert r.accepted and r.ignored_changes == 1 and r.final.status("Pleural Effusion") == "absent"


def test_tool_cap_stops_and_routes_to_review(tmp_path: Path) -> None:
    llm = FakeLLM(script([call("get_sentence", sentence_id="F1")]), tmp_path)
    r = repair(llm, "1", SENTS, FAILING)
    assert r.stop == "tool_cap" and r.tool_calls == MAX_TOOL_CALLS and r.route == "review"


def test_no_tool_call_routes_to_review(tmp_path: Path) -> None:
    r = repair(FakeLLM(lambda m: "I think it is fine.", tmp_path), "1", SENTS, FAILING)
    assert r.stop == "no_tool_call" and r.route == "review" and r.submitted is None
