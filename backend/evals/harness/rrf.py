"""Reciprocal Rank Fusion and doc-level collapse for hybrid retrieval."""

from __future__ import annotations

from collections.abc import Sequence


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[str]],
    *,
    k: int = 60,
    weights: Sequence[float] | None = None,
) -> list[tuple[str, float]]:
    """Fuse ranked id lists with RRF. Higher score is better.

    ``k`` is the RRF constant (Cormack et al.; 60 is the common default).
    ``weights`` scales each list's contribution (default all 1.0).
    """
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    elif len(weights) != len(ranked_lists):
        raise ValueError(
            f"weights length {len(weights)} must match ranked_lists length {len(ranked_lists)}"
        )

    scores: dict[str, float] = {}
    for weight, ranked in zip(weights, ranked_lists, strict=True):
        w = float(weight)
        for rank, item_id in enumerate(ranked, start=1):
            scores[item_id] = scores.get(item_id, 0.0) + w / (k + rank)

    return sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))


def collapse_chunks_to_docs(
    chunk_ranked: Sequence[tuple[str, str, float]],
) -> list[tuple[str, float]]:
    """Collapse (chunk_id, gold_doc_id, score) → unique docs by best score.

    First occurrence of each ``gold_doc_id`` wins (assumes input is score-desc).
    """
    seen: set[str] = set()
    out: list[tuple[str, float]] = []
    for _chunk_id, gold_doc_id, score in chunk_ranked:
        if gold_doc_id in seen:
            continue
        seen.add(gold_doc_id)
        out.append((gold_doc_id, score))
    return out
