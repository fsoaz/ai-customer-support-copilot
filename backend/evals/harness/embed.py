"""Local embedding via fastembed (no paid API for Stage 0 sweeps)."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

# Small, fast ONNX model — record name+dim in ingest_meta for run comparability.
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
# BGE asymmetric query prefix (documents stay unprefixed at ingest).
DEFAULT_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        *,
        query_prefix: str | None = None,
    ) -> None:
        from fastembed import TextEmbedding

        self.model_name = model_name
        self.query_prefix = query_prefix
        self._model = TextEmbedding(model_name=model_name)
        # Probe dim once.
        probe = next(self._model.embed(["dimension probe"]))
        self.dim = int(np.asarray(probe, dtype=np.float32).shape[0])

    def embed_documents(self, texts: Sequence[str], *, batch_size: int = 64) -> np.ndarray:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        vectors = list(self._model.embed(list(texts), batch_size=batch_size))
        matrix = np.vstack([np.asarray(v, dtype=np.float32) for v in vectors])
        return _l2_normalize(matrix)

    def embed_query(self, text: str) -> np.ndarray:
        return self.embed_documents([self.format_query(text)])[0]

    def format_query(self, text: str) -> str:
        if not self.query_prefix:
            return text
        return f"{self.query_prefix}{text}"


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-12)
    return matrix / norms
