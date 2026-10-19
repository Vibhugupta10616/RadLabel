"""Duplicate clusters: exact normalised text + near-duplicates by exact pairwise Jaccard >= 0.9.

Pairwise and deterministic (README §4.2); MinHash LSH missed true merges. O(n^2) over unique texts,
pruned by the size bound |A|/|B| >= threshold; under 3 s for ~3k texts.
"""

from __future__ import annotations

from radlabel.preprocess.text import norm_text


def _shingles(text: str, n: int = 3) -> set[str]:
    w = text.split()
    if len(w) < n:
        return {" ".join(w)}
    return {" ".join(w[i : i + n]) for i in range(len(w) - n + 1)}


def cluster(texts: dict[str, str], threshold: float = 0.9) -> dict[str, int]:
    """Map item id -> cluster id. Identical normalised texts always share a cluster; distinct texts are
    merged (transitively) when their word-3-shingle Jaccard is >= threshold."""
    by_norm: dict[str, list[str]] = {}
    for k, t in texts.items():
        by_norm.setdefault(norm_text(t), []).append(k)
    norms = sorted(by_norm)
    parent = list(range(len(norms)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    sh = [_shingles(n) for n in norms]
    order = sorted(range(len(sh)), key=lambda i: len(sh[i]))
    for a, i in enumerate(order):
        si = sh[i]
        for j in order[a + 1 :]:
            sj = sh[j]
            if len(si) < threshold * len(sj):  # sorted by size: no later j can reach the threshold
                break
            inter = len(si & sj)
            if inter >= threshold * (len(si) + len(sj) - inter):
                parent[find(i)] = find(j)

    roots: dict[int, int] = {}
    out = {}
    for i, n in enumerate(norms):
        cid = roots.setdefault(find(i), len(roots))
        for k in by_norm[n]:
            out[k] = cid
    return out
