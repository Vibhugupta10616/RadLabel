"""Training pairs for negation-aware embedding fine-tuning (SPEC §6.3, M9).

Per fold k (`build(k)`):
- Training reports: exact-text representatives whose cluster is NOT in fold k and NOT in fold k's inner-validation
  clusters; the inner-validation reports are returned separately for epoch selection. Fold k is never read.
- Queries: the label name and the non-held-out, non-anchor pipeline aliases of each training label. The held-out
  labels (Fracture, Lung Lesion, Pleural Other) and held-out aliases are never used.
- Positive: a plain sentence (no prefix) that clearly states the finding (an affirmed pipeline mention:
  radlabel.preprocess.negation) in a report whose v1 expert code is positive.
- Hard negative, alternating: a sentence that mentions the finding only negated ("no pleural effusion"), or the
  sentence most similar in wording (token Jaccard) that clearly states a DIFFERENT training finding.
- The eval-only detector (negspacy, eval/lexicon.yaml) is never used here: it stays independent of training.
Report -> report pairs (optional in the spec) are not built.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path

from eval.cv import load_folds
from radlabel.labels import FINDING_LABELS
from radlabel.preprocess.aliases import aliases, normalise
from radlabel.preprocess.negation import mentions

PROC = Path("data/processed")
HELDOUT_LABELS = ("Fracture", "Lung Lesion", "Pleural Other")  # = eval/queries/retrieval_v1.yaml (test)
TRAIN_LABELS = [lab for lab in FINDING_LABELS if lab not in HELDOUT_LABELS]
MAX_POS_PER_QUERY = 64  # distinct positive sentences per query (seeded sample)
JACCARD_POOL = 300  # candidates scanned for the similar-wording negative


@dataclass
class Report:
    id: int
    cluster: int
    sentences: list[str]
    labels: set[str] = field(default_factory=set)  # v1 expert labels (training side only)


@dataclass
class Fold:
    k: int
    triplets: list[tuple[str, str, str]]  # (query, positive, hard negative)
    sources: set[int]  # report ids that contributed a positive or a negative
    inner: list[Report]  # inner validation: epoch selection only
    train_ids: set[int]


def queries() -> dict[str, list[str]]:
    # an alias text held out for ANY label is never a training query (the same words can serve two labels)
    held = {normalise(a.text.replace("_", " ")) for als in aliases().values() for a in als if a.heldout}
    out: dict[str, list[str]] = {}
    for lab in TRAIN_LABELS:
        qs = [lab.lower()] + [a.text.replace("_", " ").strip() for a in aliases()[lab]
                              if not a.heldout and not a.anchor and len(a.text.strip("_ ")) >= 3
                              and normalise(a.text.replace("_", " ")) not in held]
        seen: set[str] = set()
        out[lab] = [q for q in qs if not (normalise(q) in seen or seen.add(normalise(q)))]  # type: ignore[func-returns-value]
    return out


def load_reports() -> list[Report]:
    exp = {e["id"]: set(e["v1"]) for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8"))}
    return [Report(r["id"], r["cluster"], [s["text"] for s in r["sentences"]], exp[r["id"]])
            for r in map(json.loads, (PROC / "reports.jsonl").open(encoding="utf-8")) if r["id"] == r["group_rep"]]


def _tokens(text: str) -> set[str]:
    return set(normalise(text).split())


def triplets(train: list[Report], seed: int) -> tuple[list[tuple[str, str, str]], set[int]]:
    rng = random.Random(seed)
    pos: dict[str, dict[str, int]] = {lab: {} for lab in TRAIN_LABELS}  # label -> text -> report id
    neg: dict[str, dict[str, int]] = {lab: {} for lab in TRAIN_LABELS}
    for r in sorted(train, key=lambda x: x.id):
        for s in r.sentences:
            ms = mentions(s)
            for lab in TRAIN_LABELS:
                lm = [m for m in ms if m.label == lab]
                if any(m.affirmed for m in lm) and lab in r.labels:
                    pos[lab].setdefault(s, r.id)
                elif lm and all(m.negated for m in lm):
                    neg[lab].setdefault(s, r.id)
    out: list[tuple[str, str, str]] = []
    used: set[int] = set()
    for lab, qs in queries().items():
        others = sorted({t: i for o in TRAIN_LABELS if o != lab
                         for t, i in pos[o].items() if t not in pos[lab]}.items())
        negs = sorted(neg[lab].items())
        texts = sorted(pos[lab])
        for q in qs:
            sample = rng.sample(texts, min(MAX_POS_PER_QUERY, len(texts)))
            for n, p in enumerate(sample):
                if n % 2 == 0 and negs:
                    t, i = negs[rng.randrange(len(negs))]
                elif others:
                    pool = [others[rng.randrange(len(others))] for _ in range(min(JACCARD_POOL, len(others)))]
                    tp = _tokens(p)
                    t, i = max(pool, key=lambda x: (len(tp & _tokens(x[0])) / max(1, len(tp | _tokens(x[0]))), x[0]))
                else:
                    continue
                out.append((q, p, t))
                used |= {pos[lab][p], i}
    return out, used


def build(k: int, reports: list[Report] | None = None, seed: int = 13) -> Fold:
    reports = reports if reports is not None else load_reports()
    fold, inner = load_folds()
    train = [r for r in reports if fold[r.cluster] != k and r.cluster not in inner[k]]
    val = [r for r in reports if fold[r.cluster] != k and r.cluster in inner[k]]
    trips, used = triplets(train, seed + k)
    return Fold(k, trips, used, val, {r.id for r in train})


def build_all(reports: list[Report], seed: int = 13) -> tuple[list[tuple[str, str, str]], set[int]]:
    """Serving model (after evaluation): every report is a training report."""
    return triplets(reports, seed)
