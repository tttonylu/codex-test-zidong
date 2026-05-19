"""Local deterministic hash-based embedder for fully offline operation."""

from __future__ import annotations

import hashlib
from typing import Any, Optional

import numpy as np
from mem0.embeddings.base import EmbeddingBase, BaseEmbedderConfig

EMBEDDING_DIM = 1536


class LocalHashEmbedder(EmbeddingBase):
    """Deterministic hash-based embedder that works fully offline.

    Generates consistent pseudo-embedding vectors from text content
    using SHA-256 seeded numpy random normal distribution.

    This is *not* a semantic embedder — similar meaning without shared
    keywords will produce different vectors.  For production use,
    swap this out for a real embedding model (OpenAI, HuggingFace, etc.).
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None) -> None:
        super().__init__(config)
        self.config.embedding_dims = self.config.embedding_dims or EMBEDDING_DIM

    def embed(self, text: str, memory_action: Optional[str] = None) -> list[float]:
        dim = self.config.embedding_dims or EMBEDDING_DIM
        text = text.replace("\n", " ")
        h = hashlib.sha256(text.encode("utf-8")).digest()
        seed = int.from_bytes(h[:8], "little")
        rng = np.random.default_rng(seed)
        vec = rng.normal(0, 1.0 / dim**0.5, dim).astype(np.float32)
        return vec.tolist()

    def embed_batch(self, texts: list[str], memory_action: str = "add") -> list[list[float]]:
        return [self.embed(t, memory_action) for t in texts]


# ── register with mem0's factory ──────────────────────────────

from mem0.utils.factory import EmbedderFactory  # noqa: E402
from mem0.embeddings.configs import EmbedderConfig  # noqa: E402

# Register under a unique name; the config validation allow-list is
# patched at service.py init time via _patch_embedder_config().
EmbedderFactory.provider_to_class["local_hash"] = "shared.memory.embedder.LocalHashEmbedder"
