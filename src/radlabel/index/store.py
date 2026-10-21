"""Qdrant collection (README §6.3): report points (dense + BM25 sparse) and contextual sentence points (dense).
Dense cosine, BM25 with Qdrant's IDF modifier (IDF over report points only, the only points with a sparse vector).
Sentence hits aggregate to reports by max score. RRF fuses report rankings (k = 60)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from qdrant_client import QdrantClient, models

from radlabel.index import bm25
from radlabel.index.points import IndexPoint

DENSE, SPARSE = "dense", "bm25"
RRF_K = 60


def create(client: QdrantClient, name: str, dim: int) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        name, vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams(modifier=models.Modifier.IDF)})
    for key in ("kind", "report_id"):
        client.create_payload_index(name, key, models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(name, "negation_only", models.PayloadSchemaType.BOOL)


def upsert(client: QdrantClient, name: str, points: Sequence[IndexPoint], dense: np.ndarray, batch: int = 256) -> None:
    """`dense`: one unit vector per point (same order). BM25 average length is computed over these report points."""
    avgdl = bm25.avg_doc_len([p.text for p in points if p.kind == "report"])
    out = []
    for p, v in zip(points, dense, strict=True):
        vec: dict[str, object] = {DENSE: v.tolist()}
        if p.kind == "report":
            idx, val = bm25.doc_vector(p.text, avgdl)
            vec[SPARSE] = models.SparseVector(indices=idx, values=val)
        out.append(models.PointStruct(id=p.id, vector=vec, payload=p.payload))
    for i in range(0, len(out), batch):
        client.upsert(name, out[i:i + batch], wait=True)


def _kind(kind: str, exclude_negation_only: bool = False) -> models.Filter:
    must: list[models.Condition] = [models.FieldCondition(key="kind", match=models.MatchValue(value=kind))]
    neg = models.FieldCondition(key="negation_only", match=models.MatchValue(value=True))
    must_not: list[models.Condition] = [neg] if exclude_negation_only else []
    return models.Filter(must=must, must_not=must_not)


def search_bm25(client: QdrantClient, name: str, text: str, k: int) -> list[tuple[str, float]]:
    idx, val = bm25.query_vector(text)
    if not idx:
        return []
    hits = client.query_points(name, query=models.SparseVector(indices=idx, values=val), using=SPARSE,
                               query_filter=_kind("report"), limit=k, with_payload=["report_id"]).points
    return [(h.payload["report_id"], h.score) for h in hits if h.payload]


def search_reports(client: QdrantClient, name: str, vec: np.ndarray, k: int) -> list[tuple[str, float]]:
    hits = client.query_points(name, query=vec.tolist(), using=DENSE, query_filter=_kind("report"), limit=k,
                               with_payload=["report_id"]).points
    return [(h.payload["report_id"], h.score) for h in hits if h.payload]


def search_sentences(client: QdrantClient, name: str, vec: np.ndarray, k: int, n_sentences: int = 200,
                     exclude_negation_only: bool = False) -> list[tuple[str, float]]:
    """Top sentence hits aggregated to reports by max score."""
    hits = client.query_points(name, query=vec.tolist(), using=DENSE,
                               query_filter=_kind("sentence", exclude_negation_only), limit=n_sentences,
                               with_payload=["report_id"]).points
    best: dict[str, float] = {}
    for h in hits:
        if h.payload:
            rid = h.payload["report_id"]
            best[rid] = max(best.get(rid, -1.0), h.score)
    return sorted(best.items(), key=lambda x: (-x[1], x[0]))[:k]


def rrf(*rankings: list[tuple[str, float]], k: int = RRF_K, top: int = 10) -> list[tuple[str, float]]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for rank, (rid, _) in enumerate(ranking, 1):
            score[rid] = score.get(rid, 0.0) + 1.0 / (k + rank)
    return sorted(score.items(), key=lambda x: (-x[1], x[0]))[:top]
