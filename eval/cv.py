"""Stratified 5-fold CV over duplicate clusters + inner validation (SPEC §4.2).

- Items = duplicate clusters (3,073); a cluster's label vector is the union of the v1 expert labels of
  its exact-text representatives (the metrics unit), over all 13 labels.
- Iterative stratification: `iterstrat` MultilabelStratifiedKFold (the SPEC §4.2 fallback: scikit-multilearn
  0.2.0 can't take a seed with scikit-learn >= 1.x). Seed = SEED.
- Inner validation: per test fold k, a stratified 10% of fold k's training clusters (seed SEED + k).

Usage: python -m eval.cv
Writes data/splits/folds.csv (cluster,fold), data/splits/inner_val.csv (test_fold,cluster) (git-ignored)
and artifacts/results/folds.json (counts only).
"""

from __future__ import annotations

import collections
import csv
import json
from pathlib import Path

import numpy as np
from iterstrat.ml_stratifiers import MultilabelStratifiedKFold, MultilabelStratifiedShuffleSplit

from radlabel.config import get_settings
from radlabel.labels import LABELS
from radlabel.results import write_result

PROC = Path("data/processed")
SPLITS = Path("data/splits")
N_FOLDS = 5
INNER_FRACTION = 0.1
TOLERANCE = 2  # acceptance: per-label positives within ±2 of an equal share in every fold


def load_items() -> tuple[dict[int, int], dict[int, set[str]], dict[int, set[str]]]:
    """Exact-text representatives: rep id -> cluster, rep -> v1 labels, rep -> strict labels."""
    reports = [json.loads(line) for line in (PROC / "reports.jsonl").open(encoding="utf-8")]
    cluster = {r["id"]: r["cluster"] for r in reports if r["id"] == r["group_rep"]}
    v1, strict = {}, {}
    for e in map(json.loads, (PROC / "expert_labels.jsonl").open(encoding="utf-8")):
        if e["id"] in cluster:
            v1[e["id"]], strict[e["id"]] = set(e["v1"]), set(e["strict"])
    return cluster, v1, strict


def assign_folds(cluster_labels: dict[int, set[str]], seed: int) -> tuple[dict[int, int], dict[int, set[int]]]:
    """cluster -> test fold, and test fold -> inner-validation clusters (subset of that fold's training clusters)."""
    cids = sorted(cluster_labels)
    y = np.array([[lab in cluster_labels[c] for lab in LABELS] for c in cids], dtype=int)
    x = np.zeros((len(cids), 1))
    fold: dict[int, int] = {}
    inner: dict[int, set[int]] = {}
    for k, (train, test) in enumerate(MultilabelStratifiedKFold(N_FOLDS, shuffle=True, random_state=seed).split(x, y)):
        for i in test:
            fold[cids[i]] = k
        ss = MultilabelStratifiedShuffleSplit(n_splits=1, test_size=INNER_FRACTION, random_state=seed + k)
        _, val = next(ss.split(x[train], y[train]))
        inner[k] = {cids[train[i]] for i in val}
    return fold, inner


def load_folds() -> tuple[dict[int, int], dict[int, set[int]]]:
    """Saved split: cluster -> test fold, test fold -> inner-validation clusters."""
    with (SPLITS / "folds.csv").open(encoding="utf-8") as f:
        fold = {int(r["cluster"]): int(r["fold"]) for r in csv.DictReader(f)}
    inner: dict[int, set[int]] = collections.defaultdict(set)
    with (SPLITS / "inner_val.csv").open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            inner[int(r["test_fold"])].add(int(r["cluster"]))
    return fold, dict(inner)


def main() -> dict:
    seed = get_settings().seed
    cluster, v1, strict = load_items()
    cl_labels: dict[int, set[str]] = collections.defaultdict(set)
    for rid, c in cluster.items():
        cl_labels[c] |= v1[rid]
    fold, inner = assign_folds(dict(cl_labels), seed)

    SPLITS.mkdir(parents=True, exist_ok=True)
    with (SPLITS / "folds.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["cluster", "fold"])
        w.writerows(sorted(fold.items()))
    with (SPLITS / "inner_val.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test_fold", "cluster"])
        w.writerows((k, c) for k in sorted(inner) for c in sorted(inner[k]))

    def positives(ids: list[int], labels: dict[int, set[str]]) -> dict[str, int]:
        return {lab: sum(lab in labels[i] for i in ids) for lab in LABELS}

    reps_in = {k: [r for r, c in cluster.items() if fold[c] == k] for k in range(N_FOLDS)}
    total = positives(list(cluster), v1)
    per_fold = {k: positives(reps_in[k], v1) for k in range(N_FOLDS)}
    deviation = {lab: max(abs(per_fold[k][lab] - total[lab] / N_FOLDS) for k in range(N_FOLDS)) for lab in LABELS}
    inner_reps = {k: [r for r, c in cluster.items() if c in inner[k]] for k in range(N_FOLDS)}
    out = {
        "n_clusters": len(fold), "n_items_exact_texts": len(cluster), "seed": seed,
        "method": "iterstrat MultilabelStratifiedKFold over clusters (13 v1 labels); inner val 10% per fold",
        "folds": {k: {"clusters": sum(f == k for f in fold.values()), "exact_texts": len(reps_in[k]),
                      "positives_v1": per_fold[k], "positives_strict": positives(reps_in[k], strict)}
                  for k in range(N_FOLDS)},
        "inner_val": {k: {"clusters": len(inner[k]), "exact_texts": len(inner_reps[k]),
                          "positives_v1": positives(inner_reps[k], v1)} for k in range(N_FOLDS)},
        "total_positives_v1": total,
        "max_deviation_from_equal_share": {lab: round(d, 2) for lab, d in deviation.items()},
        "acceptance_within_pm2": all(d <= TOLERANCE for d in deviation.values()),
    }
    write_result("folds", out, fold=None)
    return out


if __name__ == "__main__":
    res = main()
    print(json.dumps({k: res[k] for k in ("n_clusters", "max_deviation_from_equal_share", "acceptance_within_pm2")},
                     indent=1))
