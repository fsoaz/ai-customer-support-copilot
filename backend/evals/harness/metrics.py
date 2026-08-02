"""Retrieval ranking metrics for Stage 0 golden-set evals."""

from __future__ import annotations

import math
from collections.abc import Sequence


def rank_of(ranked_ids: Sequence[str], gold_id: str) -> int | None:
    """1-based rank of ``gold_id``, or None if absent."""
    try:
        return list(ranked_ids).index(gold_id) + 1
    except ValueError:
        return None


def recall_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    r = rank_of(ranked_ids, gold_id)
    return 1.0 if r is not None and r <= k else 0.0


def reciprocal_rank(ranked_ids: Sequence[str], gold_id: str) -> float:
    r = rank_of(ranked_ids, gold_id)
    return 0.0 if r is None else 1.0 / r


def ndcg_at_k(ranked_ids: Sequence[str], gold_id: str, k: int) -> float:
    """Binary nDCG@k for a single relevant document."""
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    r = rank_of(ranked_ids, gold_id)
    if r is None or r > k:
        return 0.0
    # Ideal DCG for one relevant doc at rank 1 is 1/log2(2) = 1.
    dcg = 1.0 / math.log2(r + 1)
    return dcg  # / idcg(=1)


def mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def aggregate_answerable(
    per_query: Sequence[dict],
    *,
    ks: Sequence[int] = (1, 5, 10),
) -> dict:
    """Aggregate per-query answerable rows into summary metrics.

    Each row needs ``ranked_ids`` (list[str]) and ``gold_doc_id`` (str).
    """
    n = len(per_query)
    recalls = {f"recall@{k}": [] for k in ks}
    mrrs: list[float] = []
    ndcgs: list[float] = []
    ranks: list[int | None] = []

    for row in per_query:
        ranked = row["ranked_ids"]
        gold = row["gold_doc_id"]
        r = rank_of(ranked, gold)
        ranks.append(r)
        for k in ks:
            recalls[f"recall@{k}"].append(recall_at_k(ranked, gold, k))
        mrrs.append(reciprocal_rank(ranked, gold))
        ndcgs.append(ndcg_at_k(ranked, gold, 10))

    summary = {
        "n": n,
        "mrr": mean(mrrs),
        "ndcg@10": mean(ndcgs),
        "hit_at_any": mean([1.0 if r is not None else 0.0 for r in ranks]),
        "median_rank": _median_int([r for r in ranks if r is not None]),
    }
    for key, vals in recalls.items():
        summary[key] = mean(vals)
    return summary


def _median_int(vals: list[int]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    mid = len(s) // 2
    if len(s) % 2:
        return float(s[mid])
    return (s[mid - 1] + s[mid]) / 2.0
