"""Tier 2 repair agent (SPEC §6.2): a bounded LangGraph tool loop, then re-verification.

- Inputs are ONLY the report's sentences, its verified Tier 1 labels and the verifier FAIL messages (owner, M5).
  Never expert codes, eval mentions, folds or metrics: tests/test_repair_leakage.py.
- Model: the repair deployment (gpt-5-mini) through `radlabel.llm` (cached, cost-logged, budget-capped). LangGraph
  only runs the loop.
- Limits per report: MAX_TOOL_CALLS tool calls (submit_fix included) and MAX_REPORT_TOKENS tokens; on either the
  loop stops and the report goes to review.
- submit_fix may change only labels with a FAIL message; changes to other labels are ignored (and counted).
- Acceptance (pre-committed, docs/evaluation_notes.md): the fixed labels are kept only if they pass re-verification;
  otherwise the report keeps its Tier 1 labels and goes to review.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from functools import lru_cache
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from radlabel.labelling.extractor import STATUSES, SYSTEM
from radlabel.labelling.schema import LabelOut, ReportLabels, derive_no_finding
from radlabel.labelling.verifier import normal_phrases, passed, section_rule, verify
from radlabel.labels import LABELS, NO_FINDING
from radlabel.llm import LLMClient
from radlabel.preprocess.aliases import aliases
from radlabel.preprocess.negation import Mention, mentions
from radlabel.preprocess.sentences import Sentence

PROMPT_VERSION = "repair-v1"
MAX_TOOL_CALLS = 6  # SPEC §6.2
MAX_REPORT_TOKENS = 60_000  # input + output over all calls of one report
MAX_COMPLETION_TOKENS = 4_000  # per call (reasoning included); Azure counts it against REPAIR_TPM
REASONING_EFFORT = "low"
FIXABLE = [lab for lab in LABELS if lab != NO_FINDING]  # No Finding is derived in code

REPAIR_SYSTEM = f"""You repair chest X-ray report labels that failed deterministic consistency checks.
You get the report as numbered sentences (Findings F1..Fn, Impression I1..In), the current labels (status and
evidence sentence IDs) and the check failures. "[REDACTED]" marks words removed for privacy; never guess them.

Statuses: present (the report states the finding), absent (the report explicitly says it is not there),
uncertain (the report hedges about it), not_mentioned (not discussed; no evidence). present, absent and uncertain
must cite the IDs of sentences that mention the finding. Use get_label_rules for a label's definition.

The checks use a fixed alias list and simple negation rules, and they can be wrong. Decide what the report
actually says. If a current label is correct, submit it unchanged: never change a correct label just to satisfy a
check (the report then goes to human review). Fix only the labels named in the failures.

You have at most {MAX_TOOL_CALLS} tool calls in total, including submit_fix. Always finish with submit_fix."""


def _fn(name: str, desc: str, props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": desc, "strict": True,
        "parameters": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}}}


_SID = {"sentence_id": {"type": "string", "description": "e.g. F2 or I1"}}
_LAB = {"label": {"type": "string", "enum": FIXABLE}}
TOOLS = [
    _fn("get_sentence", "Text and section of one sentence.", _SID),
    _fn("check_negation", "The pipeline's label mentions in one sentence, with negation and hedge tags.", _SID),
    _fn("get_label_rules", "Definition, aliases recognised by the checks, and normal phrases for a label.", _LAB),
    _fn("compare_sections", "Mentions of a label in Findings vs Impression, and the section-rule result.", _LAB),
    _fn("submit_fix", "Submit the corrected labels (only labels named in the failures). Ends the repair.", {
        "labels": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["label", "status", "evidence"], "properties": {
                                                  "label": {"type": "string", "enum": FIXABLE},
                                                  "status": {"type": "string", "enum": STATUSES},
                                                  "evidence": {"type": "array", "items": {"type": "string"}}}}},
        "reason": {"type": "string", "description": "one short sentence"}}),
]


@lru_cache
def definitions() -> dict[str, str]:
    """Label definitions from the frozen Tier 1 prompt (one source of truth)."""
    block = SYSTEM.split("Labels (", 1)[1].split("\n\nSections:", 1)[0]
    out = {}
    for item in block.split("\n- ")[1:]:
        name, _, text = item.partition(":")
        out[name.strip()] = " ".join(text.split())
    return out


class RepairResult(BaseModel):
    report_id: str
    final: ReportLabels
    route: str  # "repaired" | "review"
    stop: str  # submitted | tool_cap | token_cap | no_tool_call | content_filtered
    accepted: bool
    tool_calls: int
    tool_names: list[str]
    llm_calls: int
    tokens: int
    cost_usd: float  # cost of the calls as made (cache hits keep it), so the result is the same on every rerun
    cached_calls: int  # run-specific
    models: list[str]  # model versions returned (cache hits keep them)
    ignored_changes: int
    submitted: list[LabelOut] | None


class _State(TypedDict):
    messages: list[dict[str, Any]]
    calls: int
    tokens: int
    llm_calls: int
    cached_calls: int
    cost: float
    names: list[str]
    models: list[str]
    fix: list[dict[str, Any]] | None
    stop: str


def _ment_json(sid: str, ms: list[Mention]) -> list[dict[str, Any]]:
    return [{"sentence_id": sid, "label": m.label, "alias": m.alias, "negated": m.negated, "hedged": m.hedged,
             "affirmed": m.affirmed} for m in ms]


def tool_impls(sentences: list[Sentence], current: dict[str, str]) -> dict[str, Callable[..., Any]]:
    by_id = {s.id: s for s in sentences}
    ments = {s.id: mentions(s.text) for s in sentences}

    def get_sentence(sentence_id: str) -> Any:
        s = by_id.get(sentence_id)
        return {"id": s.id, "section": s.section, "text": s.text} if s else {"error": f"unknown id {sentence_id}"}

    def check_negation(sentence_id: str) -> Any:
        return {"mentions": _ment_json(sentence_id, ments[sentence_id])} if sentence_id in ments else {
            "error": f"unknown id {sentence_id}"}

    def get_label_rules(label: str) -> Any:
        return {"label": label, "definition": definitions().get(label, ""),
                "aliases": sorted({a.text.replace("_", "") for a in aliases().get(label, [])}),
                "normal_phrases_that_support_absent": normal_phrases().get(label, [])}

    def compare_sections(label: str) -> Any:
        def sec(name: str) -> list[dict[str, Any]]:
            return [x for s in sentences if s.section == name
                    for x in _ment_json(s.id, [m for m in ments[s.id] if m.label == label])]
        return {"findings": sec("findings"), "impression": sec("impression"),
                "section_rule": section_rule(label, current.get(label, "not_mentioned"), sentences, ments)}

    return {"get_sentence": get_sentence, "check_negation": check_negation, "get_label_rules": get_label_rules,
            "compare_sections": compare_sections}


def user_message(sentences: list[Sentence], verified: ReportLabels) -> str:
    body = "\n".join(f"{s.id}: {s.text}" for s in sentences) or "(empty report)"
    labs = "\n".join(f"- {x.label}: {x.status} {x.evidence}" for x in verified.labels if x.label != NO_FINDING)
    fails = "\n".join(f"- {m.label} ({m.check}): {m.detail}" for m in verified.verifier_messages if m.level == "fail")
    return f"Report:\n{body}\n\nCurrent labels:\n{labs}\n\nFailures:\n{fails}"


def repair(llm: LLMClient, report_id: str, sentences: list[Sentence], verified: ReportLabels) -> RepairResult:
    """`verified`: the Tier 1 output after the verifier, with at least one FAIL message."""
    current: dict[str, str] = {x.label: x.status for x in verified.labels}
    impls = tool_impls(sentences, current)

    def agent(st: _State) -> dict[str, Any]:
        r = llm.complete(st["messages"], "repair", tools=TOOLS, max_tokens=MAX_COMPLETION_TOKENS, temperature=None,
                         reasoning_effort=REASONING_EFFORT, purpose=f"repair:{PROMPT_VERSION}")
        upd: dict[str, Any] = {"llm_calls": st["llm_calls"] + 1, "cached_calls": st["cached_calls"] + r.cached,
                               "tokens": st["tokens"] + r.input_tokens + r.output_tokens,
                               "cost": st["cost"] + r.cost_usd,  # original call cost, also when served from cache
                               "models": sorted({*st["models"], r.model})}
        if r.filtered:
            return {**upd, "stop": "content_filtered"}
        if not r.tool_calls:
            return {**upd, "stop": "no_tool_call"}
        msg = {"role": "assistant", "content": r.text or None, "tool_calls": [
            {"id": t["id"], "type": "function", "function": {"name": t["name"], "arguments": t["arguments"]}}
            for t in r.tool_calls]}
        return {**upd, "messages": [*st["messages"], msg]}

    def tools(st: _State) -> dict[str, Any]:
        msgs, calls, names = list(st["messages"]), st["calls"], list(st["names"])
        fix, stop = st["fix"], st["stop"]
        for t in msgs[-1]["tool_calls"]:
            name = t["function"]["name"]
            if calls >= MAX_TOOL_CALLS:
                out: Any = {"error": "tool-call limit reached"}
            else:
                calls += 1
                names.append(name)
                try:
                    args = json.loads(t["function"]["arguments"])
                    if name == "submit_fix":
                        fix, stop, out = list(args["labels"]), "submitted", {"ok": True}
                    else:
                        out = impls[name](**args)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    out = {"error": f"invalid call: {type(e).__name__}"}
            if not stop and calls == MAX_TOOL_CALLS - 1:
                out = {"result": out, "note": "1 tool call left: call submit_fix now"}
            msgs.append({"role": "tool", "tool_call_id": t["id"], "content": json.dumps(out)})
        if not stop and calls >= MAX_TOOL_CALLS:
            stop = "tool_cap"
        if not stop and st["tokens"] >= MAX_REPORT_TOKENS:
            stop = "token_cap"
        return {"messages": msgs, "calls": calls, "names": names, "fix": fix, "stop": stop}

    g: Any = StateGraph(_State)  # langgraph's overloads don't accept partial-update node functions under mypy
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", lambda st: END if st["stop"] else "tools")
    g.add_conditional_edges("tools", lambda st: END if st["stop"] else "agent")
    init: _State = {"messages": [{"role": "system", "content": REPAIR_SYSTEM},
                                 {"role": "user", "content": user_message(sentences, verified)}],
                    "calls": 0, "tokens": 0, "llm_calls": 0, "cached_calls": 0, "cost": 0.0, "names": [], "models": [],
                    "fix": None, "stop": ""}
    st = g.compile().invoke(init, {"recursion_limit": 4 * MAX_TOOL_CALLS + 4})

    failing = {m.label for m in verified.verifier_messages if m.level == "fail"}
    new = {x.label: x for x in verified.labels}
    submitted, ignored = None, 0
    if st["fix"] is not None:
        submitted = []
        for f in st["fix"]:
            lo = LabelOut(label=f["label"], status=f["status"],
                          evidence=[] if f["status"] == "not_mentioned" else list(f["evidence"]))
            submitted.append(lo)
            if lo.label in failing:
                new[lo.label] = lo
            else:
                ignored += 1
    accepted = False
    final = verified.model_copy(update={"route": "review"})
    if submitted is not None:
        fixed = derive_no_finding(ReportLabels(report_id=report_id, tier=2, labels=[
            new[lab] for lab in LABELS if lab != NO_FINDING]))
        v = verify(fixed, sentences)
        if passed(v):
            accepted, final = True, v.model_copy(update={"route": "repaired"})
    return RepairResult(report_id=report_id, final=final, route=final.route, stop=st["stop"], accepted=accepted,
                        tool_calls=st["calls"], tool_names=st["names"], llm_calls=st["llm_calls"],
                        tokens=st["tokens"], cost_usd=st["cost"], cached_calls=st["cached_calls"],
                        ignored_changes=ignored, submitted=submitted, models=st["models"])
