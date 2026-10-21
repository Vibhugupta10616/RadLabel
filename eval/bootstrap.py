"""95% bootstrap CIs resampled over clusters (SPEC §4.2): near-duplicates are resampled together."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np


def bootstrap_ci(
    metric: Callable[[np.ndarray], float],
    clusters: Sequence[int],
    n: int = 1000,
    seed: int = 13,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """`metric(idx)` scores the items at positions `idx` (repeats allowed). Returns (point, lo, hi)."""
    _, inv = np.unique(np.asarray(clusters), return_inverse=True)
    order = np.argsort(inv, kind="stable")
    members = np.split(order, np.flatnonzero(np.diff(inv[order])) + 1)
    rng = np.random.default_rng(seed)
    stats = [metric(np.concatenate([members[c] for c in rng.integers(0, len(members), len(members))]))
             for _ in range(n)]
    lo, hi = np.nanpercentile(stats, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return metric(np.arange(len(inv))), float(lo), float(hi)


def f1(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    """Binary (or pooled micro) F1 over boolean arrays; nan when there are no positives at all."""
    tp = np.sum(y_true & y_pred)
    denom = np.sum(y_true) + np.sum(y_pred)
    return float(2 * tp / denom) if denom else float("nan")
