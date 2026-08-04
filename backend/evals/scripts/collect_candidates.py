"""Collect all resolved docs-link candidates for golden answerable rows (Task 0.7).

Surfaces ambiguity instead of hiding it behind resolved[0] (BUG-014).
Also builds the prioritized remediation_queue.jsonl triage slice.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

from evals.harness.golden_links import (
    accepted_answer_htmls,
    aggregate_candidates,
    collect_resolved_hits,
    thread_id_from_url,
)
from evals.harness.paths import EVALS_ROOT, GOLDEN_PATH

MANIFEST_PATH = EVALS_ROOT / "corpus" / "auth0" / "docs" / "manifest.json"
REDIRECTS_PATH = EVALS_ROOT / "corpus" / "auth0" / "docs" / "redirects_flat.json"
FORUM_RAW = EVALS_ROOT / "corpus" / "auth0" / "forum" / "raw"
CANDIDATES_PATH = EVALS_ROOT / "datasets" / "retrieval_golden_candidates.jsonl"
QUEUE_PATH = EVALS_ROOT / "datasets" / "remediation_queue.jsonl"
DEFAULT_AUDIT = EVALS_ROOT / "reports" / "first_stage_audit_c256.json"


def load_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_miss_ids(audit_path: Path) -> list[str]:
    """Prefer full complete_miss_ids; fall back to miss_sample."""
    if not audit_path.is_file():
        print(f"WARNING: audit missing: {audit_path}", file=sys.stderr)
        return []
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    ids = audit.get("complete_miss_ids")
    if isinstance(ids, list) and ids:
        # May be list[str] or list[dict]
        out: list[str] = []
        for item in ids:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict) and item.get("id"):
                out.append(str(item["id"]))
        return out
    sample = audit.get("miss_sample") or []
    return [str(r["id"]) for r in sample if r.get("id")]


def collect_for_row(
    row: dict,
    *,
    url_to_id: dict[str, str],
    redirects: dict[str, str],
    id_to_doc: dict,
) -> dict:
    tid = thread_id_from_url(str(row.get("source_thread_url") or ""))
    topic = None
    if tid:
        topic_path = FORUM_RAW / f"{tid}.json"
        if topic_path.is_file():
            try:
                topic = json.loads(topic_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                topic = None

    candidates: list[dict] = []
    if topic is not None:
        htmls = accepted_answer_htmls(topic)
        resolved = collect_resolved_hits(htmls, url_to_id, redirects, id_to_doc)
        candidates = aggregate_candidates(resolved)

    # Always include current gold as a candidate so single-link rows stay reviewable.
    gold_id = str(row.get("gold_doc_id") or "")
    gold_url = str(row.get("gold_doc_url") or "")
    if gold_id and gold_id not in {c["doc_id"] for c in candidates}:
        candidates.append(
            {
                "doc_id": gold_id,
                "url": gold_url,
                "position": len(candidates),
                "occurrence_count": 0,
                "from_current_gold": True,
            }
        )

    return {
        "id": row["id"],
        "question": row["question"],
        "source_thread_url": row.get("source_thread_url", ""),
        "current_gold_doc_id": gold_id,
        "current_gold_doc_url": gold_url,
        "thread_id": tid,
        "candidates": candidates,
        "n_candidates": len(candidates),
    }


def build_queue(
    candidate_rows: list[dict],
    *,
    miss_ids: list[str],
    single_frac: float,
    seed: int,
) -> list[dict]:
    by_id = {r["id"]: r for r in candidate_rows}
    selected: dict[str, dict] = {}

    def add(row: dict, reason: str) -> None:
        rid = row["id"]
        if rid in selected:
            reasons = selected[rid].setdefault("triage_reasons", [])
            if reason not in reasons:
                reasons.append(reason)
            return
        out = dict(row)
        out["triage_reasons"] = [reason]
        selected[rid] = out

    for row in candidate_rows:
        # Distinct docs from answer HTML (ignore synthetic from_current_gold-only padding).
        real = [c for c in row["candidates"] if not c.get("from_current_gold")]
        if len(real) > 1:
            add(row, "multi_candidate")

    for mid in miss_ids:
        row = by_id.get(mid)
        if row:
            add(row, "complete_miss")

    remaining = [
        r
        for r in candidate_rows
        if r["id"] not in selected
        and len([c for c in r["candidates"] if not c.get("from_current_gold")]) <= 1
    ]
    rng = random.Random(seed)
    rng.shuffle(remaining)
    n_single = max(1, int(round(len(remaining) * single_frac))) if remaining else 0
    for row in remaining[:n_single]:
        add(row, "stratified_single")

    # Stable order: multi first, then complete_miss, then stratified; within by id.
    reason_rank = {"multi_candidate": 0, "complete_miss": 1, "stratified_single": 2}

    def sort_key(r: dict) -> tuple:
        reasons = r.get("triage_reasons") or []
        best = min(reason_rank.get(x, 9) for x in reasons) if reasons else 9
        return (best, r["id"])

    return sorted(selected.values(), key=sort_key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=GOLDEN_PATH)
    parser.add_argument("--out-candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument("--out-queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--single-frac", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()

    if not MANIFEST_PATH.is_file():
        print(f"manifest missing: {MANIFEST_PATH}", file=sys.stderr)
        return 1
    if not args.golden.is_file():
        print(f"golden missing: {args.golden}", file=sys.stderr)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    redirects = (
        json.loads(REDIRECTS_PATH.read_text(encoding="utf-8")) if REDIRECTS_PATH.exists() else {}
    )
    url_to_id: dict[str, str] = manifest["url_to_id"]
    id_to_doc = {d["gold_doc_id"]: d for d in manifest["documents"]}

    golden = [r for r in load_jsonl(args.golden) if r.get("answerable")]
    print(f"collecting candidates for {len(golden)} answerable rows")

    candidate_rows: list[dict] = []
    missing_topic = 0
    multi = 0
    for row in golden:
        collected = collect_for_row(
            row, url_to_id=url_to_id, redirects=redirects, id_to_doc=id_to_doc
        )
        tid = collected["thread_id"]
        if tid is None or not (FORUM_RAW / f"{tid}.json").is_file():
            missing_topic += 1
        real = [c for c in collected["candidates"] if not c.get("from_current_gold")]
        if len(real) > 1:
            multi += 1
        candidate_rows.append(collected)

    write_jsonl(args.out_candidates, candidate_rows)
    print(
        f"wrote {args.out_candidates}: {len(candidate_rows)} rows "
        f"(multi_candidate={multi}, missing_forum_topic={missing_topic})"
    )

    miss_ids = load_miss_ids(args.audit)
    print(f"loaded {len(miss_ids)} complete-miss ids from {args.audit}")
    queue = build_queue(
        candidate_rows,
        miss_ids=miss_ids,
        single_frac=args.single_frac,
        seed=args.seed,
    )
    write_jsonl(args.out_queue, queue)
    reason_counts: dict[str, int] = {}
    for r in queue:
        for reason in r.get("triage_reasons") or []:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    print(f"wrote {args.out_queue}: {len(queue)} triage rows {reason_counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
