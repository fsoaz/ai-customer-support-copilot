"""Harvest solved Auth0 Community topics via Discourse public JSON.

Respects robots.txt: uses /c/ and /t/ only — never /search.
Fetches topic JSON as soon as a solved topic is listed.
Writes a durable failure ledger and rebuilds index.jsonl from raw/ (BUG-010/011).
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "corpus" / "auth0" / "forum" / "raw"
INDEX_PATH = ROOT / "corpus" / "auth0" / "forum" / "index.jsonl"
FAILURES_PATH = ROOT / "corpus" / "auth0" / "forum" / "harvest_failures.jsonl"

BASE = "https://community.auth0.com"
USER_AGENT = "CorpCorpusBot/0.1 (+local-research; Stage0 eval corpus; respectful rate limit)"

DEFAULT_CATEGORY_IDS = [
    6,  # Get Help
    118,  # Dev to Dev Hub
    98,  # Developer Hub
    115,  # Auth0 for Gen AI
    111,  # Fine-Grained Authorization
    112,  # Passkeys
    8,  # JWT.io
    88,  # Marketplace
]


def log(msg: str) -> None:
    print(msg, flush=True)


def record_failure(topic_id: int | str | None, status: str, reason: str, url: str = "") -> None:
    FAILURES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FAILURES_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "topic_id": topic_id,
                    "status": status,
                    "reason": reason,
                    "url": url,
                    "ts": time.time(),
                }
            )
            + "\n"
        )


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def get_json(http: httpx.Client, url: str) -> dict:
    """GET JSON with multi-429 handling (BUG-010)."""
    for attempt in range(8):
        resp = http.get(url)
        if resp.status_code == 429:
            retry_after = float(resp.headers.get("Retry-After", str(min(60, 5 * (attempt + 1)))))
            log(f"429 on {url}; sleeping {retry_after}s (attempt {attempt + 1})")
            time.sleep(retry_after)
            continue
        if resp.status_code == 404:
            return {}
        if resp.status_code >= 500:
            resp.raise_for_status()
        resp.raise_for_status()
        return resp.json()
    raise httpx.HTTPStatusError(
        f"exhausted 429 retries for {url}",
        request=httpx.Request("GET", url),
        response=resp,
    )


def rebuild_index() -> int:
    """Rebuild index.jsonl from raw/ (BUG-011)."""
    rows: list[dict] = []
    for path in sorted(RAW_DIR.glob("*.json")):
        try:
            topic = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        rows.append(
            {
                "id": topic.get("id") or int(path.stem),
                "slug": topic.get("slug"),
                "title": topic.get("title"),
                "path": path.name,
            }
        )
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INDEX_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    return len(rows)


def harvest(
    *,
    category_ids: list[int],
    max_pages: int,
    max_topics: int,
    sleep_s: float,
    force: bool,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fetched_new = 0
    skipped = 0
    seen_ids: set[int] = set()
    category_breaks = 0

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=60.0,
        follow_redirects=True,
    ) as http:
        ids = list(category_ids)
        try:
            cats = get_json(http, f"{BASE}/categories.json")
            time.sleep(sleep_s)
            for c in cats.get("category_list", {}).get("categories", []):
                if c.get("id") == 6:
                    for sub in c.get("subcategory_ids") or []:
                        if sub not in ids:
                            ids.append(sub)
        except Exception as exc:  # noqa: BLE001
            log(f"category discovery warning: {exc}")
            record_failure(None, "discovery", str(exc), f"{BASE}/categories.json")

        log(f"scanning categories: {ids}")

        for cid in ids:
            if fetched_new >= max_topics:
                break
            for page in range(0, max_pages):
                if fetched_new >= max_topics:
                    break
                url = f"{BASE}/c/{cid}.json?page={page}"
                try:
                    data = get_json(http, url)
                except httpx.HTTPStatusError as exc:
                    log(f"ERROR category break {url}: {exc}")
                    record_failure(None, "category_break", str(exc), url)
                    category_breaks += 1
                    break
                time.sleep(sleep_s)
                topics = data.get("topic_list", {}).get("topics", [])
                if not topics:
                    break

                solved = [t for t in topics if t.get("has_accepted_answer")]
                log(
                    f"category {cid} page {page}: {len(topics)} topics, "
                    f"{len(solved)} solved; new_fetched={fetched_new}"
                )

                for t in solved:
                    if fetched_new >= max_topics:
                        break
                    tid = int(t["id"])
                    if tid in seen_ids:
                        continue
                    seen_ids.add(tid)
                    out_path = RAW_DIR / f"{tid}.json"
                    if out_path.exists() and not force:
                        skipped += 1
                        continue

                    slug = t.get("slug") or "topic"
                    topic_url = f"{BASE}/t/{slug}/{tid}.json"
                    try:
                        topic = get_json(http, topic_url)
                    except Exception as exc:  # noqa: BLE001
                        log(f"fail topic {tid}: {exc}")
                        record_failure(tid, "topic_fetch", str(exc), topic_url)
                        time.sleep(sleep_s)
                        continue
                    time.sleep(sleep_s)
                    if not topic:
                        record_failure(tid, "404", "empty topic payload", topic_url)
                        continue
                    out_path.write_text(json.dumps(topic), encoding="utf-8")
                    fetched_new += 1
                    if fetched_new % 25 == 0:
                        log(f"progress: fetched_new={fetched_new} skipped_existing={skipped}")

                if len(topics) < 30:
                    break

    n_index = rebuild_index()
    total = len(list(RAW_DIR.glob("*.json")))
    log(
        f"done: fetched_new={fetched_new} skipped_existing={skipped} "
        f"total_raw={total} index_rows={n_index} category_breaks={category_breaks}"
    )
    if category_breaks:
        log(f"WARNING: {category_breaks} category page walks aborted (see {FAILURES_PATH})")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-topics", type=int, default=2000)
    parser.add_argument("--sleep", type=float, default=0.35)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--categories", type=int, nargs="*", default=DEFAULT_CATEGORY_IDS)
    parser.add_argument(
        "--rebuild-index-only",
        action="store_true",
        help="Only rebuild index.jsonl from existing raw/",
    )
    args = parser.parse_args()
    if args.rebuild_index_only:
        n = rebuild_index()
        log(f"rebuilt index with {n} rows")
        return 0
    harvest(
        category_ids=list(args.categories),
        max_pages=args.max_pages,
        max_topics=args.max_topics,
        sleep_s=args.sleep,
        force=args.force,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
