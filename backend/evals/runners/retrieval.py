"""Stage 0 retrieval eval runner — recall@k, MRR, nDCG on the golden set.

Usage:
  uv run python -m evals.runners.retrieval
  uv run python -m evals.runners.retrieval --rerank
  uv run python -m evals.runners.retrieval --rerank --dense-top-k 100 --lexical-top-k 100
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from evals.harness.embed import Embedder
from evals.harness.ingest_meta import load_ingest_meta
from evals.harness.metrics import aggregate_answerable, rank_of
from evals.harness.paths import EVALS_ROOT, GOLDEN_PATH, STORE_DB_PATH
from evals.harness.rerank import DEFAULT_RERANK_MODEL, CrossEncoderReranker
from evals.harness.retrieve import HybridRetriever
from evals.harness.store import ChunkStore

REPORTS_DIR = EVALS_ROOT / "reports"
GATE_RECALL10 = 0.85
GATE_MRR = 0.60


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def run_retrieval_eval(
    *,
    db_path: Path = STORE_DB_PATH,
    golden_path: Path = GOLDEN_PATH,
    dense_top_k: int = 50,
    lexical_top_k: int = 50,
    rrf_k: int = 60,
    dense_weight: float = 1.0,
    lexical_weight: float = 1.0,
    query_prefix: str | None = None,
    rerank: bool = False,
    rerank_model: str = DEFAULT_RERANK_MODEL,
    rerank_candidates: int = 50,
    limit: int | None = None,
) -> dict:
    golden = load_golden(golden_path)
    if limit is not None:
        golden = golden[:limit]

    answerable = [r for r in golden if r.get("answerable")]
    unanswerable = [r for r in golden if not r.get("answerable")]

    started = time.perf_counter()
    reranker = CrossEncoderReranker(model_name=rerank_model) if rerank else None

    with ChunkStore(db_path) as store:
        ingest_meta = load_ingest_meta(db_path=db_path, store=store)
        model_name = ingest_meta.get("embedding_model", "BAAI/bge-small-en-v1.5")
        embedder = Embedder(model_name=model_name, query_prefix=query_prefix)
        retriever = HybridRetriever.from_store(
            store,
            dense_top_k=dense_top_k,
            lexical_top_k=lexical_top_k,
            rrf_k=rrf_k,
            dense_weight=dense_weight,
            lexical_weight=lexical_weight,
            reranker=reranker,
            rerank_candidates=rerank_candidates,
        )
        ingested = store.document_ids()

        missing = sorted(
            {
                r["gold_doc_id"]
                for r in answerable
                if r.get("gold_doc_id") and r["gold_doc_id"] not in ingested
            }
        )
        if missing:
            raise RuntimeError(
                f"{len(missing)} answerable gold_doc_ids missing from store (first: {missing[0]})"
            )

        all_rows = answerable + unanswerable
        # Apply query prefix (if any) before batch embed — documents stay unprefixed.
        questions = [embedder.format_query(r["question"]) for r in all_rows]
        q_matrix = embedder.embed_documents(questions, batch_size=64)

        answerable_detail: list[dict] = []
        unanswerable_detail: list[dict] = []

        for i, row in enumerate(all_rows):
            result = retriever.retrieve(row["question"], q_matrix[i])
            ranked_ids = [d for d, _s in result.ranked_docs]
            top1_score = result.ranked_docs[0][1] if result.ranked_docs else 0.0
            detail = {
                "id": row["id"],
                "answerable": bool(row.get("answerable")),
                "negative_slice": row.get("negative_slice"),
                "gold_doc_id": row.get("gold_doc_id") or "",
                "ranked_ids": ranked_ids,
                "top1_doc_id": ranked_ids[0] if ranked_ids else None,
                "top1_score": top1_score,
                "n_docs_retrieved": len(ranked_ids),
                "reranked": result.reranked,
            }
            if row.get("answerable"):
                detail["rank"] = rank_of(ranked_ids, row["gold_doc_id"])
                answerable_detail.append(detail)
            else:
                unanswerable_detail.append(detail)

    elapsed = time.perf_counter() - started
    answerable_metrics = aggregate_answerable(answerable_detail)

    un_scores = [d["top1_score"] for d in unanswerable_detail]
    ans_hit_scores = [d["top1_score"] for d in answerable_detail if d.get("rank") is not None]
    ans_miss_scores = [d["top1_score"] for d in answerable_detail if d.get("rank") is None]

    by_slice: dict[str, dict] = {}
    slices = {d.get("negative_slice") or "unknown" for d in unanswerable_detail}
    for slice_name in sorted(slices):
        subset = [
            d for d in unanswerable_detail if (d.get("negative_slice") or "unknown") == slice_name
        ]
        scores = [d["top1_score"] for d in subset]
        by_slice[slice_name] = {
            "n": len(subset),
            "mean_top1_score": statistics.fmean(scores) if scores else 0.0,
            "median_top1_score": statistics.median(scores) if scores else 0.0,
        }

    score_label = "cross_encoder" if rerank else "rrf"
    unanswerable_metrics = {
        "n": len(unanswerable_detail),
        "mean_top1_score": statistics.fmean(un_scores) if un_scores else 0.0,
        "median_top1_score": statistics.median(un_scores) if un_scores else 0.0,
        "score_kind": score_label,
        "by_slice": by_slice,
        "note": (
            "Scored separately from answerable recall/MRR. No refuse threshold applied yet; "
            "top1 scores reported for calibrating a confidence gate in later sweeps."
        ),
    }

    recall10 = answerable_metrics["recall@10"]
    mrr = answerable_metrics["mrr"]
    gate = {
        "recall@10": {
            "threshold": GATE_RECALL10,
            "measured": recall10,
            "pass": recall10 >= GATE_RECALL10,
        },
        "mrr": {
            "threshold": GATE_MRR,
            "measured": mrr,
            "pass": mrr >= GATE_MRR,
        },
        "stage0_pass": recall10 >= GATE_RECALL10 and mrr >= GATE_MRR,
    }

    report = {
        "task": "0.4" if rerank else "0.3",
        "runner": "evals.runners.retrieval",
        "created_at": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "dataset": str(golden_path),
        "config": {
            "embedding_model": model_name,
            "embedding_dim": ingest_meta.get("embedding_dim"),
            "chunk_tokens": ingest_meta.get("chunk_tokens"),
            "overlap_ratio": ingest_meta.get("overlap_ratio"),
            "tokenizer": ingest_meta.get("tokenizer"),
            "corpus_commit": ingest_meta.get("commit"),
            "query_prefix": query_prefix,
            "dense_top_k": dense_top_k,
            "lexical_top_k": lexical_top_k,
            "rrf_k": rrf_k,
            "dense_weight": dense_weight,
            "lexical_weight": lexical_weight,
            "rerank": (
                {
                    "enabled": True,
                    "model": rerank_model,
                    "candidates": rerank_candidates,
                }
                if rerank
                else None
            ),
            "store_docs": ingest_meta.get("document_count"),
            "store_chunks": ingest_meta.get("chunk_count"),
        },
        "answerable": answerable_metrics,
        "answerable_score_mass": {
            "mean_top1_score_hit": statistics.fmean(ans_hit_scores) if ans_hit_scores else 0.0,
            "mean_top1_score_miss": statistics.fmean(ans_miss_scores) if ans_miss_scores else 0.0,
            "n_hit": len(ans_hit_scores),
            "n_miss": len(ans_miss_scores),
            "score_kind": score_label,
        },
        "unanswerable": unanswerable_metrics,
        "gate": gate,
        "per_query_answerable": [
            {
                "id": d["id"],
                "gold_doc_id": d["gold_doc_id"],
                "rank": d["rank"],
                "top1_score": d["top1_score"],
                "top5": d["ranked_ids"][:5],
            }
            for d in answerable_detail
        ],
        "per_query_unanswerable": [
            {
                "id": d["id"],
                "negative_slice": d["negative_slice"],
                "top1_doc_id": d["top1_doc_id"],
                "top1_score": d["top1_score"],
                "n_docs_retrieved": d["n_docs_retrieved"],
            }
            for d in unanswerable_detail
        ],
    }
    return report


def write_report(
    report: dict,
    reports_dir: Path = REPORTS_DIR,
    *,
    tag: str | None = None,
) -> Path:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"_{tag}" if tag else ""
    path = reports_dir / f"retrieval{suffix}_{stamp}.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    latest = reports_dir / "retrieval_latest.json"
    latest.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if tag:
        tagged = reports_dir / f"retrieval_{tag}.json"
        tagged.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=STORE_DB_PATH)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--dense-top-k", type=int, default=50)
    parser.add_argument("--lexical-top-k", type=int, default=50)
    parser.add_argument("--rrf-k", type=int, default=60)
    parser.add_argument("--dense-weight", type=float, default=1.0)
    parser.add_argument("--lexical-weight", type=float, default=1.0)
    parser.add_argument(
        "--query-prefix",
        default=None,
        help="Optional BGE-style query instruction prefix (documents stay unprefixed)",
    )
    parser.add_argument(
        "--bge-query-prefix",
        action="store_true",
        help="Use DEFAULT_QUERY_PREFIX from evals.harness.embed",
    )
    parser.add_argument(
        "--rerank",
        action="store_true",
        help="Enable FlashRank cross-encoder rerank (off by default)",
    )
    parser.add_argument("--rerank-model", default=DEFAULT_RERANK_MODEL)
    parser.add_argument("--rerank-candidates", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None, help="Score only first N golden rows")
    parser.add_argument("--tag", default=None, help="Optional report tag (e.g. rerank_on)")
    parser.add_argument("--reports-dir", type=Path, default=REPORTS_DIR)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"store missing: {args.db}; run ingest_docs first", file=sys.stderr)
        return 1

    from evals.harness.embed import DEFAULT_QUERY_PREFIX

    query_prefix = args.query_prefix
    if args.bge_query_prefix:
        query_prefix = DEFAULT_QUERY_PREFIX

    try:
        report = run_retrieval_eval(
            db_path=args.db,
            golden_path=args.golden,
            dense_top_k=args.dense_top_k,
            lexical_top_k=args.lexical_top_k,
            rrf_k=args.rrf_k,
            dense_weight=args.dense_weight,
            lexical_weight=args.lexical_weight,
            query_prefix=query_prefix,
            rerank=args.rerank,
            rerank_model=args.rerank_model,
            rerank_candidates=args.rerank_candidates,
            limit=args.limit,
        )
    except (FileNotFoundError, RuntimeError, OSError, ValueError) as exc:
        print(f"retrieval eval failed: {exc}", file=sys.stderr)
        return 1

    tag = args.tag
    if tag is None and args.rerank:
        tag = "rerank_on"
    elif tag is None:
        tag = "rerank_off"

    path = write_report(report, args.reports_dir, tag=tag)
    a = report["answerable"]
    g = report["gate"]
    cfg = report["config"]
    print(
        f"config dense={cfg['dense_top_k']} lexical={cfg['lexical_top_k']} rerank={cfg['rerank']}"
    )
    print(
        f"answerable n={a['n']}  "
        f"recall@1={a['recall@1']:.4f}  recall@5={a['recall@5']:.4f}  "
        f"recall@10={a['recall@10']:.4f}  mrr={a['mrr']:.4f}  ndcg@10={a['ndcg@10']:.4f}"
    )
    u = report["unanswerable"]
    print(
        f"unanswerable n={u['n']}  mean_top1={u['mean_top1_score']:.4f}  (excluded from recall/MRR)"
    )
    print(
        f"gate: recall@10 {g['recall@10']['measured']:.4f}/"
        f"{g['recall@10']['threshold']} "
        f"{'PASS' if g['recall@10']['pass'] else 'FAIL'} · "
        f"mrr {g['mrr']['measured']:.4f}/{g['mrr']['threshold']} "
        f"{'PASS' if g['mrr']['pass'] else 'FAIL'} · "
        f"stage0={'PASS' if g['stage0_pass'] else 'FAIL'}"
    )
    print(f"report → {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
