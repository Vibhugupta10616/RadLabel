"""Deterministic verifier (SPEC §6.2). Every check has unit tests (tests/test_verifier.py).

| Check                   | Rule                                                                              |
| evidence_exists         | present/absent/uncertain cite >= 1 valid sentence ID; invalid IDs fail; absent    |
|                         | with no evidence -> flag                                                          |
| evidence_mentions_label | present/uncertain: a cited sentence contains an alias of the label, else fail;    |
|                         | absent: alias OR a label-scoped normal phrase (normal_phrases.yaml), else flag;   |
|                         | Other Abnormality (open-ended) -> flag; a cited sentence with [REDACTED] -> flag  |
| negation_consistency    | present, but every cited mention of the label is negated -> flag (review; M4: the |
|                         | pipeline negation was wrong in 20/23 full-run fails, owner rule)                   |
| hedge_consistency       | present, but the only cited evidence is hedged -> converted to uncertain + flag;  |
|                         | wording the label's definition counts as present ("borderline" cardiomegaly) is   |
|                         | not a hedge for that label (M6 consistency fix, SPEC §6.2)                      |
| no_finding_exclusivity  | No Finding present => no other label present (No Finding is derived in code, see |
|                         | schema.derive_no_finding, so its own evidence is not checked)                     |
| section_rule            | Impression overrides Findings only on an explicit same-label contradiction;       |
|                         | "no acute disease" never cancels specific Findings. Disagreement -> FLAG (review) |
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from radlabel.labelling.schema import LabelOut, ReportLabels, VerifierMessage
from radlabel.labels import NO_FINDING, OTHER
from radlabel.preprocess.aliases import normalise
from radlabel.preprocess.negation import HEDGE, Mention, mentions, redaction_adjacent
from radlabel.preprocess.sentences import Sentence
from radlabel.preprocess.text import REDACTED

NORMAL_PHRASES = Path(__file__).with_name("normal_phrases.yaml")
# Wording that a label's definition counts as present (frozen Tier 1 prompt: Cardiomegaly "including mild or
# borderline-stated enlargement") is not a hedge for that label in hedge_consistency (M6, SPEC §6.2).
DEFINITION_PRESENT: dict[str, frozenset[str]] = {"Cardiomegaly": frozenset({"borderline", "mild"})}


@lru_cache
def normal_phrases() -> dict[str, list[str]]:
    d = yaml.safe_load(NORMAL_PHRASES.read_text(encoding="utf-8"))["labels"]

    def flat(x: object) -> list[str]:
        return [y for v in x for y in flat(v)] if isinstance(x, list) else [str(x)]
    return {lab: [normalise(p) for p in flat(v)] for lab, v in d.items()}


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
        if lo.status != "not_mentioned" and lab != NO_FINDING:  # No Finding is derived, not claimed
            valid = [e for e in lo.evidence if e in by_id]
            bad = sorted(set(lo.evidence) - set(by_id))
            if bad:
                msgs.append(_msg("evidence_exists", lab, "fail", f"invalid sentence IDs {bad}"))
            elif not valid:  # (A) absent with no evidence = implied absence -> flag; present/uncertain -> fail
                msgs.append(_msg("evidence_exists", lab, "flag" if lo.status == "absent" else "fail",
                                 "no evidence cited"))
            cited = [m for e in valid for m in ments[e] if m.label == lab]
            if valid and not cited:
                normal = normal_phrases().get(lab, [])
                if lo.status == "absent" and any(p in normalise(by_id[e].text) for e in valid for p in normal):
                    pass  # absence supported by a label-scoped normal statement ("clear lungs")
                elif lab == OTHER:  # (B) open-ended label: no alias list can be complete
                    msgs.append(_msg("evidence_mentions_label", lab, "flag", "no alias cited (open-ended label)"))
                elif any(REDACTED in by_id[e].text for e in valid) or any(
                        redaction_adjacent(by_id[e].text) for e in valid):  # (D) the label word may be redacted
                    msgs.append(_msg("evidence_mentions_label", lab, "flag",
                                     "no alias in cited sentences; cited sentence contains [REDACTED]"))
                elif lo.status == "absent":
                    msgs.append(_msg("evidence_mentions_label", lab, "flag",
                                     "absent: cited sentences neither name the label nor state a normal finding"))
                else:
                    msgs.append(_msg("evidence_mentions_label", lab, "fail", "no alias in cited sentences"))
            if lo.status == "present" and cited:
                exempt = DEFINITION_PRESENT.get(lab, frozenset())
                hedged = [not set(m.hedge_cues) <= exempt for m in cited]
                if all(m.negated for m in cited):
                    msgs.append(_msg("negation_consistency", lab, "flag", "only negated mentions cited"))
                elif (not any(m.asserted and not m.negated and not h for m, h in zip(cited, hedged, strict=True))
                      and any(h and not m.negated for m, h in zip(cited, hedged, strict=True))):
                    lo.status = "uncertain"
                    msgs.append(_msg("hedge_consistency", lab, "flag", "only hedged evidence: set to uncertain"))
        if lab != NO_FINDING:
            sec = section_rule(lab, lo.status, sentences, ments)
            if sec:
                # (C) flag -> review, not repair: on the pilot the LLM was right in 26/39 disagreements (owner rule)
                msgs.append(_msg("section_rule", lab, "flag", sec))
        labels.append(lo)

    if any(x.label == NO_FINDING and x.status == "present" for x in labels):
        others = [x.label for x in labels if x.label != NO_FINDING and x.status == "present"]
        if others:
            msgs.append(_msg("no_finding_exclusivity", NO_FINDING, "fail", f"No Finding present with {others}"))

    return out.model_copy(update={"labels": labels, "verifier_messages": msgs})


def definition_present(label: str, evidence: list[str], sentences: list[Sentence]) -> bool:
    """Final consistency rule (owner, M10b; found on the hand-written sample, not on test results). An `uncertain`
    label is `present` if its cited sentences hold a word the label's definition counts as present ("borderline",
    "mild") and no other hedge cue, and at least one cited mention of the label is not negated. Any other hedge cue
    anywhere in the cited sentences ("possible mild cardiomegaly") keeps it uncertain."""
    exempt = DEFINITION_PRESENT.get(label, frozenset())
    by_id = {s.id: s for s in sentences}
    cited = [by_id[e] for e in evidence if e in by_id]
    toks = [normalise(s.text).split() for s in cited]
    cues = {c for t in toks for c in HEDGE if any(t[i:i + len(c.split())] == c.split() for i in range(len(t)))}
    word = any(w in (x, x.removesuffix("ly")) for t in toks for x in t for w in exempt)
    return bool(word and cues <= exempt
                and any(not m.negated for s in cited for m in mentions(s.text) if m.label == label))


def section_rule(label: str, status: str, sentences: list[Sentence], ments: dict[str, list[Mention]]) -> str | None:
    """Impression overrides Findings only on an explicit same-label contradiction (SPEC §6.2)."""
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
