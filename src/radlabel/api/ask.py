"""Questions about the session's reports (SPEC §6.4, M10a).

- scope "report": the whole report (all sections, sentence IDs) and its labels go into the prompt; no retrieval.
- scope "all": RAG, a LangGraph of retrieve -> answer -> check over the session index (optional report / label
  filters); the model may only use the retrieved sentences.
- Structured output: an answer with citations (report_no, sentence_id), or a refusal. Code keeps only citations
  that were given to the model; an answer with no valid citation becomes NOT_STATED.
- Diagnosis, treatment and out-of-scope questions are refused (prompt rule). gpt-4.1-mini (the Tier 1 deployment)
  through radlabel.llm. Prompts are frozen (hash test, tests/test_api.py): ASK_REPORT_VERSION, ASK_ALL_VERSION.
"""

from __future__ import annotations

import json
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from radlabel.api.session import Entry, Session
from radlabel.llm import BudgetExceeded, LLMClient

ASK_REPORT_VERSION = "ask-report-v1"
ASK_ALL_VERSION = "ask-all-v1"
ASK_REPORT_VERSION_V2 = "ask-report-v2"  # ask v2 (M10b follow-up): developed on the dev slice only, then frozen
ASK_ALL_VERSION_V2 = "ask-all-v2"
ASK_CONTEXT_VERSION_V2 = "ask-context-v2"  # all sentences of all reports in the prompt (no retrieval)
TOP_K = 12
PER_REPORT = 2  # ask v2 retrieval: the top 2 sentences of every report are added to the global top TOP_K
MAX_TOKENS = 600
NOT_STATED = "The reports don't state this."
UNAVAILABLE = "Questions are temporarily unavailable (the daily usage limit was reached). Please try again later."

_RULES = """Rules:
- Use ONLY the numbered report sentences given below. Never add facts from general knowledge.
- Cite every sentence you rely on as {"report_no": <number>, "sentence_id": "<id>"}.
- If the sentences do not answer the question, return the refusal "The reports don't state this." and no answer.
- Hedged statements ("possible", "may represent", "cannot be excluded") are uncertain: say so; never state them as
  definite.
- Refuse, with a one-sentence refusal and no answer, any request for a diagnosis, treatment, medication or
  management advice (e.g. whether to start a drug), a prognosis, or anything not about what these reports say.
- "[REDACTED]" marks words removed for privacy; never guess them.
- Keep the answer to at most three short sentences, in plain language.
Return JSON with "answer" (string or null), "refusal" (string or null; exactly one of the two is non-null) and
"citations"."""

REPORT_SYSTEM = f"""You answer questions about one chest X-ray report for a research demo (not a medical device).
You get the report's sentences with their IDs (N = indication, C = comparison, F = findings, I = impression) and
the labels the labelling pipeline assigned, each with a verification state. The labels are hints; the sentences are
the evidence.
{_RULES}"""

ALL_SYSTEM = f"""You answer questions across several chest X-ray reports of one patient for a research demo (not a
medical device). You get the sentences retrieved for the question, each with its report number (reports are
numbered in upload order) and sentence ID (N = indication, C = comparison, F = findings, I = impression). Only these
sentences were retrieved; other sentences of the reports are not available to you.
{_RULES}"""

# ---- ask v2: the v1 rules with two fixes (a "not stated" reply goes in `refusal`, never in `answer`; a report that
# negates a finding is never listed or counted as having it)
_RULES_V2 = _RULES.replace(
    "- If the sentences do not answer the question, return the refusal "
    '"The reports don\'t state this." and no answer.',
    """- If the sentences do not answer the question, or the question asks for something these reports cannot state (the
  patient's age, other tests, vital signs), put exactly "The reports don't state this." in "refusal" and set
  "answer" to null. A reply that says something is not stated, not specified, not provided or not mentioned belongs in
  "refusal" in that exact wording, never in "answer".
- A sentence that negates a finding ("no pleural effusion", "no pneumothorax", "the effusion has resolved") does not
  describe that finding. Never list or count a report as having a finding because of a negating sentence; list and
  count only reports with a sentence that states the finding is present. If no report has the finding, say that none
  do and cite the negating sentences.""")
assert _RULES_V2 != _RULES

REPORT_SYSTEM_V2 = REPORT_SYSTEM.replace(_RULES, _RULES_V2)
ALL_SYSTEM_V2 = ALL_SYSTEM.replace(_RULES, _RULES_V2)
CONTEXT_SYSTEM_V2 = f"""You answer questions across several chest X-ray reports of one patient for a research demo (not
a medical device). You get ALL sentences of ALL the reports, each with its report number (reports are numbered in
upload order) and sentence ID (N = indication, C = comparison, F = findings, I = impression).
{_RULES_V2}"""

# version -> (report system, report prompt version, all system, all prompt version, per-report retrieval)
VERSIONS = {"v1": (REPORT_SYSTEM, ASK_REPORT_VERSION, ALL_SYSTEM, ASK_ALL_VERSION, 0),
            "v2": (REPORT_SYSTEM_V2, ASK_REPORT_VERSION_V2, ALL_SYSTEM_V2, ASK_ALL_VERSION_V2, PER_REPORT)}
DEFAULT_REPORT_VERSION = "v1"  # the website's choices (ask v2 decisions are recorded in docs/STATUS.md)
DEFAULT_ALL_VERSION = "v1"
CONTEXT_ABOVE: int | None = None  # scope "all": above this many reports in scope, put every sentence in the prompt

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": ["string", "null"]},
        "refusal": {"type": ["string", "null"]},
        "citations": {"type": "array", "items": {
            "type": "object", "properties": {"report_no": {"type": "integer"}, "sentence_id": {"type": "string"}},
            "required": ["report_no", "sentence_id"], "additionalProperties": False}},
    },
    "required": ["answer", "refusal", "citations"],
    "additionalProperties": False,
}


class Citation(BaseModel):
    report_no: int
    sentence_id: str


class AskResult(BaseModel):
    answer: str | None
    refusal: str | None
    citations: list[Citation]
    retrieved_sentences: int
    retrieved_reports: int


def _line(e: Entry) -> str:
    return f"[report {e.report_no}, {e.sentence_id}, {e.section}] {e.text}"


def check(text: str, given: list[Entry]) -> tuple[str | None, str | None, list[Citation]]:
    """Keep only citations of sentences that were given to the model; an answer without one is NOT_STATED."""
    try:
        d = json.loads(text)
        answer, refusal = d.get("answer"), d.get("refusal")
        cited = [Citation(**c) for c in d.get("citations", [])]
    except (json.JSONDecodeError, TypeError, ValueError):
        return None, NOT_STATED, []
    allowed = {(e.report_no, e.sentence_id) for e in given}
    seen: set[tuple[int, str]] = set()
    valid = [c for c in cited if (c.report_no, c.sentence_id) in allowed
             and not ((c.report_no, c.sentence_id) in seen or seen.add((c.report_no, c.sentence_id)))]  # type: ignore[func-returns-value]
    if answer and not refusal:
        return (answer, None, valid) if valid else (None, NOT_STATED, [])
    return None, refusal or NOT_STATED, valid


def _complete(llm: LLMClient, system: str, user: str, version: str) -> str:
    r = llm.complete([{"role": "system", "content": system}, {"role": "user", "content": user}], "tier1",
                     json_schema=SCHEMA, max_tokens=MAX_TOKENS, temperature=0.0, purpose=f"ask:{version}")
    return "" if r.filtered else r.text


def ask_report(llm: LLMClient, session: Session, report_no: int, question: str,
               version: str | None = None) -> AskResult:
    system, prompt_version = VERSIONS[version or DEFAULT_REPORT_VERSION][:2]
    rep = session.report(report_no)
    if rep is None:
        raise KeyError(report_no)
    given = [Entry(report_no, s.id, name, s.text) for name in ("indication", "comparison", "findings", "impression")
             for s in rep.sections[name]]
    labels = "\n".join(f"- {x.label}: {x.status} ({x.verification})" for x in rep.labels)
    user = (f"Report {report_no} sentences:\n" + "\n".join(_line(e) for e in given)
            + f"\n\nPipeline labels:\n{labels}\n\nQuestion: {question}")
    try:
        answer, refusal, cites = check(_complete(llm, system, user, prompt_version), given)
    except BudgetExceeded:
        answer, refusal, cites = None, UNAVAILABLE, []
    return AskResult(answer=answer, refusal=refusal, citations=cites, retrieved_sentences=len(given),
                     retrieved_reports=1)


class _State(TypedDict):
    question: str
    retrieved: list[Entry]
    raw: str
    result: AskResult | None


def ask_all(llm: LLMClient, session: Session, question: str, report_nos: list[int] | None = None,
            labels: list[str] | None = None, k: int = TOP_K, version: str | None = None) -> AskResult:
    system, prompt_version, per_report = VERSIONS[version or DEFAULT_ALL_VERSION][2:]

    def retrieve(st: _State) -> dict[str, Any]:
        return {"retrieved": session.retrieve(st["question"], k, report_nos, labels, per_report)}

    def answer(st: _State) -> dict[str, Any]:
        if not st["retrieved"]:
            return {"raw": ""}
        user = ("Retrieved sentences:\n" + "\n".join(_line(e) for e in st["retrieved"])
                + f"\n\nQuestion: {st['question']}")
        try:
            return {"raw": _complete(llm, system, user, prompt_version)}
        except BudgetExceeded:
            return {"raw": "", "result": AskResult(answer=None, refusal=UNAVAILABLE, citations=[],
                                                   retrieved_sentences=len(st["retrieved"]),
                                                   retrieved_reports=len({e.report_no for e in st["retrieved"]}))}

    def check_node(st: _State) -> dict[str, Any]:
        if st["result"] is not None:
            return {}
        a, r, c = check(st["raw"], st["retrieved"]) if st["raw"] else (None, NOT_STATED, [])
        return {"result": AskResult(answer=a, refusal=r, citations=c, retrieved_sentences=len(st["retrieved"]),
                                    retrieved_reports=len({e.report_no for e in st["retrieved"]}))}

    g: Any = StateGraph(_State)
    g.add_node("retrieve", retrieve)
    g.add_node("answer", answer)
    g.add_node("check", check_node)
    g.add_edge(START, "retrieve")
    g.add_edge("retrieve", "answer")
    g.add_edge("answer", "check")
    g.add_edge("check", END)
    out = g.compile().invoke({"question": question, "retrieved": [], "raw": "", "result": None})
    result: AskResult = out["result"]
    return result


def ask_context(llm: LLMClient, session: Session, question: str, report_nos: list[int] | None = None,
                labels: list[str] | None = None) -> AskResult:
    """Ask v2, long-context mode: every sentence in scope goes into the prompt (no retrieval); same rules, same
    citation check. Costs more per question as the session grows (SPEC §8.3)."""
    given = [session.entries[i] for i in session.select(report_nos, labels)]
    reports = len({e.report_no for e in given})
    if not given:
        return AskResult(answer=None, refusal=NOT_STATED, citations=[], retrieved_sentences=0, retrieved_reports=0)
    user = "All report sentences:\n" + "\n".join(_line(e) for e in given) + f"\n\nQuestion: {question}"
    try:
        a, r, c = check(_complete(llm, CONTEXT_SYSTEM_V2, user, ASK_CONTEXT_VERSION_V2), given)
    except BudgetExceeded:
        a, r, c = None, UNAVAILABLE, []
    return AskResult(answer=a, refusal=r, citations=c, retrieved_sentences=len(given), retrieved_reports=reports)


def ask_scope_all(llm: LLMClient, session: Session, question: str, report_nos: list[int] | None = None,
                  labels: list[str] | None = None) -> AskResult:
    """What the website runs for scope "all" (the ask v2 decision, docs/STATUS.md): session RAG, or every sentence in
    the prompt above CONTEXT_ABOVE reports in scope."""
    n = len({session.entries[i].report_no for i in session.select(report_nos, labels)})
    if CONTEXT_ABOVE is not None and n > CONTEXT_ABOVE:
        return ask_context(llm, session, question, report_nos, labels)
    return ask_all(llm, session, question, report_nos, labels)
