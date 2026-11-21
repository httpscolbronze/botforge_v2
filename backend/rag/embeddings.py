"""Embedding generation with a clearly-labelled local fallback.

Preferred path: `nomic-embed-text` through Ollama, so documents never leave the
machine. If that model is missing and BOTFORGE_EMBEDDING_FALLBACK is enabled we
fall back to a deterministic hashing embedding so retrieval still works. The
provider is reported to the UI so the degraded mode is never invisible.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Any

from backend.config import settings
from backend.engine.ollama_client import OllamaError, ollama
from backend.storage import repositories

logger = logging.getLogger("botforge.embeddings")

DIMENSION = 384
_TOKEN_RE = re.compile(r"[a-z0-9_]+")


class EmbeddingUnavailable(Exception):
    pass


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def local_embedding(text: str, dimension: int = DIMENSION) -> list[float]:
    """Hashing bag-of-words embedding (unigrams + bigrams), L2 normalised."""
    vector = [0.0] * dimension
    tokens = _tokens(text)
    if not tokens:
        return vector

    def add(token: str, weight: float) -> None:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "little") % dimension
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * weight

    for token in tokens:
        add(token, 1.0)
    for first, second in zip(tokens, tokens[1:]):
        add(f"{first}_{second}", 0.6)
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def current_embedding_model() -> str:
    """The host-selected embedding model, persisted in SQLite."""
    return repositories.selected_models()["embedding_model"]


async def embed_texts(texts: list[str], *, allow_fallback: bool | None = None) -> dict[str, Any]:
    """Embed texts; returns {"vectors", "provider", "model", "warning"}."""
    if not texts:
        return {"vectors": [], "provider": "none", "model": None, "warning": None}
    allow_fallback = settings.embedding_fallback if allow_fallback is None else allow_fallback
    model = current_embedding_model()

    try:
        vectors = await ollama.embed(texts, model)
        if vectors and all(vectors):
            return {
                "vectors": vectors,
                "provider": "ollama",
                "model": model,
                "warning": None,
            }
        raise OllamaError(f"Embedding model '{model}' returned empty vectors.")
    except OllamaError as exc:
        if not allow_fallback:
            raise EmbeddingUnavailable(
                f"{exc.message} Alternatively enable BOTFORGE_EMBEDDING_FALLBACK=true."
            ) from exc
        warning = (
            f"Embedding model '{model}' is unavailable; using the local "
            f"hashing fallback (lower retrieval quality). Ollama said: {exc.message}"
        )
        logger.warning(warning)
        return {
            "vectors": [local_embedding(text) for text in texts],
            "provider": "local-fallback",
            "model": "local-hashing-v1",
            "warning": warning,
        }


async def embed_query(text: str) -> dict[str, Any]:
    return await embed_texts([text])
