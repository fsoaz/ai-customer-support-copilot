"""Build docs manifest from fetched auth0/docs raw tree (no network).

Maps article paths and redirected canonical URLs to stable gold_doc_id values.
Requires redirects_flat.json (produced by dumping config/redirects.js via node).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "corpus" / "auth0" / "docs"
RAW_DIR = DOCS_DIR / "raw"
REDIRECTS_JSON = DOCS_DIR / "redirects_flat.json"
MANIFEST_PATH = DOCS_DIR / "manifest.json"
FETCH_META = DOCS_DIR / "fetch_meta.json"

SKIP_DIR_PARTS = {"_includes", "media"}
DOC_BASE = "https://auth0.com/docs"


def dump_redirects() -> dict[str, str]:
    """Export redirects.js to a flat from→to JSON map."""
    script = """
const redirects = require('./config/redirects.js');
const map = {};
for (const rule of redirects) {
  const to = Array.isArray(rule.to) ? rule.to[0] : rule.to;
  const froms = Array.isArray(rule.from) ? rule.from : [rule.from];
  if (typeof to !== 'string') continue;
  for (const from of froms) {
    if (typeof from === 'string') map[from] = to;
  }
}
process.stdout.write(JSON.stringify(map));
"""
    out = subprocess.check_output(
        ["node", "-e", script],
        cwd=str(RAW_DIR),
        text=True,
    )
    data = json.loads(out)
    REDIRECTS_JSON.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def normalize_path(path: str) -> str:
    path = path.strip()
    if not path.startswith("/"):
        path = "/" + path
    path = path.split("#", 1)[0].split("?", 1)[0]
    if path.endswith(".md"):
        path = path[: -len(".md")]
    if path.endswith("/index"):
        path = path[: -len("/index")] or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    return path or "/"


def follow_redirects(path: str, redirects: dict[str, str], limit: int = 10) -> str:
    seen: set[str] = set()
    cur = normalize_path(path)
    for _ in range(limit):
        if cur in seen:
            break
        seen.add(cur)
        nxt = redirects.get(cur)
        if not nxt:
            break
        cur = normalize_path(nxt)
    return cur


def article_url_path(rel: Path) -> str:
    """articles/foo/bar.md → /foo/bar ; articles/foo/index.md → /foo"""
    parts = rel.as_posix()
    assert parts.startswith("articles/")
    path = "/" + parts[len("articles/") :]
    if path.endswith(".md"):
        path = path[: -len(".md")]
    return normalize_path(path)


def doc_id_for(source_path: str) -> str:
    digest = hashlib.sha1(source_path.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", source_path.strip("/")).strip("-").lower()
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    return f"auth0-{slug}-{digest}"


def build_manifest(redirects: dict[str, str]) -> dict:
    articles_root = RAW_DIR / "articles"
    if not articles_root.is_dir():
        raise FileNotFoundError(f"missing articles dir: {articles_root}")

    documents: list[dict] = []
    url_to_id: dict[str, str] = {}

    for md in sorted(articles_root.rglob("*.md")):
        rel = md.relative_to(RAW_DIR)
        if any(part in SKIP_DIR_PARTS for part in rel.parts):
            continue
        source_path = rel.as_posix()
        url_path = article_url_path(rel)
        canonical = follow_redirects(url_path, redirects)
        gold_id = doc_id_for(source_path)
        title = _title_from_file(md)

        aliases = {url_path, canonical}
        # Any redirect source that lands on this canonical
        for frm, to in redirects.items():
            if follow_redirects(frm, redirects) == canonical:
                aliases.add(normalize_path(frm))

        entry = {
            "gold_doc_id": gold_id,
            "source_path": source_path,
            "url_path": url_path,
            "canonical_path": canonical,
            "canonical_url": f"{DOC_BASE}{canonical}",
            "title": title,
            "alias_paths": sorted(aliases),
        }
        documents.append(entry)
        for alias in aliases:
            # Prefer first writer; later collisions keep first (stable sort by path)
            url_to_id.setdefault(alias, gold_id)
            url_to_id.setdefault(f"{DOC_BASE}{alias}", gold_id)

    commit = None
    if FETCH_META.exists():
        commit = json.loads(FETCH_META.read_text(encoding="utf-8")).get("commit")

    return {
        "repo": "https://github.com/auth0/docs",
        "commit": commit,
        "doc_base": DOC_BASE,
        "document_count": len(documents),
        "documents": documents,
        "url_to_id": url_to_id,
    }


def _title_from_file(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return path.stem
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ")


def resolve_doc_url(url: str, manifest: dict) -> tuple[str | None, str | None]:
    """Return (gold_doc_id, canonical_url) for an auth0.com/docs URL."""
    url_to_id: dict[str, str] = manifest["url_to_id"]
    if REDIRECTS_JSON.exists():
        redirects = json.loads(REDIRECTS_JSON.read_text(encoding="utf-8"))
    else:
        redirects = {}

    raw = url.strip()
    if raw.startswith(DOC_BASE):
        path = raw[len(DOC_BASE) :] or "/"
    elif "auth0.com/docs" in raw:
        path = raw.split("auth0.com/docs", 1)[1]
    else:
        path = raw
    path = normalize_path(path)

    for candidate in (path, follow_redirects(path, redirects), f"{DOC_BASE}{path}"):
        gold_id = url_to_id.get(candidate)
        if gold_id:
            break
    else:
        return None, None

    for doc in manifest["documents"]:
        if doc["gold_doc_id"] == gold_id:
            return gold_id, doc["canonical_url"]
    return gold_id, f"{DOC_BASE}{path}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-redirects-dump",
        action="store_true",
        help="Reuse existing redirects_flat.json",
    )
    args = parser.parse_args()

    if not RAW_DIR.is_dir() or not (RAW_DIR / "articles").is_dir():
        print("docs raw missing; run fetch_docs.py first", file=sys.stderr)
        return 1

    if args.skip_redirects_dump and REDIRECTS_JSON.exists():
        redirects = json.loads(REDIRECTS_JSON.read_text(encoding="utf-8"))
    else:
        try:
            redirects = dump_redirects()
        except (subprocess.CalledProcessError, FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"failed to dump redirects: {exc}", file=sys.stderr)
            return 1

    manifest = build_manifest(redirects)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"wrote {MANIFEST_PATH} — {manifest['document_count']} docs, "
        f"{len(manifest['url_to_id'])} url keys"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
