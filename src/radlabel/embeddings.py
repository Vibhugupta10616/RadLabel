"""Sentence embeddings (optional extra "embed"), the base model EMBED_BASE_MODEL. Used by the verifier agent's
find_by_meaning tool, which stays on the base model (the agent is frozen), and by the index (SPEC §6.3). The
fine-tuned model (M9) is for search and RAG only."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from radlabel.config import get_settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "  # bge retrieval instruction


@lru_cache
def _encoder() -> Any:
    from sentence_transformers import SentenceTransformer  # optional extra "embed"

    s = get_settings()
    return SentenceTransformer(s.embed_base_model, device=None if s.device == "auto" else s.device)


def encode(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Unit-normalised embeddings, one row per text (tests replace this function)."""
    return np.asarray(_encoder().encode(texts, normalize_embeddings=True, batch_size=batch_size))


@lru_cache
def load_encoder(path: str) -> Any:
    """A sentence-transformers model from a local directory (the private fine-tuned models, M9)."""
    from sentence_transformers import SentenceTransformer  # optional extra "embed"

    s = get_settings()
    return SentenceTransformer(path, device=None if s.device == "auto" else s.device)


def search_encode(texts: list[str], batch_size: int = 64) -> np.ndarray:
    """Search / RAG encoder: SEARCH_EMBED_MODEL (the fine-tuned serving model, M9) if set, else the base model. The
    verifier agent never uses this (it keeps the base model)."""
    path = get_settings().search_embed_model
    if not path:
        return encode(texts, batch_size)
    return np.asarray(load_encoder(path).encode(texts, normalize_embeddings=True, batch_size=batch_size))
