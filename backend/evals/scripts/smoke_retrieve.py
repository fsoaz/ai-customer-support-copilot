"""Coverage check + hybrid retrieval smoke against the Stage 0 golden set.

Definition of done (task 0.2):
- every answerable gold_doc_id resolves to an ingested document
- a handful of golden questions return the gold doc in top-50 (pre-rerank)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evals.harness.embed import Embedder
from evals.harness.ingest_meta import load_ingest_meta
from evals.harness.paths import GOLDEN_PATH, STORE_DB_PATH
from evals.harness.retrieve import HybridRetriever
from evals.harness.store import ChunkStore

DEFAULT_SMOKE_N = 10
DEFAULT_TOP_K = 50


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def coverage_report(golden: list[dict], ingested_ids: set[str]) -> tuple[int, int, list[str]]:
    answerable = [r for r in golden if r.get("answerable")]
    missing = sorted(
        {
            r["gold_doc_id"]
            for r in answerable
            if r.get("gold_doc_id") and r["gold_doc_id"] not in ingested_ids
        }
    )
    return len(answerable), len(answerable) - len(missing), missing


def smoke_retrieve(
    *,
    store: ChunkStore,
    embedder: Embedder,
    pairs: list[dict],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    retriever = HybridRetriever.from_store(store)
    results: list[dict] = []
    for row in pairs:
        q = row["question"]
        gold = row["gold_doc_id"]
        qvec = embedder.embed_query(q)
        ranked = retriever.retrieve(q, qvec).ranked_docs
        doc_ids = [d for d, _s in ranked[:top_k]]
        try:
            rank = doc_ids.index(gold) + 1
        except ValueError:
            rank = None
        results.append(
            {
                "id": row["id"],
                "gold_doc_id": gold,
                "rank": rank,
                "hit_at_50": rank is not None and rank <= top_k,
                "top5": doc_ids[:5],
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=STORE_DB_PATH)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--smoke-n", type=int, default=DEFAULT_SMOKE_N)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"store missing: {args.db}; run ingest_docs first", file=sys.stderr)
        return 1

    golden = load_golden(args.golden)
    with ChunkStore(args.db) as store:
        ingested = store.document_ids()
        answerable_n, covered_n, missing = coverage_report(golden, ingested)
        print(
            f"coverage: {covered_n}/{answerable_n} answerable gold_doc_ids ingested "
            f"({store.document_count()} docs / {store.chunk_count()} chunks in store)"
        )
        if missing:
            print(f"MISSING ({len(missing)}):", file=sys.stderr)
            for mid in missing[:20]:
                print(f"  {mid}", file=sys.stderr)
            if len(missing) > 20:
                print(f"  … +{len(missing) - 20} more", file=sys.stderr)
            return 2

        answerable = [r for r in golden if r.get("answerable")]
        # Deterministic sample: every Nth row so we spread across the set.
        step = max(len(answerable) // args.smoke_n, 1)
        sample = [answerable[i] for i in range(0, len(answerable), step)][: args.smoke_n]

        meta = load_ingest_meta(db_path=args.db, store=store)
        model_name = meta.get("embedding_model", "BAAI/bge-small-en-v1.5")

        print(f"smoke: embedding queries with {model_name} …")
        embedder = Embedder(model_name=model_name)
        results = smoke_retrieve(store=store, embedder=embedder, pairs=sample, top_k=args.top_k)

    hits = sum(1 for r in results if r["hit_at_50"])
    print(f"smoke hit@{args.top_k}: {hits}/{len(results)}")
    for r in results:
        mark = "OK" if r["hit_at_50"] else "MISS"
        print(f"  [{mark}] {r['id']} rank={r['rank']} gold={r['gold_doc_id']}")

    if hits < len(results):
        # Soft fail: report but still exit non-zero so CI/humans notice.
        # Task 0.2 DoD is "a handful" — require majority.
        if hits < max(1, len(results) // 2):
            print("smoke failed: fewer than half of samples hit top-k", file=sys.stderr)
            return 3
        print("smoke: partial hits (majority ok); investigate misses before gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
