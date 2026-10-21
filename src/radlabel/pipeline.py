"""The single entry point (README §5, invariant 2): `run_pipeline(raw_text)` is the only way labels are produced.

M6: parse -> sentences ([REDACTED], IDs) -> Tier 1 tagger (Findings + Impression only; the indication is never an
input) -> deterministic verifier. M7 adds the free checks' escalation and the verifier agent.
Content-filtered or invalid tagger output -> the rule labeller's labels (owner policy, M4). Reads report text only:
never expert codes, folds, eval mentions or metrics (tests/test_pipeline_leakage.py).
"""

from __future__ import annotations

from pydantic import BaseModel

from radlabel.labelling.extractor import extract
from radlabel.labelling.rules import label_report
from radlabel.labelling.schema import ReportLabels
from radlabel.labelling.verifier import verify
from radlabel.llm import LLMClient
from radlabel.preprocess.parser import ParsedReport, parse_report
from radlabel.preprocess.sentences import Sentence, report_sentences


class PipelineResult(BaseModel):
    report_id: str
    parse: ParsedReport
    sentences: list[Sentence]
    tagger: ReportLabels | None  # raw Tier 1 output; None if content-filtered or invalid
    labels: ReportLabels  # final labels
    content_filtered: bool = False
    invalid_output: bool = False
    tagger_cost_usd: float = 0.0  # cost of the tagger call (kept on cache hits)


def run_pipeline(raw_text: str, llm: LLMClient | None = None, report_id: str = "upload") -> PipelineResult:
    parsed = parse_report(raw_text)
    sents = report_sentences(parsed.findings, parsed.impression)
    out, resp = extract(llm or LLMClient(), report_id, sents, temperature=0.0)
    labels = label_report(report_id, sents) if out is None else verify(out, sents)
    return PipelineResult(report_id=report_id, parse=parsed, sentences=sents, tagger=out, labels=labels,
                          content_filtered=resp.filtered, invalid_output=out is None and not resp.filtered,
                          tagger_cost_usd=resp.cost_usd)
