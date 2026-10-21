"""Verifier agent (README §6.2, M7): a bounded ReAct tool loop (LangGraph) that runs only on escalated reports.

- Model: the agent deployment (role "repair" = gpt-5-mini) through `radlabel.llm` (cached, cost-logged, capped).
- Blind first: it gets the report sentences, the tagger's statuses WITHOUT the tagger's evidence, and the escalation
  reasons (free_checks.py). Never codes from the dataset, folds, eval mentions or metrics
  (tests/test_verifier_agent_leakage.py).
- Tools: find_by_alias, find_by_meaning (sentence embeddings, base model until M9), check_negation,
  compare_sections, check_redaction, get_label_definition (the frozen Tier 1 definitions), normal_check, submit.
- Limits: MAX_TOOL_CALLS tool calls (submit included) and MAX_REPORT_TOKENS tokens per report; on a cap, the budget
  or a content-filter refusal, the escalated labels end `unverified` with the reason.
- Evidence is string-checked: each item is a sentence ID plus a quote that must occur in that sentence.
- Per label (`final_labels`): verified_rules (not escalated) | verified | verified_impression_only (no Findings) |
  corrected (status changed) | suggested (a finding the tagger missed: absent/not_mentioned -> present/uncertain) |
  unverified (with reason). No Finding stays consistent: any present/uncertain label withholds it.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, Literal, TypedDict

import numpy as np
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from radlabel.config import get_settings
from radlabel.labelling.extractor import STATUSES
from radlabel.labelling.free_checks import Escalation, normal_check
from radlabel.labelling.repair_agent import _ment_json, definitions
from radlabel.labelling.schema import ReportLabels
from radlabel.labelling.verifier import section_rule
from radlabel.labels import LABELS, NO_FINDING
from radlabel.llm import LLMClient
from radlabel.preprocess.aliases import normalise
from radlabel.preprocess.negation import mentions, redaction_adjacent
from radlabel.preprocess.sentences import Sentence
from radlabel.preprocess.text import REDACTED

PROMPT_VERSION = "verifier-v2"  # FROZEN on the dev slice (v1-v3 tried, v2 kept by the pre-set rule); hash test
MAX_TOOL_CALLS = 8  # README §6.2
MAX_REPORT_TOKENS = 80_000  # input + output over all calls of one report
MAX_COMPLETION_TOKENS = 4_000  # per call, reasoning included
REASONING_EFFORT = "low"
MEANING_TOP_K = 5
AGENT_STATUSES = [*STATUSES, "cannot_verify"]
Verification = Literal["verified_rules", "verified", "verified_impression_only", "corrected", "suggested",
                       "unverified"]

SYSTEM = f"""You verify the labels another model (the tagger) gave a chest X-ray report.
The report is a list of numbered sentences: Findings F1..Fn, Impression I1..In. "[REDACTED]" marks words removed
for privacy; never guess them. If the report's sections could not be identified, all sentences are F sentences.

You see the tagger's status for every label but not its evidence: find the evidence yourself with the tools.
Automatic checks escalated some labels; their reasons are listed. The checks use fixed word lists and simple
negation rules and are often wrong, so decide what the report actually says.

An escalation is a reason to look, not evidence: most escalations are false alarms. Keep the tagger's status unless
the text clearly supports another one; if the text is ambiguous, keep the tagger's status.

For every escalated label, submit the status the report supports:
- present: the report states the finding as there now.
- absent: the report explicitly says the finding is not there. A size qualifier does not make it uncertain
  ("no large effusion" is absent).
- uncertain: the report itself hedges about it ("possible", "may represent", "cannot exclude", "versus").
- not_mentioned: the report does not talk about it.
- cannot_verify: the text does not let you decide (for example, the key word is [REDACTED]).
A finding described as removed, resolved or no longer seen is not present. A heart "at the upper limits of normal"
is normal size, not enlarged.

Label definitions (binding; judge each label on its own, one label never implies another):
{{definitions}}

No Finding means the report describes no abnormality of any kind, including chronic or incidental findings. If No
Finding is escalated and the report contains only normal statements (general ones such as "no acute disease"
included) and nothing abnormal, confirm it (present). If the report states any abnormality, submit No Finding as
not_mentioned and add each abnormal finding as its own label.
You may also add a label that was not escalated, but only as present or uncertain, and only if the report clearly
states a finding the tagger missed.

Evidence: for present, absent and uncertain give at least one item: a sentence ID and an exact quote copied from
that sentence. Quotes are checked character by character; a label with no valid evidence is discarded.
You have at most {MAX_TOOL_CALLS} tool calls in total, including submit. Always finish with submit."""
# the frozen Tier 1 label definitions (one source of truth with the tagger and get_label_definition)
SYSTEM = SYSTEM.replace("{definitions}", "\n".join(f"- {k}: {v}" for k, v in definitions().items()))


def _fn(name: str, desc: str, props: dict[str, Any]) -> dict[str, Any]:
    return {"type": "function", "function": {
        "name": name, "description": desc, "strict": True,
        "parameters": {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}}}


_SID = {"sentence_id": {"type": "string", "description": "e.g. F2 or I1"}}
_LAB = {"label": {"type": "string", "enum": LABELS}}
TOOLS = [
    _fn("find_by_alias", "Sentences mentioning the label's known words, with negation and hedge tags.", _LAB),
    _fn("find_by_meaning", f"The {MEANING_TOP_K} sentences closest in meaning to the label definition.", _LAB),
    _fn("check_negation", "A sentence's text and its label mentions, with negation and hedge tags.", _SID),
    _fn("compare_sections", "Mentions of a label in Findings vs Impression, and the section-rule result.", _LAB),
    _fn("check_redaction", "Whether a sentence contains [REDACTED], and whether it sits next to a finding word.", _SID),
    _fn("get_label_definition", "What the label covers (binding definition).", _LAB),
    _fn("normal_check", "Which body regions have normal statements, and which sentences look abnormal.", {}),
    _fn("submit", "Submit your decisions. Ends the verification.", {
        "labels": {"type": "array", "items": {"type": "object", "additionalProperties": False,
                                              "required": ["label", "status", "evidence", "reason"], "properties": {
            "label": {"type": "string", "enum": LABELS},
            "status": {"type": "string", "enum": AGENT_STATUSES},
            "evidence": {"type": "array", "items": {
                "type": "object", "additionalProperties": False, "required": ["sentence_id", "quote"],
                "properties": {"sentence_id": {"type": "string"}, "quote": {"type": "string"}}}},
            "reason": {"type": "string", "description": "one short sentence"}}}}}),
]


@lru_cache
def _encoder() -> Any:
    from sentence_transformers import SentenceTransformer  # optional extra "embed"

    s = get_settings()
    return SentenceTransformer(s.embed_base_model, device=None if s.device == "auto" else s.device)


def encode(texts: list[str]) -> np.ndarray:
    """Unit-normalised sentence embeddings (tests replace this function)."""
    return np.asarray(_encoder().encode(texts, normalize_embeddings=True))


QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge retrieval instruction


def tool_impls(sentences: list[Sentence], tagger: dict[str, str]) -> dict[str, Any]:
    by_id = {s.id: s for s in sentences}
    ments = {s.id: mentions(s.text) for s in sentences}

    def unknown(sid: str) -> dict[str, str]:
        return {"error": f"unknown sentence id {sid}"}

    def find_by_alias(label: str) -> Any:
        return {"label": label, "mentions": [{**x, "text": by_id[x["sentence_id"]].text} for s in sentences
                                             for x in _ment_json(s.id, [m for m in ments[s.id] if m.label == label])]}

    def find_by_meaning(label: str) -> Any:
        if not sentences:
            return {"label": label, "sentences": []}
        try:
            v = encode([QUERY_PREFIX + f"{label}: {definitions().get(label, '')}"] + [s.text for s in sentences])
        except ImportError:  # optional extra "embed" not installed: the agent still has its other tools
            return {"error": "sentence embeddings unavailable; use find_by_alias"}
        sims = v[1:] @ v[0]
        top = np.argsort(-sims, kind="stable")[:MEANING_TOP_K]
        return {"label": label, "sentences": [{"sentence_id": sentences[i].id, "text": sentences[i].text,
                                               "score": round(float(sims[i]), 3)} for i in top]}

    def check_negation(sentence_id: str) -> Any:
        s = by_id.get(sentence_id)
        return {"sentence_id": s.id, "section": s.section, "text": s.text,
                "mentions": _ment_json(s.id, ments[s.id])} if s else unknown(sentence_id)

    def compare_sections(label: str) -> Any:
        def sec(name: str) -> list[dict[str, Any]]:
            return [x for s in sentences if s.section == name
                    for x in _ment_json(s.id, [m for m in ments[s.id] if m.label == label])]
        return {"findings": sec("findings"), "impression": sec("impression"),
                "section_rule": section_rule(label, tagger.get(label, "not_mentioned"), sentences, ments)}

    def check_redaction(sentence_id: str) -> Any:
        s = by_id.get(sentence_id)
        return {"sentence_id": s.id, "text": s.text, "contains_redacted": REDACTED in s.text,
                "redacted_next_to_finding_word": redaction_adjacent(s.text)} if s else unknown(sentence_id)

    def get_label_definition(label: str) -> Any:
        return {"label": label, "definition": definitions().get(label, "")}

    def normal_check_tool() -> Any:
        return normal_check(sentences).model_dump()

    return {"find_by_alias": find_by_alias, "find_by_meaning": find_by_meaning, "check_negation": check_negation,
            "compare_sections": compare_sections, "check_redaction": check_redaction,
            "get_label_definition": get_label_definition, "normal_check": normal_check_tool}


def user_message(sentences: list[Sentence], tagger: ReportLabels, esc: list[Escalation],
                 sections_identified: bool) -> str:
    body = "\n".join(f"{s.id}: {s.text}" for s in sentences) or "(empty report)"
    note = "" if sections_identified else "\n(Sections could not be identified: every sentence is an F sentence.)"
    labs = "\n".join(f"- {x.label}: {x.status}" for x in tagger.labels)
    reasons = "\n".join(f"- {e.label} ({e.reason}): {e.detail}" for e in esc)
    return f"Report:\n{body}{note}\n\nTagger labels (status only):\n{labs}\n\nEscalated labels and reasons:\n{reasons}"


class Evidence(BaseModel):
    sentence_id: str
    quote: str


class Decision(BaseModel):
    label: str
    status: str
    evidence: list[Evidence]
    reason: str


class AgentResult(BaseModel):
    report_id: str
    stop: str  # submitted | tool_cap | token_cap | no_tool_call | content_filtered | budget
    decisions: list[Decision] | None
    tool_calls: int
    tool_names: list[str]
    llm_calls: int
    tokens: int
    cost_usd: float  # cost of the calls as made (cache hits keep it)
    cached_calls: int = 0  # run-specific (left out of prediction files)
    models: list[str]


class FinalLabel(BaseModel):
    label: str
    status: str
    evidence: list[str]
    verification: Verification
    reason: str = ""
    # present or suggested labels: which sections the evidence comes from (code only; routing never uses it)
    corroboration: Literal["both", "findings", "impression", "none"] | None = None


class _State(TypedDict):
    messages: list[dict[str, Any]]
    calls: int
    tokens: int
    llm_calls: int
    cached_calls: int
    cost: float
    names: list[str]
    models: list[str]
    decisions: list[dict[str, Any]] | None
    stop: str


def run_agent(llm: LLMClient, report_id: str, sentences: list[Sentence], tagger: ReportLabels,
              esc: list[Escalation], sections_identified: bool = True) -> AgentResult:
    """`tagger`: the tagger's labels after the deterministic verifier; only their statuses are shown."""
    impls = tool_impls(sentences, {x.label: x.status for x in tagger.labels})

    def agent(st: _State) -> dict[str, Any]:
        r = llm.complete(st["messages"], "repair", tools=TOOLS, max_tokens=MAX_COMPLETION_TOKENS, temperature=None,
                         reasoning_effort=REASONING_EFFORT, purpose=f"verifier_agent:{PROMPT_VERSION}")
        upd: dict[str, Any] = {"llm_calls": st["llm_calls"] + 1, "cached_calls": st["cached_calls"] + r.cached,
                               "tokens": st["tokens"] + r.input_tokens + r.output_tokens,
                               "cost": st["cost"] + r.cost_usd, "models": sorted({*st["models"], r.model})}
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
        decisions, stop = st["decisions"], st["stop"]
        for t in msgs[-1]["tool_calls"]:
            name = t["function"]["name"]
            if calls >= MAX_TOOL_CALLS:
                out: Any = {"error": "tool-call limit reached"}
            else:
                calls += 1
                names.append(name)
                try:
                    args = json.loads(t["function"]["arguments"])
                    if name == "submit":
                        decisions, stop, out = list(args["labels"]), "submitted", {"ok": True}
                    elif name == "normal_check":
                        out = impls["normal_check"]()
                    else:
                        out = impls[name](**args)
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    out = {"error": f"invalid call: {type(e).__name__}"}
            if not stop and calls == MAX_TOOL_CALLS - 1:
                out = {"result": out, "note": "1 tool call left: call submit now"}
            msgs.append({"role": "tool", "tool_call_id": t["id"], "content": json.dumps(out)})
        if not stop and calls >= MAX_TOOL_CALLS:
            stop = "tool_cap"
        if not stop and st["tokens"] >= MAX_REPORT_TOKENS:
            stop = "token_cap"
        return {"messages": msgs, "calls": calls, "names": names, "decisions": decisions, "stop": stop}

    g: Any = StateGraph(_State)
    g.add_node("agent", agent)
    g.add_node("tools", tools)
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", lambda st: END if st["stop"] else "tools")
    g.add_conditional_edges("tools", lambda st: END if st["stop"] else "agent")
    init: _State = {"messages": [{"role": "system", "content": SYSTEM},
                                 {"role": "user", "content": user_message(sentences, tagger, esc,
                                                                          sections_identified)}],
                    "calls": 0, "tokens": 0, "llm_calls": 0, "cached_calls": 0, "cost": 0.0, "names": [],
                    "models": [], "decisions": None, "stop": ""}
    st = g.compile().invoke(init, {"recursion_limit": 4 * MAX_TOOL_CALLS + 4})
    decisions = None
    if st["decisions"] is not None:
        decisions = [Decision(label=d["label"], status=d["status"], reason=d.get("reason", ""),
                              evidence=[Evidence(**e) for e in d.get("evidence", [])]) for d in st["decisions"]]
    return AgentResult(report_id=report_id, stop=st["stop"], decisions=decisions, tool_calls=st["calls"],
                       tool_names=st["names"], llm_calls=st["llm_calls"], tokens=st["tokens"], cost_usd=st["cost"],
                       cached_calls=st["cached_calls"], models=st["models"])


def valid_evidence(ev: list[Evidence], sentences: list[Sentence]) -> list[str]:
    """IDs whose quote occurs verbatim (case and spacing aside) in that sentence."""
    by_id = {s.id: normalise(s.text) for s in sentences}
    return sorted({e.sentence_id for e in ev
                   if e.sentence_id in by_id and normalise(e.quote) and normalise(e.quote) in by_id[e.sentence_id]})


def final_labels(tagger: ReportLabels, sentences: list[Sentence], esc: list[Escalation],
                 result: AgentResult | None, not_run_reason: str = "agent not run") -> list[FinalLabel]:
    """Merge the tagger's labels, the escalations and the agent's decisions into the per-label output."""
    has_findings = any(s.section == "findings" for s in sentences)
    asked = {e.label for e in esc}
    tag = {x.label: x for x in tagger.labels}
    out: dict[str, FinalLabel] = {lab: FinalLabel(label=lab, status=tag[lab].status, evidence=tag[lab].evidence,
                                                  verification="verified_rules") for lab in LABELS}
    if NO_FINDING not in asked and tag[NO_FINDING].status == "present":
        out[NO_FINDING].evidence = sorted({i for ids in normal_check(sentences).covered.values() for i in ids})
    why = not_run_reason if result is None else f"agent stopped: {result.stop}"
    for lab in asked:
        out[lab] = out[lab].model_copy(update={"verification": "unverified", "reason": why})
    decided = {d.label: d for d in (result.decisions or [])} if result is not None else {}
    for lab, d in decided.items():
        t = tag[lab].status
        if lab not in asked and not (t in ("absent", "not_mentioned") and d.status in ("present", "uncertain")):
            continue  # not escalated: only a missed finding may be added
        if d.status == "cannot_verify":
            out[lab] = out[lab].model_copy(update={"verification": "unverified", "reason": d.reason})
            continue
        ev = valid_evidence(d.evidence, sentences)
        if d.status != "not_mentioned" and lab != NO_FINDING and not ev:
            if lab in asked:
                out[lab] = out[lab].model_copy(update={"verification": "unverified",
                                                       "reason": "agent evidence failed the string check"})
            continue
        if d.status == t:
            v: Verification = "verified" if has_findings else "verified_impression_only"
        elif t in ("absent", "not_mentioned") and d.status in ("present", "uncertain"):
            v = "suggested"
        else:
            v = "corrected"
        out[lab] = FinalLabel(label=lab, status=d.status, evidence=[] if d.status == "not_mentioned" else ev,
                              verification=v, reason=d.reason)
    # No Finding stays consistent with the other labels (it is derived, README §6.2)
    abnormal = any(x.status in ("present", "uncertain") for x in out.values() if x.label != NO_FINDING)
    nf = out[NO_FINDING]
    if abnormal and nf.status == "present":
        out[NO_FINDING] = FinalLabel(label=NO_FINDING, status="not_mentioned", evidence=[], verification="corrected",
                                     reason="withheld: abnormal findings")
    elif not abnormal and nf.status != "present" and NO_FINDING not in decided:  # the agent's withholding stands
        nc = normal_check(sentences)
        out[NO_FINDING] = FinalLabel(
            label=NO_FINDING, status="present", evidence=sorted({i for v in nc.covered.values() for i in v}),
            verification="verified_rules" if nc.ok else "unverified",
            reason="" if nc.ok else "derived after the agent's changes; normal check not passed")
    section = {s.id: s.section for s in sentences}
    for lab, x in out.items():
        if x.status == "present" or x.verification == "suggested":
            secs = {section[e] for e in x.evidence if e in section}
            out[lab] = x.model_copy(update={"corroboration": "both" if len(secs) == 2 else
                                            (secs.pop() if secs else "none")})
    return [out[lab] for lab in LABELS]
