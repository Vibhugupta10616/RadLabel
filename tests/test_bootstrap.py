import numpy as np

from eval.bootstrap import bootstrap_ci, f1


def test_f1() -> None:
    t = np.array([1, 1, 0, 0], bool)
    assert f1(t, np.array([1, 0, 1, 0], bool)) == 0.5
    assert np.isnan(f1(np.zeros(3, bool), np.zeros(3, bool)))


def test_bootstrap_resamples_whole_clusters() -> None:
    clusters = [0, 0, 1, 1, 2, 3]
    seen = []

    def metric(idx: np.ndarray) -> float:
        s = set(idx.tolist())
        seen.append(s)
        return 1.0

    point, lo, hi = bootstrap_ci(metric, clusters, n=50)
    assert (point, lo, hi) == (1.0, 1.0, 1.0)
    for s in seen:  # members of a cluster always appear together
        assert ({0, 1} <= s or not s & {0, 1}) and ({2, 3} <= s or not s & {2, 3})


def test_bootstrap_ci_brackets_point() -> None:
    rng = np.random.default_rng(0)
    t = rng.random(300) < 0.3
    p = t ^ (rng.random(300) < 0.1)
    point, lo, hi = bootstrap_ci(lambda i: f1(t[i], p[i]), list(range(300)), n=300)
    assert lo < point < hi
