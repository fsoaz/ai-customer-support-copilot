"""Harvest solved Auth0 Community topics via Discourse public JSON.

Respects robots.txt: uses /c/ and /t/ only — never /search.
Fetches topic JSON as soon as a solved topic is listed (no full pre-scan).
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

BASE = "https://community.auth0.com"
USER_AGENT = "CorpCorpusBot/0.1 (+local-research; Stage0 eval corpus; respectful rate limit)"

# Help-first; then related technical categories
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


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(6),
    reraise=True,
)
def get_json(http: httpx.Client, url: str) -> dict:
    resp = http.get(url)
    if resp.status_code == 429:
        retry_after = float(resp.headers.get("Retry-After", "15"))
        log(f"429 on {url}; sleeping {retry_after}s")
        time.sleep(retry_after)
        resp = http.get(url)
    if resp.status_code >= 500:
        resp.raise_for_status()
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def harvest(
    *,
    category_ids: list[int],
    max_pages: int,
    max_topics: int,
    sleep_s: float,
    force: bool,
) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)

    existing = {p.stem for p in RAW_DIR.glob("*.json")}
    fetched_new = 0
    skipped = 0
    seen_ids: set[int] = set()

    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=60.0,
        follow_redirects=True,
    ) as http:
        # Expand Help subcategories when available
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

        log(f"scanning categories: {ids}")

        with INDEX_PATH.open("a", encoding="utf-8") as index_f:
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
                        log(f"skip {url}: {exc}")
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
                            existing.add(str(tid))
                            continue

                        slug = t.get("slug") or "topic"
                        try:
                            topic = get_json(http, f"{BASE}/t/{slug}/{tid}.json")
                        except Exception as exc:  # noqa: BLE001
                            log(f"fail topic {tid}: {exc}")
                            time.sleep(sleep_s)
                            continue
                        time.sleep(sleep_s)
                        if not topic:
                            continue
                        out_path.write_text(json.dumps(topic), encoding="utf-8")
                        index_f.write(
                            json.dumps(
                                {
                                    "id": tid,
                                    "slug": topic.get("slug") or slug,
                                    "title": topic.get("title") or t.get("title"),
                                    "path": out_path.name,
                                }
                            )
                            + "\n"
                        )
                        index_f.flush()
                        fetched_new += 1
                        if fetched_new % 25 == 0:
                            log(f"progress: fetched_new={fetched_new} skipped_existing={skipped}")

                    if len(topics) < 30:
                        break

    total = len(list(RAW_DIR.glob("*.json")))
    log(f"done: fetched_new={fetched_new} skipped_existing={skipped} total_raw={total}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-topics", type=int, default=2000)
    parser.add_argument("--sleep", type=float, default=0.35)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--categories", type=int, nargs="*", default=DEFAULT_CATEGORY_IDS)
    args = parser.parse_args()
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
