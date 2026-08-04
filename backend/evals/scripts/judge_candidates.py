"""Judge remediation-queue candidates (Task 0.7).

LLM (OpenAI-compatible) proposes best doc_id or none; heuristic fallback when no API key.
Writes remediation_judgments.jsonl — never mutates the golden set.
Also emits a stratified human spot-check sample for verify-before-apply.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from pathlib import Path

import httpx

from evals.harness.paths import EVALS_ROOT, STORE_DB_PATH
from evals.harness.store import ChunkStore

QUEUE_PATH = EVALS_ROOT / "datasets" / "remediation_queue.jsonl"
JUDGMENTS_PATH = EVALS_ROOT / "datasets" / "remediation_judgments.jsonl"
SPOT_PATH = EVALS_ROOT / "datasets" / "remediation_spot_check.jsonl"
DEFAULT_DB = EVALS_ROOT / "store" / "auth0_chunks_bge_base_c256.sqlite"

_TOKEN_RE = re.compile(r"[a-z0-9]{3,}", re.I)

SYSTEM_PROMPT = """You are labeling golden retrieval pairs for an Auth0 docs eval set.
Given a support question and candidate documentation pages (title + excerpt), pick the single
candidate that actually answers the question, or "none" if none is load-bearing.

Rules:
- Prefer the doc that would let an agent draft a correct reply with citations.
- Reject incidental footer/signature links that do not answer the question.
- Reply with JSON only: {"chosen_doc_id": "<id or none>", "rationale": "<one short sentence>"}
"""


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


def _overlap(question: str, text: str) -> float:
    q = set(_TOKEN_RE.findall(question.lower()))
    g = set(_TOKEN_RE.findall(text.lower()))
    if not q or not g:
        return 0.0
    return len(q & g) / len(q)


def heuristic_judge(row: dict, *, titles: dict[str, str], excerpts: dict[str, str]) -> dict:
    """Rank by token overlap, then occurrence_count, then earlier position."""
    question = str(row.get("question") or "")
    scored: list[tuple[float, int, int, str, str]] = []
    for c in row.get("candidates") or []:
        doc_id = str(c["doc_id"])
        body = excerpts.get(doc_id, "")
        title = titles.get(doc_id, "")
        ov = _overlap(question, f"{title}\n{body}")
        occ = int(c.get("occurrence_count") or 0)
        pos = int(c.get("position") or 0)
        # Higher overlap + occurrence wins; earlier position breaks ties.
        scored.append((ov, occ, -pos, doc_id, title))
    scored.sort(reverse=True)
    if not scored or scored[0][0] < 0.05:
        return {
            "chosen_doc_id": "none",
            "rationale": "heuristic: no candidate with meaningful token overlap",
            "method": "heuristic",
            "score_overlap": scored[0][0] if scored else 0.0,
        }
    best = scored[0]
    return {
        "chosen_doc_id": best[3],
        "rationale": f"heuristic: overlap={best[0]:.3f} occ={best[1]} title={best[4][:80]}",
        "method": "heuristic",
        "score_overlap": best[0],
    }


def llm_judge(
    row: dict,
    *,
    titles: dict[str, str],
    excerpts: dict[str, str],
    model: str,
    base_url: str,
    api_key: str,
) -> dict:
    parts = [
        f"Question:\n{row['question'][:3000]}\n",
        "Candidates:",
    ]
    for c in row.get("candidates") or []:
        doc_id = str(c["doc_id"])
        title = titles.get(doc_id, "(no title)")
        excerpt = (excerpts.get(doc_id) or "")[:1200]
        parts.append(
            f"- doc_id={doc_id}\n  url={c.get('url')}\n  title={title}\n"
            f"  occurrence_count={c.get('occurrence_count')} position={c.get('position')}\n"
            f"  excerpt={excerpt}\n"
        )
    parts.append('Respond with JSON: {"chosen_doc_id": "... or none", "rationale": "..."}')
    user = "\n".join(parts)

    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    with httpx.Client(timeout=90.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    content = data["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    chosen = str(parsed.get("chosen_doc_id") or "none").strip()
    rationale = str(parsed.get("rationale") or "").strip()
    valid_ids = {str(c["doc_id"]) for c in row.get("candidates") or []}
    if chosen != "none" and chosen not in valid_ids:
        return {
            "chosen_doc_id": "none",
            "rationale": f"llm returned unknown id {chosen!r}; treated as none. raw={rationale}",
            "method": "llm",
            "model": model,
        }
    return {
        "chosen_doc_id": chosen,
        "rationale": rationale,
        "method": "llm",
        "model": model,
    }


def stratify_spot(judgments: list[dict], *, n: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    by_bucket: dict[str, list[dict]] = {
        "changed": [],
        "same": [],
        "none": [],
    }
    for j in judgments:
        chosen = j.get("chosen_doc_id")
        current = j.get("current_gold_doc_id")
        if chosen == "none":
            by_bucket["none"].append(j)
        elif chosen == current:
            by_bucket["same"].append(j)
        else:
            by_bucket["changed"].append(j)

    # Aim for mix: ~40% changed, ~30% none, ~30% same (adjust to available).
    targets = {
        "changed": max(1, int(round(n * 0.4))),
        "none": max(1, int(round(n * 0.3))),
        "same": max(1, int(round(n * 0.3))),
    }
    sample: list[dict] = []
    for key, target in targets.items():
        pool = list(by_bucket[key])
        rng.shuffle(pool)
        for row in pool[:target]:
            out = dict(row)
            out["spot_bucket"] = key
            out["human_verdict"] = None  # fill during spot-check
            out["human_note"] = ""
            sample.append(out)

    # Top up if short.
    if len(sample) < n:
        remaining = [j for j in judgments if j["id"] not in {s["id"] for s in sample}]
        rng.shuffle(remaining)
        for row in remaining[: n - len(sample)]:
            out = dict(row)
            out["spot_bucket"] = "topup"
            out["human_verdict"] = None
            out["human_note"] = ""
            sample.append(out)
    return sample[:n]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    default_db = DEFAULT_DB if DEFAULT_DB.is_file() else STORE_DB_PATH
    parser.add_argument("--db", type=Path, default=default_db)
    parser.add_argument("--out", type=Path, default=JUDGMENTS_PATH)
    parser.add_argument("--spot-out", type=Path, default=SPOT_PATH)
    parser.add_argument("--spot-n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260804)
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument(
        "--base-url",
        default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
    )
    parser.add_argument(
        "--force-heuristic",
        action="store_true",
        help="Skip LLM even if OPENAI_API_KEY is set",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Judge only first N queue rows (0=all)",
    )
    args = parser.parse_args()

    if not args.queue.is_file():
        print(f"queue missing: {args.queue}", file=sys.stderr)
        return 1
    if not args.db.is_file():
        print(f"store missing: {args.db}", file=sys.stderr)
        return 1

    queue = load_jsonl(args.queue)
    if args.limit and args.limit > 0:
        queue = queue[: args.limit]

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    use_llm = bool(api_key) and not args.force_heuristic
    if not use_llm:
        print("OPENAI_API_KEY unset or --force-heuristic: using heuristic judge", file=sys.stderr)

    judgments: list[dict] = []
    with ChunkStore(args.db) as store:
        titles = store.document_titles()
        # Prefetch excerpts for all candidate ids in queue.
        needed: set[str] = set()
        for row in queue:
            for c in row.get("candidates") or []:
                needed.add(str(c["doc_id"]))
        excerpts = {doc_id: store.document_text(doc_id)[:4000] for doc_id in needed}

        for i, row in enumerate(queue):
            if use_llm:
                try:
                    verdict = llm_judge(
                        row,
                        titles=titles,
                        excerpts=excerpts,
                        model=args.model,
                        base_url=args.base_url,
                        api_key=api_key,
                    )
                except Exception as exc:  # noqa: BLE001 — record and fall back
                    print(f"LLM failed on {row['id']}: {exc}; heuristic fallback", file=sys.stderr)
                    verdict = heuristic_judge(row, titles=titles, excerpts=excerpts)
                    verdict["llm_error"] = str(exc)
            else:
                verdict = heuristic_judge(row, titles=titles, excerpts=excerpts)

            cand_by_id = {str(c["doc_id"]): c for c in row.get("candidates") or []}
            chosen = verdict["chosen_doc_id"]
            chosen_url = ""
            if chosen != "none" and chosen in cand_by_id:
                chosen_url = str(cand_by_id[chosen].get("url") or "")

            judgments.append(
                {
                    "id": row["id"],
                    "question": row["question"],
                    "source_thread_url": row.get("source_thread_url", ""),
                    "current_gold_doc_id": row.get("current_gold_doc_id", ""),
                    "current_gold_doc_url": row.get("current_gold_doc_url", ""),
                    "triage_reasons": row.get("triage_reasons", []),
                    "n_candidates": row.get("n_candidates", len(row.get("candidates") or [])),
                    "candidates": row.get("candidates", []),
                    "chosen_doc_id": chosen,
                    "chosen_doc_url": chosen_url,
                    "rationale": verdict.get("rationale", ""),
                    "method": verdict.get("method"),
                    "model": verdict.get("model"),
                    "score_overlap": verdict.get("score_overlap"),
                    "human_approved": None,
                }
            )
            if (i + 1) % 25 == 0 or i + 1 == len(queue):
                print(f"judged {i + 1}/{len(queue)}")

    write_jsonl(args.out, judgments)
    changed = sum(
        1
        for j in judgments
        if j["chosen_doc_id"] != "none" and j["chosen_doc_id"] != j["current_gold_doc_id"]
    )
    none_n = sum(1 for j in judgments if j["chosen_doc_id"] == "none")
    print(f"wrote {args.out}: {len(judgments)} (changed={changed}, none={none_n})")

    spot = stratify_spot(judgments, n=args.spot_n, seed=args.seed)
    write_jsonl(args.spot_out, spot)
    print(f"wrote {args.spot_out}: {len(spot)} spot-check rows (human_verdict=null)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
