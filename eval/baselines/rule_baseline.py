"""Rule baseline (README §6.2): alias match + pipeline negation, no LLM, no tuned parameters (decision D1).

Per label, over all sentences: an affirmed mention (asserted, not negated, not hedged) -> present, unless the
Impression explicitly contradicts it (section rule); else a hedged non-negated mention -> uncertain; else a
negated mention -> absent; else not_mentioned. No Finding is present iff no other label is present or uncertain.
Evidence = the sentence IDs of the deciding mentions.
"""

from __future__ import annotations

from radlabel.labelling.schema import LabelOut, ReportLabels
from radlabel.labelling.verifier import verify
from radlabel.labels import LABELS, NO_FINDING
from radlabel.preprocess.negation import Mention, mentions
from radlabel.preprocess.sentences import Sentence


def label_report(report_id: str, sentences: list[Sentence]) -> ReportLabels:
    ments: list[tuple[Sentence, Mention]] = [(s, m) for s in sentences for m in mentions(s.text)]
    out: list[LabelOut] = []
    for lab in LABELS:
        if lab == NO_FINDING:
            continue
        ms = [(s, m) for s, m in ments if m.label == lab]
        aff = [(s, m) for s, m in ms if m.affirmed]
        imp_aff = any(s.section == "impression" for s, _ in aff)
        imp_neg = any(s.section == "impression" and m.negated for s, m in ms)
        hed = [(s, m) for s, m in ms if m.hedged and not m.negated and m.asserted]
        neg = [(s, m) for s, m in ms if m.negated]
        if aff and (imp_aff or not imp_neg):
            status, ev = "present", aff
        elif aff:  # Findings affirm, Impression explicitly negates the same label: Impression wins
            status, ev = "absent", [(s, m) for s, m in neg if s.section == "impression"]
        elif hed:
            status, ev = "uncertain", hed
        elif neg:
            status, ev = "absent", neg
        else:
            status, ev = "not_mentioned", []
        out.append(LabelOut(label=lab, status=status, evidence=sorted({s.id for s, _ in ev})))  # type: ignore[arg-type]
    if any(x.status in ("present", "uncertain") for x in out):
        out.insert(0, LabelOut(label=NO_FINDING, status="not_mentioned"))
    else:
        nf_ev = sorted({s.id for s, m in ments if m.label == NO_FINDING})
        out.insert(0, LabelOut(label=NO_FINDING, status="present", evidence=nf_ev))
    return verify(ReportLabels(report_id=report_id, labels=out), sentences)
