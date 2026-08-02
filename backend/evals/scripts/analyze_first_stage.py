"""Diagnose first-stage misses on a harness store (Task 0.6).

Reports dense-only / lexical-only / fused coverage and a pool-size ceiling curve
so we can tell whether the Stage 0 gap is candidate generation vs ranking vs labels.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from evals.harness.embed import Embedder
from evals.harness.ingest_meta import load_ingest_meta
from evals.harness.metrics import recall_at_k
from evals.harness.paths import GOLDEN_PATH, STORE_DB_PATH
from evals.harness.retrieve import HybridRetriever
from evals.harness.rrf import collapse_chunks_to_docs, reciprocal_rank_fusion
from evals.harness.store import ChunkStore

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.I)


def load_golden(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _doc_ids_from_chunks(retriever: HybridRetriever, chunk_ids: list[str]) -> list[str]:
    ranked = [
        (cid, retriever._id_to_doc[cid], float(len(chunk_ids) - i))
        for i, cid in enumerate(chunk_ids)
    ]
    return [d for d, _s in collapse_chunks_to_docs(ranked)]


def _overlap(question: str, gold_text: str) -> float:
    q = set(_TOKEN_RE.findall(question.lower()))
    g = set(_TOKEN_RE.findall(gold_text.lower()))
    if not q or not g:
        return 0.0
    return len(q & g) / len(q)


def analyze(
    *,
    db_path: Path,
    golden_path: Path,
    pool_ks: list[int],
    sample_misses: int,
    seed: int,
) -> dict:
    golden = [r for r in load_golden(golden_path) if r.get("answerable")]
    with ChunkStore(db_path) as store:
        meta = load_ingest_meta(db_path=db_path, store=store)
        model_name = meta.get("embedding_model", "BAAI/bge-small-en-v1.5")
        embedder = Embedder(model_name=model_name)
        # Use max pool so one pass covers the ceiling curve.
        max_k = max(pool_ks)
        retriever = HybridRetriever.from_store(
            store,
            dense_top_k=max_k,
            lexical_top_k=max_k,
        )
        questions = [r["question"] for r in golden]
        q_matrix = embedder.embed_documents(questions, batch_size=64)

        # Preload gold texts for overlap heuristic (all chunks of gold doc).
        gold_texts = {gid: store.document_text(gid) for gid in store.document_ids()}
        titles = store.document_titles()

        per_k: dict[str, dict] = {}
        channel = {
            "dense_only": 0,
            "lexical_only": 0,
            "both": 0,
            "neither": 0,
        }
        miss_rows: list[dict] = []

        for i, row in enumerate(golden):
            gold = row["gold_doc_id"]
            dense_chunks = retriever.dense_search(q_matrix[i], top_k=max_k)
            lexical_chunks = retriever.lexical_search(row["question"], top_k=max_k)
            dense_docs = _doc_ids_from_chunks(retriever, dense_chunks)
            lexical_docs = _doc_ids_from_chunks(retriever, lexical_chunks)
            in_dense = gold in dense_docs
            in_lex = gold in lexical_docs
            if in_dense and in_lex:
                channel["both"] += 1
            elif in_dense:
                channel["dense_only"] += 1
            elif in_lex:
                channel["lexical_only"] += 1
            else:
                channel["neither"] += 1

            fused = reciprocal_rank_fusion([dense_chunks, lexical_chunks], k=60)
            chunk_ranked = [
                (cid, retriever._id_to_doc[cid], score)
                for cid, score in fused
                if cid in retriever._id_to_doc
            ]
            fused_docs = [d for d, _s in collapse_chunks_to_docs(chunk_ranked)]

            for k in pool_ks:
                bucket = per_k.setdefault(
                    str(k),
                    {"dense_hit": 0, "lexical_hit": 0, "fused_hit": 0, "recall@10": 0},
                )
                if gold in dense_docs[:k]:
                    bucket["dense_hit"] += 1
                if gold in lexical_docs[:k]:
                    bucket["lexical_hit"] += 1
                if gold in fused_docs[:k]:
                    bucket["fused_hit"] += 1
                d_k = dense_chunks[:k]
                l_k = lexical_chunks[:k]
                fused_k = reciprocal_rank_fusion([d_k, l_k], k=60)
                ranked_k = collapse_chunks_to_docs(
                    [
                        (cid, retriever._id_to_doc[cid], score)
                        for cid, score in fused_k
                        if cid in retriever._id_to_doc
                    ]
                )
                ranked_ids = [d for d, _s in ranked_k]
                bucket["recall@10"] += recall_at_k(ranked_ids, gold, 10)

            if gold not in fused_docs:
                body = gold_texts.get(gold, "")
                miss_rows.append(
                    {
                        "id": row["id"],
                        "gold_doc_id": gold,
                        "gold_title": titles.get(gold, ""),
                        "gold_url": row.get("gold_doc_url"),
                        "question_head": row["question"].split("\n", 1)[0][:160],
                        "token_overlap": round(_overlap(row["question"], body), 3),
                        "in_dense_max": in_dense,
                        "in_lexical_max": in_lex,
                    }
                )

        n = len(golden)
        for k, bucket in per_k.items():
            for key in ("dense_hit", "lexical_hit", "fused_hit", "recall@10"):
                bucket[key] = round(bucket[key] / n, 4)

        # Sample complete misses for label review (lowest overlap first — likelier noise).
        miss_rows.sort(key=lambda r: (r["token_overlap"], r["id"]))
        import random

        rng = random.Random(seed)
        # Prefer low-overlap for noise suspects; also keep a random mid sample.
        low = miss_rows[: max(sample_misses // 2, 1)]
        rest = miss_rows[max(sample_misses // 2, 1) :]
        mid = rng.sample(rest, min(sample_misses - len(low), len(rest))) if rest else []
        sample = low + mid

        return {
            "task": "0.6",
            "store_db": str(db_path),
            "embedding_model": model_name,
            "chunk_tokens": meta.get("chunk_tokens"),
            "n_answerable": n,
            "channel_at_max_k": {**channel, "max_k": max_k},
            "channel_fractions": {k: round(v / n, 4) for k, v in channel.items()},
            "pool_curve": per_k,
            "complete_misses": len(miss_rows),
            "miss_sample": sample,
            "spot_check_prior": {
                "n_reviewed": 20,
                "label_fails": 4,
                "noise_rate_estimate": 0.20,
                "source": "evals/datasets/spot_check.md",
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=STORE_DB_PATH)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument(
        "--pool-ks",
        default="50,100,200,500",
        help="Comma-separated candidate pool sizes for the ceiling curve",
    )
    parser.add_argument("--sample-misses", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260802)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if not args.db.is_file():
        print(f"store missing: {args.db}", file=sys.stderr)
        return 1

    pool_ks = [int(x) for x in args.pool_ks.split(",") if x.strip()]
    report = analyze(
        db_path=args.db,
        golden_path=args.golden,
        pool_ks=pool_ks,
        sample_misses=args.sample_misses,
        seed=args.seed,
    )
    text = json.dumps(report, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(f"wrote {args.out}")
    print(
        f"n={report['n_answerable']} complete_misses={report['complete_misses']} "
        f"channel={report['channel_fractions']}"
    )
    for k, bucket in report["pool_curve"].items():
        print(
            f"  pool@{k}: dense_hit={bucket['dense_hit']:.3f} "
            f"lex_hit={bucket['lexical_hit']:.3f} fused_hit={bucket['fused_hit']:.3f} "
            f"recall@10={bucket['recall@10']:.3f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
