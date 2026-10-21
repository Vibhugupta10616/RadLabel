"""Sentence embeddings (optional extra "embed"): the base model until M9 (EMBED_BASE_MODEL), then the fine-tuned one.
Used by the verifier agent's find_by_meaning tool and by the index (README §6.3)."""

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
