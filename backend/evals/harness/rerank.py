"""Cross-encoder rerank via FlashRank (ONNX, no torch)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

DEFAULT_RERANK_MODEL = "ms-marco-TinyBERT-L-2-v2"


@dataclass(frozen=True)
class RerankHit:
    chunk_id: str
    score: float


class CrossEncoderReranker:
    """Score (query, passage) pairs and return chunk ids sorted by score desc."""

    def __init__(
        self,
        model_name: str = DEFAULT_RERANK_MODEL,
        *,
        max_length: int = 512,
        cache_dir: str | None = None,
    ) -> None:
        from flashrank import Ranker

        kwargs: dict = {"model_name": model_name, "max_length": max_length, "log_level": "ERROR"}
        if cache_dir is not None:
            kwargs["cache_dir"] = cache_dir
        self.model_name = model_name
        self._ranker = Ranker(**kwargs)

    def rerank(
        self,
        query: str,
        passages: Sequence[tuple[str, str]],
        *,
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """Rerank ``(chunk_id, text)`` passages; higher score is better."""
        from flashrank import RerankRequest

        if not passages:
            return []
        payload = [{"id": cid, "text": text[:2000]} for cid, text in passages]
        request = RerankRequest(query=query, passages=payload)
        ranked = self._ranker.rerank(request)
        hits = [RerankHit(chunk_id=str(row["id"]), score=float(row["score"])) for row in ranked]
        if top_n is not None:
            hits = hits[:top_n]
        return hits
