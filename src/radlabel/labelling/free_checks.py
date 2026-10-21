"""Free checks (README §6.2, M7): code only, no LLM, $0, every report. They decide which labels escalate to the
verifier agent, and why. Reads report sentences and pipeline outputs only.

Part 1, deterministic verifier (verifier.py), v2 actions: every FAIL escalates; of the flags, negation_consistency,
  hedge_consistency, section_rule and a [REDACTED] evidence flag on a present/uncertain label escalate. The other
  flags (absent without evidence, absent with generic evidence, Other Abnormality) are recorded only.
Part 2, recall scan: the rule labeller (rules.py) as a second reader; rules `present` while the tagger says
  `absent`/`not_mentioned` escalates that label.
Part 3, normal check: a predicted No Finding is a claim to confirm. It holds when normal statements cover the heart
  AND the lungs (specific statements only; a general "no acute disease" covers nothing) and the rule scan finds no
  present/uncertain label, Other Abnormality cues included. Pleura, mediastinum and bones are recorded when stated.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml
from pydantic import BaseModel

from radlabel.labelling.rules import label_report
from radlabel.labelling.schema import ReportLabels
from radlabel.labelling.verifier import NORMAL_PHRASES, normal_phrases
from radlabel.labels import NO_FINDING
from radlabel.preprocess.aliases import normalise
from radlabel.preprocess.negation import mentions
from radlabel.preprocess.sentences import Sentence
from radlabel.preprocess.text import REDACTED

ESCALATING_FLAGS = ("negation_consistency", "hedge_consistency", "section_rule")
# region -> (labels whose negated mention covers it, normal-phrase sources in normal_phrases.yaml (a top-level
# anchor such as lungs_clear, or a label's own list), extra regex). General phrases (no_acute_cp) cover no region.
REGIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...], str | None]] = {
    "heart": (("Cardiomegaly",), ("Cardiomegaly", "heart_normal"), None),
    "lungs": (("Lung Opacity", "Consolidation", "Edema"), ("lungs_clear",), None),
    "pleura": (("Pleural Effusion", "Pneumothorax", "Pleural Other"), ("pleura_clear",), None),
    "mediastinum": ((), (), r"mediastin\w*\b.*\b(normal|unremarkable|within normal limits)\b"
                            r"|\b(normal|unremarkable)\b.*\bmediastin"),
    "bones": (("Fracture",), ("Fracture",), None),
}
REQUIRED_REGIONS = ("heart", "lungs")


class Escalation(BaseModel):
    label: str
    reason: str  # a verifier check name, "recall_scan" or "normal_check"
    detail: str


class NormalCheck(BaseModel):
    ok: bool
    covered: dict[str, list[str]]  # region -> sentence IDs of the normal statements
    missing: list[str]  # required regions not covered
    abnormal: dict[str, list[str]]  # label -> sentence IDs, rule scan present/uncertain


@lru_cache
def _anchor_phrases() -> dict[str, list[str]]:
    d = yaml.safe_load(NORMAL_PHRASES.read_text(encoding="utf-8"))
    return {k: [normalise(p) for p in v] for k, v in d.items() if k != "labels"}


def normal_check(sentences: list[Sentence], rules: ReportLabels | None = None) -> NormalCheck:
    rules = rules or label_report("normal_check", sentences)
    covered: dict[str, list[str]] = {}
    for region, (labels, anchors, rx) in REGIONS.items():
        phrases = [p for a in anchors for p in _anchor_phrases().get(a) or normal_phrases()[a]]
        ids = [s.id for s in sentences
               if any(m.label in labels and m.negated for m in mentions(s.text))
               or any(p in normalise(s.text) for p in phrases)
               or (rx is not None and re.search(rx, s.text.lower()))]
        if ids:
            covered[region] = ids
    abnormal = {x.label: x.evidence for x in rules.labels
                if x.label != NO_FINDING and x.status in ("present", "uncertain")}
    missing = [r for r in REQUIRED_REGIONS if r not in covered]
    return NormalCheck(ok=not missing and not abnormal, covered=covered, missing=missing, abnormal=abnormal)


def escalations(verified: ReportLabels, sentences: list[Sentence],
                rules: ReportLabels | None = None) -> list[Escalation]:
    """Why (and for which labels) the report goes to the verifier agent; [] = every label stays `verified_rules`."""
    status = {x.label: x.status for x in verified.labels}
    out: list[Escalation] = []
    for m in verified.verifier_messages:
        if (m.level == "fail" or m.check in ESCALATING_FLAGS
                or (m.check == "evidence_mentions_label" and REDACTED in m.detail
                    and status.get(m.label) in ("present", "uncertain"))):
            out.append(Escalation(label=m.label, reason=m.check, detail=m.detail))
    rules = rules or label_report(verified.report_id, sentences)
    for x in rules.labels:
        if x.label != NO_FINDING and x.status == "present" and status.get(x.label) in ("absent", "not_mentioned"):
            out.append(Escalation(label=x.label, reason="recall_scan",
                                  detail=f"rules: present {x.evidence}; tagger: {status.get(x.label)}"))
    if status.get(NO_FINDING) == "present":
        nc = normal_check(sentences, rules)
        if not nc.ok:
            parts = ([f"no normal statement for {', '.join(nc.missing)}"] if nc.missing else []) + (
                [f"rule scan finds {sorted(nc.abnormal)}"] if nc.abnormal else [])
            out.append(Escalation(label=NO_FINDING, reason="normal_check", detail="; ".join(parts)))
    return out
