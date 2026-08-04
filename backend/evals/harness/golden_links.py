"""Shared Auth0 docs-link extraction and manifest resolution for golden builders."""

from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup

DOC_BASE = "https://auth0.com/docs"
DOCS_HREF_RE = re.compile(
    r"https?://(?:www\.)?auth0\.com/docs(/[^\s\"'<>#]+)?",
    re.IGNORECASE,
)


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


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    text = unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_docs_links(html: str) -> list[str]:
    links: list[str] = []
    soup = BeautifulSoup(html or "", "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "auth0.com/docs" in href:
            links.append(href)
    for m in DOCS_HREF_RE.finditer(html or ""):
        links.append(m.group(0))
    out: list[str] = []
    seen: set[str] = set()
    for link in links:
        path = link
        if "auth0.com/docs" in link:
            path = link.split("auth0.com/docs", 1)[1]
        path = normalize_path(path)
        if path == "/" or path.startswith("/api"):
            continue
        canon_url = f"{DOC_BASE}{path}"
        if canon_url not in seen:
            seen.add(canon_url)
            out.append(canon_url)
    return out


def resolve(
    url: str,
    url_to_id: dict[str, str],
    redirects: dict[str, str],
    id_to_doc: dict,
) -> tuple[str, str] | None:
    """Resolve only against the MIT mirror manifest — no synthetic IDs (BUG-001)."""
    path = url
    if "auth0.com/docs" in url:
        path = url.split("auth0.com/docs", 1)[1]
    path = normalize_path(path)
    if path in {"/", ""}:
        return None
    candidates = [
        path,
        follow_redirects(path, redirects),
        f"{DOC_BASE}{path}",
        f"{DOC_BASE}{follow_redirects(path, redirects)}",
    ]
    for c in candidates:
        gold_id = url_to_id.get(c)
        if gold_id and gold_id in id_to_doc:
            return gold_id, id_to_doc[gold_id]["canonical_url"]
    return None


def accepted_answer_htmls(topic: dict) -> list[str]:
    htmls: list[str] = []
    for ans in topic.get("accepted_answers") or []:
        if ans.get("cooked"):
            htmls.append(ans["cooked"])
    for p in topic.get("post_stream", {}).get("posts") or []:
        if p.get("accepted_answer") and p.get("cooked"):
            htmls.append(p["cooked"])
    seen: set[str] = set()
    out: list[str] = []
    for h in htmls:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def collect_resolved_hits(
    htmls: list[str],
    url_to_id: dict[str, str],
    redirects: dict[str, str],
    id_to_doc: dict,
) -> list[tuple[str, str]]:
    """Return every resolved (doc_id, url) hit in appearance order (duplicates kept)."""
    resolved: list[tuple[str, str]] = []
    for html in htmls:
        for link in extract_docs_links(html):
            hit = resolve(link, url_to_id, redirects, id_to_doc)
            if hit:
                resolved.append(hit)
    return resolved


def aggregate_candidates(resolved: list[tuple[str, str]]) -> list[dict]:
    """Collapse resolved hits to distinct docs with first position + occurrence_count."""
    by_id: dict[str, dict] = {}
    for pos, (doc_id, url) in enumerate(resolved):
        if doc_id not in by_id:
            by_id[doc_id] = {
                "doc_id": doc_id,
                "url": url,
                "position": pos,
                "occurrence_count": 0,
            }
        by_id[doc_id]["occurrence_count"] += 1
    return sorted(by_id.values(), key=lambda c: (int(c["position"]), c["doc_id"]))


def pick_unambiguous_gold(
    candidates: list[dict],
) -> tuple[str, str] | None:
    """Auto-pick only when exactly one distinct resolved doc (BUG-014 fix)."""
    if len(candidates) != 1:
        return None
    c = candidates[0]
    return str(c["doc_id"]), str(c["url"])


def thread_id_from_url(source_thread_url: str) -> str | None:
    """Extract Discourse topic id from community.auth0.com/t/.../<id>."""
    if not source_thread_url:
        return None
    parts = source_thread_url.rstrip("/").split("/")
    if not parts:
        return None
    tid = parts[-1]
    return tid if tid.isdigit() else None
