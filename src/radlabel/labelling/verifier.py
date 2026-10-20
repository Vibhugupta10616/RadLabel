"""Deterministic verifier (README §6.2). Every check has unit tests (tests/test_verifier.py).

| Check                   | Rule                                                                              |
| evidence_exists         | present/absent/uncertain cite >= 1 valid sentence ID                              |
| evidence_mentions_label | a cited sentence contains an alias of the label; [REDACTED] within 2 words of a   |
|                         | finding term -> flag, not fail                                                    |
| negation_consistency    | present, but every cited mention of the label is negated -> fail                  |
| hedge_consistency       | present, but the only cited evidence is hedged -> converted to uncertain + flag   |
| no_finding_exclusivity  | No Finding present => no other label present                                      |
| section_rule            | Impression overrides Findings only on an explicit same-label contradiction;       |
|                         | "no acute disease" never cancels specific Findings                                |
"""

from __future__ import annotations

from radlabel.labelling.schema import LabelOut, ReportLabels, VerifierMessage
from radlabel.labels import NO_FINDING
from radlabel.preprocess.negation import Mention, mentions, redaction_adjacent
from radlabel.preprocess.sentences import Sentence


def _msg(check: str, label: str, level: str, detail: str) -> VerifierMessage:
    return VerifierMessage(check=check, label=label, level=level, detail=detail)  # type: ignore[arg-type]


def verify(out: ReportLabels, sentences: list[Sentence]) -> ReportLabels:
    """Return a copy with hedge conversions applied and `verifier_messages` filled in."""
    by_id = {s.id: s for s in sentences}
    ments: dict[str, list[Mention]] = {s.id: mentions(s.text) for s in sentences}
    msgs: list[VerifierMessage] = []
    labels: list[LabelOut] = []

    for lo in out.labels:
        lo = lo.model_copy()
        lab = lo.label
        if lo.status != "not_mentioned":
            valid = [e for e in lo.evidence if e in by_id]
            if not valid or len(valid) != len(lo.evidence):
                bad = sorted(set(lo.evidence) - set(by_id))
                msgs.append(_msg("evidence_exists", lab, "fail",
                                 f"invalid sentence IDs {bad}" if bad else "no evidence cited"))
            cited = [m for e in valid for m in ments[e] if m.label == lab]
            if valid and not cited:
                if any(redaction_adjacent(by_id[e].text) for e in valid):
                    msgs.append(_msg("evidence_mentions_label", lab, "flag",
                                     "no alias in cited sentences; [REDACTED] next to a finding term"))
                else:
                    msgs.append(_msg("evidence_mentions_label", lab, "fail", "no alias in cited sentences"))
            if lo.status == "present" and lab != NO_FINDING and cited:
                if all(m.negated for m in cited):
                    msgs.append(_msg("negation_consistency", lab, "fail", "only negated mentions cited"))
                elif not any(m.affirmed for m in cited) and any(m.hedged and not m.negated for m in cited):
                    lo.status = "uncertain"
                    msgs.append(_msg("hedge_consistency", lab, "flag", "only hedged evidence: set to uncertain"))
        if lab != NO_FINDING:
            sec = section_rule(lab, lo.status, sentences, ments)
            if sec:
                msgs.append(_msg("section_rule", lab, "fail", sec))
        labels.append(lo)

    if any(x.label == NO_FINDING and x.status == "present" for x in labels):
        others = [x.label for x in labels if x.label != NO_FINDING and x.status == "present"]
        if others:
            msgs.append(_msg("no_finding_exclusivity", NO_FINDING, "fail", f"No Finding present with {others}"))

    return out.model_copy(update={"labels": labels, "verifier_messages": msgs})


def section_rule(label: str, status: str, sentences: list[Sentence], ments: dict[str, list[Mention]]) -> str | None:
    """Impression overrides Findings only on an explicit same-label contradiction (README §6.2)."""
    def sec(section: str) -> list[Mention]:
        return [m for s in sentences if s.section == section for m in ments[s.id] if m.label == label]

    f, i = sec("findings"), sec("impression")
    f_aff = any(m.affirmed for m in f)
    i_aff = any(m.affirmed for m in i)
    i_contradicts = any(m.negated for m in i) and not i_aff
    if status != "present" and (i_aff or (f_aff and not i_contradicts)):
        return "affirmed in the report and not explicitly contradicted by the Impression"
    if status == "present" and f_aff and not i_aff and i_contradicts:
        return "Impression explicitly contradicts the Findings for this label"
    return None


def passed(out: ReportLabels) -> bool:
    return not any(m.level == "fail" for m in out.verifier_messages)
