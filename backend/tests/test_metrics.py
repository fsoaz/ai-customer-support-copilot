"""Unit tests for Stage 0 retrieval metrics."""

from __future__ import annotations

from evals.harness.metrics import (
    aggregate_answerable,
    ndcg_at_k,
    rank_of,
    recall_at_k,
    reciprocal_rank,
)


def test_rank_of_and_miss() -> None:
    assert rank_of(["a", "b", "c"], "b") == 2
    assert rank_of(["a", "b"], "z") is None


def test_recall_at_k() -> None:
    ranked = ["x", "gold", "y"]
    assert recall_at_k(ranked, "gold", 1) == 0.0
    assert recall_at_k(ranked, "gold", 2) == 1.0
    assert recall_at_k(ranked, "missing", 10) == 0.0


def test_mrr() -> None:
    assert reciprocal_rank(["gold"], "gold") == 1.0
    assert reciprocal_rank(["a", "gold"], "gold") == 0.5
    assert reciprocal_rank(["a"], "gold") == 0.0


def test_ndcg_binary_single_relevant() -> None:
    import math

    assert ndcg_at_k(["gold"], "gold", 10) == 1.0
    assert abs(ndcg_at_k(["a", "gold"], "gold", 10) - (1.0 / math.log2(3))) < 1e-9
    assert ndcg_at_k(["a"] * 11 + ["gold"], "gold", 10) == 0.0


def test_aggregate_answerable() -> None:
    rows = [
        {"ranked_ids": ["g1", "x"], "gold_doc_id": "g1"},
        {"ranked_ids": ["x", "y", "g2"], "gold_doc_id": "g2"},
        {"ranked_ids": ["x"], "gold_doc_id": "miss"},
    ]
    s = aggregate_answerable(rows)
    assert s["n"] == 3
    assert abs(s["recall@1"] - 1 / 3) < 1e-9
    assert abs(s["recall@5"] - 2 / 3) < 1e-9
    assert abs(s["mrr"] - (1.0 + 1 / 3 + 0.0) / 3) < 1e-9
