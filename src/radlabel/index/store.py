"""Qdrant collection (SPEC §6.3): report points (dense + BM25 sparse) and contextual sentence points (dense).
Dense cosine; BM25 sparse vectors carry the full BM25 weight (IDF computed in bm25.py over the indexed reports).
Sentence hits aggregate to reports by max score. RRF fuses report rankings (k = 60)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from qdrant_client import QdrantClient, models

from radlabel.index import bm25
from radlabel.index.points import IndexPoint

DENSE, SPARSE = "dense", "bm25"
RRF_K = 60
TIE_LIMIT = 20_000  # upper bound when fetching every point tied at the cut-off score
SCORE_DECIMALS, SCORE_EPS, SCORE_REL_MARGIN = 6, 1e-5, 1e-4  # candidate margin far above float32 sum noise


def create(client: QdrantClient, name: str, dim: int) -> None:
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        name, vectors_config={DENSE: models.VectorParams(size=dim, distance=models.Distance.COSINE)},
        sparse_vectors_config={SPARSE: models.SparseVectorParams()})
    for key in ("kind", "report_id"):
        client.create_payload_index(name, key, models.PayloadSchemaType.KEYWORD)
    client.create_payload_index(name, "negation_only", models.PayloadSchemaType.BOOL)


def upsert(client: QdrantClient, name: str, points: Sequence[IndexPoint], dense: np.ndarray, batch: int = 256) -> None:
    """`dense`: one unit vector per point (same order). BM25 statistics (IDF, average length) are computed over the
    report points passed here, so call it once with all of a collection's reports."""
    reports = [p.text for p in points if p.kind == "report"]
    avgdl, idfs = bm25.avg_doc_len(reports), bm25.idf(reports)
    out = []
    for p, v in zip(points, dense, strict=True):
        vec: dict[str, object] = {DENSE: v.tolist()}
        if p.kind == "report":
            idx, val = bm25.doc_vector(p.text, avgdl, idfs)
            vec[SPARSE] = models.SparseVector(indices=idx, values=val)
        out.append(models.PointStruct(id=p.id, vector=vec, payload=p.payload))
    for i in range(0, len(out), batch):
        client.upsert(name, out[i:i + batch], wait=True)


def _kind(kind: str, exclude_negation_only: bool = False) -> models.Filter:
    must: list[models.Condition] = [models.FieldCondition(key="kind", match=models.MatchValue(value=kind))]
    neg = models.FieldCondition(key="negation_only", match=models.MatchValue(value=True))
    must_not: list[models.Condition] = [neg] if exclude_negation_only else []
    return models.Filter(must=must, must_not=must_not)


def _top(client: QdrantClient, name: str, query: object, using: str, flt: models.Filter, k: int,
         sparse_query: set[int] | None = None) -> list[tuple[str, str, float]]:
    """Top k hits as (report_id, point id, score), deterministic across runs (found after M8):
    - every point within a small relative margin of the k-th score is fetched (Qdrant returns ties in no fixed order);
    - BM25 (`sparse_query` = the query's term ids): each candidate's score is recomputed here from its stored sparse
      vector, summed in index order, because the server's float32 sums can differ in the last digits between runs;
    - scores rounded to SCORE_DECIMALS, sorted by (score, report id, point id)."""
    def q(limit: int, threshold: float | None = None) -> list[models.ScoredPoint]:
        return client.query_points(  # type: ignore[arg-type]
            name, query=query, using=using, query_filter=flt, limit=limit, score_threshold=threshold,
            with_payload=["report_id"], with_vectors=[SPARSE] if sparse_query is not None else False).points
    hits = q(k)
    if len(hits) == k:
        s = hits[-1].score
        hits = q(TIE_LIMIT, s - abs(s) * SCORE_REL_MARGIN - SCORE_EPS)

    def score(h: models.ScoredPoint) -> float:
        if sparse_query is None:
            return h.score
        v = h.vector[SPARSE] if isinstance(h.vector, dict) else None
        if not isinstance(v, models.SparseVector):
            return h.score
        return float(sum(w for i, w in sorted(zip(v.indices, v.values, strict=True)) if i in sparse_query))
    out = sorted(((h.payload["report_id"], str(h.id), round(score(h), SCORE_DECIMALS)) for h in hits if h.payload),
                 key=lambda x: (-x[2], x[0], x[1]))
    return out[:k]


def search_bm25(client: QdrantClient, name: str, text: str, k: int) -> list[tuple[str, float]]:
    idx, val = bm25.query_vector(text)
    if not idx:
        return []
    return [(r, s) for r, _, s in _top(client, name, models.SparseVector(indices=idx, values=val), SPARSE,
                                       _kind("report"), k, sparse_query=set(idx))]


def search_reports(client: QdrantClient, name: str, vec: np.ndarray, k: int) -> list[tuple[str, float]]:
    return [(r, s) for r, _, s in _top(client, name, vec.tolist(), DENSE, _kind("report"), k)]


def search_sentences(client: QdrantClient, name: str, vec: np.ndarray, k: int, n_sentences: int = 200,
                     exclude_negation_only: bool = False) -> list[tuple[str, float]]:
    """Top sentence hits aggregated to reports by max score."""
    best: dict[str, float] = {}
    for rid, _, score in _top(client, name, vec.tolist(), DENSE, _kind("sentence", exclude_negation_only),
                              n_sentences):
        best[rid] = max(best.get(rid, -1.0), score)
    return sorted(best.items(), key=lambda x: (-x[1], x[0]))[:k]


def rrf(*rankings: list[tuple[str, float]], k: int = RRF_K, top: int = 10) -> list[tuple[str, float]]:
    score: dict[str, float] = {}
    for ranking in rankings:
        for rank, (rid, _) in enumerate(ranking, 1):
            score[rid] = score.get(rid, 0.0) + 1.0 / (k + rank)
    return sorted(score.items(), key=lambda x: (-x[1], x[0]))[:top]
