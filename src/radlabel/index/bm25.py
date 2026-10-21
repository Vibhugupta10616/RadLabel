"""BM25 as Qdrant sparse vectors (README §6.3): document weights tf * (k1 + 1) / (tf + k1 * (1 - b + b * dl / avgdl)),
the IDF factor applied by Qdrant (sparse vector modifier IDF), query weights 1 per distinct term."""

from __future__ import annotations

import zlib
from collections import Counter

from radlabel.preprocess.aliases import normalise

K1, B = 1.2, 0.75


def tokens(text: str) -> list[str]:
    return normalise(text).split()


def term_id(term: str) -> int:
    return zlib.crc32(term.encode())  # ponytail: stable 32-bit hash ids; collisions are negligible at this vocabulary


def doc_vector(text: str, avgdl: float) -> tuple[list[int], list[float]]:
    tf = Counter(term_id(t) for t in tokens(text))
    dl = sum(tf.values())
    items = sorted((i, n * (K1 + 1) / (n + K1 * (1 - B + B * dl / avgdl))) for i, n in tf.items())
    return [i for i, _ in items], [w for _, w in items]


def query_vector(text: str) -> tuple[list[int], list[float]]:
    ids = sorted({term_id(t) for t in tokens(text)})
    return ids, [1.0] * len(ids)


def avg_doc_len(texts: list[str]) -> float:
    return sum(len(tokens(t)) for t in texts) / max(1, len(texts))
