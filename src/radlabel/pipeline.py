"""The single entry point (README §5, invariant 2): `run_pipeline(raw_text)` is the only way labels are produced.

parse -> sentences ([REDACTED], IDs) -> Tier 1 tagger (Findings + Impression only; the indication is never an input)
-> deterministic verifier -> free checks (escalation, recall scan, normal check) -> verifier agent on escalated
reports only. `agent=False` stops before the agent (escalated labels end `unverified`, reason "agent not run").
Content-filtered or invalid tagger output -> the rule labeller's labels, all `unverified` (owner policy, M4).
Reads report text only: never codes from the dataset, folds, eval mentions or metrics
(tests/test_pipeline_leakage.py).
"""

from __future__ import annotations

from pydantic import BaseModel

from radlabel.labelling.extractor import extract
from radlabel.labelling.free_checks import Escalation, escalations
from radlabel.labelling.rules import label_report
from radlabel.labelling.schema import ReportLabels
from radlabel.labelling.verifier import verify
from radlabel.labelling.verifier_agent import AgentResult, FinalLabel, final_labels, run_agent
from radlabel.llm import BudgetExceeded, LLMClient
from radlabel.preprocess.parser import ParsedReport, parse_report
from radlabel.preprocess.sentences import Sentence, report_sentences


class PipelineResult(BaseModel):
    report_id: str
    sections_identified: bool  # False: no headers found, the whole text was read as Findings (incl. any indication)
    parse: ParsedReport
    sentences: list[Sentence]
    tagger: ReportLabels | None  # raw Tier 1 output; None if content-filtered or invalid
    labels: ReportLabels  # after the deterministic verifier (v1 "LLM + verifier"); rule labels on fallback
    final: list[FinalLabel]  # v2 output: status, evidence and verification state per label
    escalations: list[Escalation] = []
    agent_used: bool = False
    agent: AgentResult | None = None
    content_filtered: bool = False
    invalid_output: bool = False
    tagger_cost_usd: float = 0.0  # cost of the tagger call (kept on cache hits)


def run_pipeline(raw_text: str, llm: LLMClient | None = None, report_id: str = "upload",
                 agent: bool = True) -> PipelineResult:
    llm = llm or LLMClient()
    parsed = parse_report(raw_text)
    sents = report_sentences(parsed.findings, parsed.impression)
    out, resp = extract(llm, report_id, sents, temperature=0.0)
    rules = label_report(report_id, sents)
    common = {"report_id": report_id, "sections_identified": parsed.sections_identified, "parse": parsed,
              "sentences": sents, "tagger": out, "content_filtered": resp.filtered,
              "invalid_output": out is None and not resp.filtered, "tagger_cost_usd": resp.cost_usd}
    if out is None:
        why = "tagger output unavailable (content filter)" if resp.filtered else "tagger output invalid"
        return PipelineResult(**common, labels=rules, final=[
            FinalLabel(label=x.label, status=x.status, evidence=x.evidence, verification="unverified", reason=why)
            for x in rules.labels])
    labels = verify(out, sents)
    esc = escalations(labels, sents, rules)
    result: AgentResult | None = None
    reason = "agent not run"
    if esc and agent:
        try:
            result = run_agent(llm, report_id, sents, labels, esc, parsed.sections_identified)
        except BudgetExceeded:
            reason = "budget"
    return PipelineResult(**common, labels=labels, final=final_labels(labels, sents, esc, result, reason),
                          escalations=esc, agent_used=result is not None, agent=result)
