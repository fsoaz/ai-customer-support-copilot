"""Build retrieval_golden.jsonl from Auth0 forum raw JSON + docs manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from html import unescape
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "corpus" / "auth0" / "docs" / "manifest.json"
REDIRECTS_PATH = ROOT / "corpus" / "auth0" / "docs" / "redirects_flat.json"
FORUM_RAW = ROOT / "corpus" / "auth0" / "forum" / "raw"
OUT_PATH = ROOT / "datasets" / "retrieval_golden.jsonl"
SPOT_CANDIDATES = ROOT / "datasets" / "spot_check_candidates.jsonl"

DOC_BASE = "https://auth0.com/docs"
DOCS_HREF_RE = re.compile(
    r"https?://(?:www\.)?auth0\.com/docs(/[^\s\"'<>#]+)?",
    re.IGNORECASE,
)

# Hand-authored questions Auth0 docs do not cover (refusal / unanswerable path).
HAND_UNANSWERABLE: list[str] = [
    "How do I configure Auth0 to mint Solana wallet addresses for every social login?",
    "Where is the Auth0 setting that disables GDPR for EU tenants permanently?",
    "How do I enable Auth0's built-in COBOL mainframe connector for AS/400?",
    "What is the Auth0 API endpoint to refund a Stripe charge from an Action?",
    "How do I make Auth0 send push notifications via WhatsApp Business API natively?",
    "Where do I configure Auth0's native Kubernetes operator for on-prem Redis sessions?",
    "How can Auth0 automatically translate my Universal Login page into Klingon?",
    "What Auth0 Dashboard toggle enables free lifetime Enterprise support?",
    "How do I use Auth0 as a payment gateway for cryptocurrency subscriptions?",
    "Where is the Auth0 feature that deletes all competitor IdP tenants from the internet?",
    "How do I configure Auth0 to bypass MFA for users named Alice on weekends only via UI?",
    "What is Auth0's official SOAP 1.1 federation connector for Windows Server 2003?",
    "How do I export Auth0 user passwords in plaintext for migration audits?",
    "Where can I buy Auth0 credits with airline miles inside the Dashboard?",
    "How do I enable Auth0's quantum-resistant lattice OTP factor in the free plan?",
    "What Action secret lets me SSH into Auth0's production database?",
    "How do I configure Auth0 to host my company's blog on auth0.com/docs?",
    "Where is the Auth0 toggle that makes ID tokens legally binding contracts?",
    "How do I stream Auth0 logs directly into a fax machine via the Management API?",
    "What is the Auth0 GraphQL mutation to rename another customer's tenant?",
    "How do I enable Auth0's built-in TikTok Shop checkout for B2B Organizations?",
    "Where do I configure Auth0 to act as an SMTP relay for arbitrary domains?",
    "How can I make Auth0 issue X.509 client certs from a Let's Encrypt integration in Actions?",
    "What Dashboard page configures Auth0's offline air-gapped USB key login?",
    "How do I turn on Auth0's native COBOL-to-OIDC protocol translator?",
    "Where is the setting for Auth0 to auto-post answers on Stack Overflow for my tickets?",
    "How do I configure Auth0 Organizations to bill end-users via Western Union?",
    "What is the undocumented Auth0 header that disables rate limits tenant-wide forever?",
    "How do I use Auth0 Lock to render a full Excel spreadsheet editor in the login widget?",
    "Where do I enable Auth0's satellite phone MFA channel for maritime tenants?",
    "How can Auth0 automatically open GitHub PRs to fix my application bugs after failed logins?",
    "What Auth0 feature maps user emails to their physical home addresses without consent?",
]


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
    # Also catch bare URLs in cooked HTML
    for m in DOCS_HREF_RE.finditer(html or ""):
        full = m.group(0)
        links.append(full)
    # Normalize
    out: list[str] = []
    seen: set[str] = set()
    for link in links:
        path = link
        if "auth0.com/docs" in link:
            path = link.split("auth0.com/docs", 1)[1]
        path = normalize_path(path)
        if path == "/" or path.startswith("/api/"):
            continue
        canon_url = f"{DOC_BASE}{path}"
        if canon_url not in seen:
            seen.add(canon_url)
            out.append(canon_url)
    return out


def synthetic_doc_id(path: str) -> str:
    digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:12]
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", path.strip("/")).strip("-").lower()
    if len(slug) > 80:
        slug = slug[:80].rstrip("-")
    return f"auth0-url-{slug}-{digest}"


def resolve(
    url: str,
    url_to_id: dict[str, str],
    redirects: dict[str, str],
    id_to_doc: dict,
    *,
    allow_synthetic: bool = True,
) -> tuple[str, str] | None:
    path = url
    if "auth0.com/docs" in url:
        path = url.split("auth0.com/docs", 1)[1]
    path = normalize_path(path)
    # Skip empty / root / API reference dumps that are not article pages
    if path in {"/", ""} or path.startswith("/api/") or path.startswith("/api"):
        return None
    # Require at least one path segment beyond /docs
    if path.count("/") < 1 or path == "/":
        return None
    segments = [s for s in path.split("/") if s]
    if len(segments) < 1:
        return None

    canonical = follow_redirects(path, redirects)
    candidates = [
        path,
        canonical,
        f"{DOC_BASE}{path}",
        f"{DOC_BASE}{canonical}",
    ]
    for c in candidates:
        gold_id = url_to_id.get(c)
        if gold_id and gold_id in id_to_doc:
            return gold_id, id_to_doc[gold_id]["canonical_url"]

    if not allow_synthetic:
        return None
    # Newer Auth0 docs URLs often are not in the MIT GitHub mirror yet; still valid gold labels.
    if len(segments) < 2 and segments[0] in {"index", "get-started"}:
        return None
    return synthetic_doc_id(canonical), f"{DOC_BASE}{canonical}"


def question_from_topic(topic: dict) -> str:
    posts = topic.get("post_stream", {}).get("posts") or []
    if not posts:
        title = topic.get("title") or ""
        return title.strip()
    op = posts[0]
    body = html_to_text(op.get("cooked") or "")
    title = (topic.get("title") or "").strip()
    if body:
        # Prefer title + body for ticket-like phrasing; cap length
        title_in_body = title.lower() in body.lower()[:120].lower()
        q = body if title_in_body else f"{title}\n\n{body}"
        if len(q) > 2000:
            q = q[:2000].rstrip() + "…"
        return q
    return title


def accepted_answer_htmls(topic: dict) -> list[str]:
    htmls: list[str] = []
    for ans in topic.get("accepted_answers") or []:
        if ans.get("cooked"):
            htmls.append(ans["cooked"])
    posts = topic.get("post_stream", {}).get("posts") or []
    for p in posts:
        if p.get("accepted_answer") and p.get("cooked"):
            htmls.append(p["cooked"])
    # Dedupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in htmls:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def pair_id(question: str, gold_doc_id: str | None, thread_id: int | str) -> str:
    raw = f"{thread_id}|{gold_doc_id or 'none'}|{question[:200]}"
    return "q-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_question_key(q: str) -> str:
    q = q.lower()
    q = re.sub(r"\s+", " ", q)
    return q[:500]


def build(
    *,
    target_answerable: int,
    min_unanswerable: int,
) -> None:
    if not MANIFEST_PATH.exists():
        raise SystemExit("manifest missing; run parse_docs_manifest.py")
    if not FORUM_RAW.is_dir():
        raise SystemExit("forum raw missing; run fetch_forum.py")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    redirects = (
        json.loads(REDIRECTS_PATH.read_text(encoding="utf-8")) if REDIRECTS_PATH.exists() else {}
    )
    url_to_id: dict[str, str] = manifest["url_to_id"]
    id_to_doc = {d["gold_doc_id"]: d for d in manifest["documents"]}

    answerable: list[dict] = []
    unanswerable_forum: list[dict] = []
    seen_q: set[str] = set()

    files = sorted(FORUM_RAW.glob("*.json"))
    print(f"scanning {len(files)} forum topics")

    for path in files:
        if path.name == ".gitkeep":
            continue
        try:
            topic = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not topic.get("has_accepted_answer") and not topic.get("accepted_answers"):
            continue

        tid = topic.get("id") or path.stem
        slug = topic.get("slug") or "topic"
        thread_url = f"https://community.auth0.com/t/{slug}/{tid}"
        question = question_from_topic(topic)
        if len(question) < 20:
            continue
        qkey = normalize_question_key(question)
        if qkey in seen_q:
            continue

        htmls = accepted_answer_htmls(topic)
        if not htmls:
            continue

        resolved: list[tuple[str, str]] = []
        for html in htmls:
            for link in extract_docs_links(html):
                hit = resolve(link, url_to_id, redirects, id_to_doc, allow_synthetic=True)
                if hit:
                    resolved.append(hit)

        if resolved:
            # Prefer first docs link in the accepted answer (order of appearance)
            gold_id, gold_url = resolved[0]
            row = {
                "id": pair_id(question, gold_id, tid),
                "question": question,
                "gold_doc_url": gold_url,
                "gold_doc_id": gold_id,
                "source_thread_url": thread_url,
                "answerable": True,
            }
            answerable.append(row)
            seen_q.add(qkey)
        else:
            answer_text = " ".join(html_to_text(h) for h in htmls).lower()
            refusalish = any(
                phrase in answer_text
                for phrase in (
                    "not supported",
                    "not possible",
                    "cannot be done",
                    "isn't supported",
                    "is not available",
                    "feature request",
                    "doesn't support",
                    "does not support",
                    "no way to",
                    "not currently",
                )
            )
            row = {
                "id": pair_id(question, None, tid),
                "question": question,
                "gold_doc_url": "",
                "gold_doc_id": "",
                "source_thread_url": thread_url,
                "answerable": False,
                "_refusalish": refusalish,
            }
            unanswerable_forum.append(row)
            seen_q.add(qkey)

        if len(answerable) >= target_answerable * 2:
            # keep scanning a bit for diversity then stop early if huge
            pass

    # Prefer unique gold docs for diversity
    answerable = _diversify(answerable, target_answerable)

    unanswerable: list[dict] = []
    # Prefer refusalish forum examples
    refusal = [r for r in unanswerable_forum if r.get("_refusalish")]
    other = [r for r in unanswerable_forum if not r.get("_refusalish")]
    for r in refusal + other:
        if len(unanswerable) >= max(0, min_unanswerable - len(HAND_UNANSWERABLE)):
            break
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        unanswerable.append(clean)

    for i, q in enumerate(HAND_UNANSWERABLE):
        if len(unanswerable) >= min_unanswerable and i >= 30:
            break
        unanswerable.append(
            {
                "id": pair_id(q, None, f"hand-{i}"),
                "question": q,
                "gold_doc_url": "",
                "gold_doc_id": "",
                "source_thread_url": "",
                "answerable": False,
            }
        )
        if len(unanswerable) >= min_unanswerable:
            break

    # Ensure at least min_unanswerable
    while len(unanswerable) < min_unanswerable and other:
        r = other.pop()
        clean = {k: v for k, v in r.items() if not k.startswith("_")}
        if clean["id"] not in {u["id"] for u in unanswerable}:
            unanswerable.append(clean)

    rows = answerable + unanswerable
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Spot-check candidates: first 40 answerable for manual review of 20
    with SPOT_CANDIDATES.open("w", encoding="utf-8") as f:
        for row in answerable[:40]:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    n_ans = sum(1 for r in rows if r["answerable"])
    n_un = sum(1 for r in rows if not r["answerable"])
    print(f"wrote {OUT_PATH}: {len(rows)} rows ({n_ans} answerable, {n_un} unanswerable)")
    if n_ans < 300:
        print(
            f"WARNING: only {n_ans} answerable pairs (target 300–500). Fetch more forum topics.",
            file=sys.stderr,
        )


def _diversify(rows: list[dict], target: int) -> list[dict]:
    """Round-robin by gold_doc_id then fill to target."""
    by_doc: dict[str, list[dict]] = {}
    for r in rows:
        by_doc.setdefault(r["gold_doc_id"], []).append(r)
    out: list[dict] = []
    while len(out) < min(target, len(rows)) and by_doc:
        empty: list[str] = []
        for doc_id, bucket in list(by_doc.items()):
            if not bucket:
                empty.append(doc_id)
                continue
            out.append(bucket.pop(0))
            if len(out) >= target:
                break
        for doc_id in empty:
            by_doc.pop(doc_id, None)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-answerable", type=int, default=400)
    parser.add_argument("--min-unanswerable", type=int, default=35)
    args = parser.parse_args()
    build(target_answerable=args.target_answerable, min_unanswerable=args.min_unanswerable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
