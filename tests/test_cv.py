"""Invariants (README §4.2): no cluster spans two folds; inner validation never overlaps its test fold."""

import json
from pathlib import Path

import pytest

from eval.cv import N_FOLDS, assign_folds, load_folds

ROOT = Path(__file__).resolve().parents[1]
HAVE_SPLIT = (ROOT / "data/splits/folds.csv").exists() and (ROOT / "data/processed/reports.jsonl").exists()


def test_assign_folds_synthetic() -> None:
    labels = {c: ({"Edema"} if c % 7 == 0 else set()) | ({"Cardiomegaly"} if c % 3 == 0 else {"No Finding"})
              for c in range(200)}
    fold, inner = assign_folds(labels, seed=13)
    assert set(fold) == set(labels) and set(fold.values()) == set(range(N_FOLDS))
    for k, val in inner.items():
        assert val and all(fold[c] != k for c in val)       # inner val drawn from training folds only
    edema = [sum(1 for c, f in fold.items() if f == k and "Edema" in labels[c]) for k in range(N_FOLDS)]
    assert max(edema) - min(edema) <= 2
    assert assign_folds(labels, seed=13) == (fold, inner)    # deterministic


@pytest.mark.skipif(not HAVE_SPLIT, reason="needs make data + make folds (data is private)")
def test_real_split_invariants() -> None:
    fold, inner = load_folds()
    reports = [json.loads(line) for line in (ROOT / "data/processed/reports.jsonl").open(encoding="utf-8")]
    by_group: dict[int, set[int]] = {}
    for r in reports:
        assert r["cluster"] in fold                          # every report has a fold via its cluster
        by_group.setdefault(r["group_rep"], set()).add(fold[r["cluster"]])
    assert all(len(f) == 1 for f in by_group.values())       # exact duplicates never split
    for k, val in inner.items():
        assert not any(fold[c] == k for c in val)            # tuning data never overlaps its test fold
