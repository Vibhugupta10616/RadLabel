"""Tier 0 (SPEC §6.2): exact normalised texts coded `normal` >= 3 times in the training data -> No Finding,
with no LLM call.

`learn` only sees normalised texts; the caller (eval/ or training/) picks the texts coded normal, so expert codes
never reach this module. The pattern set holds report text: it lives in MODEL_STORE / memory, never in git.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from radlabel.labelling.schema import LabelOut, ReportLabels, derive_no_finding
from radlabel.labels import LABELS, NO_FINDING
from radlabel.preprocess.text import norm_text

MIN_COUNT = 3


def key(findings: str, impression: str) -> str:
    """Same normalisation as exact-duplicate grouping (data_prep/build_dataset.py)."""
    return norm_text(findings + " " + impression)


def learn(normal_keys: Iterable[str], min_count: int = MIN_COUNT) -> frozenset[str]:
    """`normal_keys`: one key per training report coded normal (duplicates repeated)."""
    return frozenset(k for k, n in Counter(normal_keys).items() if n >= min_count)


def label(report_id: str, findings: str, impression: str, patterns: frozenset[str]) -> ReportLabels | None:
    if key(findings, impression) not in patterns:
        return None
    out = ReportLabels(report_id=report_id, tier=0,
                       labels=[LabelOut(label=lab, status="not_mentioned") for lab in LABELS if lab != NO_FINDING])
    return derive_no_finding(out)
