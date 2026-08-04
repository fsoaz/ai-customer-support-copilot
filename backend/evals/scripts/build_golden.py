"""Build retrieval_golden.jsonl from Auth0 forum raw JSON + docs manifest.

Only mirror-backed golds (manifest hits) are kept — no synthetic auth0-url-* (BUG-001).
Unanswerable rows are hand-authored only (BUG-002/003).
Ambiguous multi-candidate threads are skipped into a review file (BUG-014).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

from evals.harness.golden_links import (
    accepted_answer_htmls,
    aggregate_candidates,
    collect_resolved_hits,
    html_to_text,
    pick_unambiguous_gold,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "corpus" / "auth0" / "docs" / "manifest.json"
REDIRECTS_PATH = ROOT / "corpus" / "auth0" / "docs" / "redirects_flat.json"
FORUM_RAW = ROOT / "corpus" / "auth0" / "forum" / "raw"
OUT_PATH = ROOT / "datasets" / "retrieval_golden.jsonl"
SPOT_CANDIDATES = ROOT / "datasets" / "spot_check_candidates.jsonl"
COVERAGE_PATH = ROOT / "datasets" / "coverage_report.json"
AMBIGUOUS_PATH = ROOT / "datasets" / "build_golden_ambiguous.jsonl"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
# tenant-looking hosts: foo.us.auth0.com / foo.eu.auth0.com / custom.auth0.com
TENANT_RE = re.compile(
    r"\b[a-z0-9][a-z0-9-]{1,40}\.(?:us|eu|au|jp|uk)?\.?auth0\.com\b",
    re.IGNORECASE,
)
CLIENT_SECRET_RE = re.compile(r"\bclient_secret\b", re.IGNORECASE)

# Near-miss negatives: Auth0 vocabulary, plausible mechanism, not a real docs feature.
HAND_NEAR_MISS: list[str] = [
    "How do I enable Auth0's Dashboard toggle for device attestation on desktop Electron apps?",
    "Where do I set a tenant-wide default that forces PKCE on all legacy Regular Web Applications retrospectively?",
    "How can I configure per-Organization custom SMS OTP sender without writing a custom Action?",
    "What is the Management API endpoint to clone an entire tenant including secrets into another region?",
    "How do I enable Auth0 Lock native biometric PIN fallback for web Universal Login?",
    "Where in the Dashboard do I configure Auth0 to mint pairwise pairwise-subject identifiers per RP by default?",
    "How can I set Actions to run on the Authentication API /oauth/token endpoint for ROPG only via UI?",
    "What setting enables Auth0 Organizations to inherit MFA policies from a parent Organization hierarchy?",
    "How do I configure Auth0 to auto-rotate signing keys weekly and push JWKS to my CDN without downtime hooks?",
    "Where do I enable silent passwordless email OTP for machine-to-machine applications?",
    "How can I attach custom SAML AttributeConsumingService indexes from the Dashboard without metadata edits?",
    "What is the Auth0 feature to version Universal Login prompts per git branch of my app?",
    "How do I configure Auth0 Forms to write directly to Salesforce Opportunity Stage on submit without Actions?",
    "Where do I enable continuous access evaluation (CAE) style token revocation for SPA refresh tokens in free tier?",
    "How can I force Auth0 to issue only encrypted ID tokens (JWE) for all OIDC clients via a tenant flag?",
    "What Dashboard page configures Auth0 as an SCIM 2.0 client pushing users into Workday HCM nightly?",
    "How do I enable per-connection DPoP requirement for social Google logins?",
    "Where do I configure Auth0 to store refresh tokens exclusively in HttpOnly cookies for Regular Web Apps without a BFF?",
    "How can I set a custom ACR value that Universal Login must satisfy before issuing tokens, without Actions?",
    "What is the built-in Auth0 connector for syncing blocked users to my Okta Workforce org in real time?",
    "How do I enable Auth0 log streaming with field-level encryption keys I manage in AWS KMS from the Dashboard alone?",
    "Where do I configure tenant-level allowlists that block authentication from Tor exit nodes automatically?",
    "How can I make Auth0 issue RFC 9068 JWT access tokens for my API by flipping one Application setting?",
    "What setting lets Organizations define their own custom database connection scripts independently of the tenant?",
    "How do I enable Auth0's native passkey attestation conveyance preference UI for platform authenticators only?",
]

# Absurdist sanity-floor negatives — tracked as negative_slice=absurdist; never average with near-miss.
HAND_ABSURDIST: list[str] = [
    "How can Auth0 automatically translate my Universal Login page into Klingon?",
    "How do I stream Auth0 logs directly into a fax machine via the Management API?",
    "Where can I buy Auth0 credits with airline miles inside the Dashboard?",
    "What Action secret lets me SSH into Auth0's production database?",
    "How do I enable Auth0's built-in COBOL mainframe connector for AS/400?",
    "What Auth0 feature maps user emails to their physical home addresses without consent?",
]


def redact_question(text: str) -> str:
    """Redact emails and tenant hosts at build time (BUG-009)."""
    email_i = 0
    tenant_i = 0

    def _email(_m: re.Match[str]) -> str:
        nonlocal email_i
        email_i += 1
        return f"<EMAIL_{email_i}>"

    def _tenant(_m: re.Match[str]) -> str:
        nonlocal tenant_i
        tenant_i += 1
        return f"<TENANT_{tenant_i}>"

    text = EMAIL_RE.sub(_email, text)
    text = TENANT_RE.sub(_tenant, text)
    text = CLIENT_SECRET_RE.sub("<CLIENT_SECRET>", text)
    return text


def truncate_question(text: str, limit: int = 2000) -> str:
    """Keep head and tail so the actual question is not always dropped (BUG-013)."""
    if len(text) <= limit:
        return text
    head = limit // 2 - 10
    tail = limit - head - 5
    return text[:head].rstrip() + "\n…\n" + text[-tail:].lstrip()


def question_from_topic(topic: dict) -> str:
    posts = topic.get("post_stream", {}).get("posts") or []
    if not posts:
        return redact_question((topic.get("title") or "").strip())
    op = posts[0]
    body = html_to_text(op.get("cooked") or "")
    title = (topic.get("title") or "").strip()
    if body:
        title_in_body = bool(title) and title.lower() in body.lower()[:120].lower()
        q = body if title_in_body else f"{title}\n\n{body}"
    else:
        q = title
    return redact_question(truncate_question(q))


def pair_id(question: str, gold_doc_id: str | None, thread_id: int | str) -> str:
    raw = f"{thread_id}|{gold_doc_id or 'none'}|{question[:200]}"
    return "q-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def normalize_question_key(q: str) -> str:
    q = q.lower()
    q = re.sub(r"\s+", " ", q)
    return q[:500]


def diversify(rows: list[dict], target: int) -> list[dict]:
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


def stratified_spot_sample(answerable: list[dict], *, n: int, seed: int) -> list[dict]:
    """Seeded sample stratified by whether gold is in-manifest (all should be) (BUG-006)."""
    rng = random.Random(seed)
    pool = list(answerable)
    rng.shuffle(pool)
    return pool[:n]


def build(
    *,
    target_answerable: int,
    min_unanswerable: int,
    spot_seed: int,
    require_full_coverage: bool,
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
    ambiguous: list[dict] = []
    skipped_unresolved = 0
    seen_q: set[str] = set()

    files = sorted(FORUM_RAW.glob("*.json"))
    print(f"scanning {len(files)} forum topics")

    for path in files:
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

        resolved = collect_resolved_hits(htmls, url_to_id, redirects, id_to_doc)
        if not resolved:
            # No mirror-backed docs link — skip (do NOT invent unanswerable labels) BUG-002
            skipped_unresolved += 1
            continue

        candidates = aggregate_candidates(resolved)
        picked = pick_unambiguous_gold(candidates)
        if picked is None:
            ambiguous.append(
                {
                    "thread_id": tid,
                    "source_thread_url": thread_url,
                    "question": question,
                    "candidates": candidates,
                    "reason": "ambiguous_multi_candidate",
                }
            )
            seen_q.add(qkey)
            continue

        gold_id, gold_url = picked
        row = {
            "id": pair_id(question, gold_id, tid),
            "question": question,
            "gold_doc_url": gold_url,
            "gold_doc_id": gold_id,
            "source_thread_url": thread_url,
            "answerable": True,
            "label_source": "original",
            "label_reviewed": False,
        }
        answerable.append(row)
        seen_q.add(qkey)

    answerable = diversify(answerable, target_answerable)

    unanswerable: list[dict] = []
    for i, q in enumerate(HAND_NEAR_MISS):
        unanswerable.append(
            {
                "id": pair_id(q, None, f"near-{i}"),
                "question": q,
                "gold_doc_url": "",
                "gold_doc_id": "",
                "source_thread_url": "",
                "answerable": False,
                "negative_slice": "near_miss",
            }
        )
    for i, q in enumerate(HAND_ABSURDIST):
        unanswerable.append(
            {
                "id": pair_id(q, None, f"abs-{i}"),
                "question": q,
                "gold_doc_url": "",
                "gold_doc_id": "",
                "source_thread_url": "",
                "answerable": False,
                "negative_slice": "absurdist",
            }
        )
    if len(unanswerable) < min_unanswerable:
        raise SystemExit(
            f"only {len(unanswerable)} hand unanswerables; need >= {min_unanswerable}"
        )

    # Coverage: every answerable gold must be in manifest
    synthetic = [r for r in answerable if str(r["gold_doc_id"]).startswith("auth0-url-")]
    missing = [r for r in answerable if r["gold_doc_id"] not in id_to_doc]
    coverage = {
        "answerable": len(answerable),
        "unanswerable": len(unanswerable),
        "synthetic_count": len(synthetic),
        "missing_from_manifest": len(missing),
        "coverage_pct": 100.0
        if not answerable
        else 100.0 * (len(answerable) - len(missing)) / len(answerable),
        "skipped_unresolved_forum_topics": skipped_unresolved,
        "ambiguous_multi_candidate": len(ambiguous),
        "forum_files_scanned": len(files),
    }
    COVERAGE_PATH.write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(coverage))

    AMBIGUOUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AMBIGUOUS_PATH.open("w", encoding="utf-8") as f:
        for row in ambiguous:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"wrote {AMBIGUOUS_PATH}: {len(ambiguous)} ambiguous threads (flagged for review)")

    if require_full_coverage and (synthetic or missing):
        raise SystemExit(
            f"coverage gate failed: synthetic={len(synthetic)} missing={len(missing)} "
            f"(see {COVERAGE_PATH})"
        )
    if len(answerable) < 300:
        print(
            f"WARNING: only {len(answerable)} answerable pairs (target 300–500). "
            "Fetch more forum topics.",
            file=sys.stderr,
        )

    rows = answerable + unanswerable
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    spot = stratified_spot_sample(answerable, n=min(40, len(answerable)), seed=spot_seed)
    with SPOT_CANDIDATES.open("w", encoding="utf-8") as f:
        meta = {"seed": spot_seed, "n": len(spot), "method": "rng_shuffle_all_answerable"}
        f.write(json.dumps({"_meta": meta}) + "\n")
        for row in spot:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(
        f"wrote {OUT_PATH}: {len(rows)} rows "
        f"({len(answerable)} answerable, {len(unanswerable)} unanswerable); "
        f"spot seed={spot_seed}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-answerable", type=int, default=400)
    parser.add_argument("--min-unanswerable", type=int, default=30)
    parser.add_argument("--spot-seed", type=int, default=20260730)
    parser.add_argument(
        "--allow-partial-coverage",
        action="store_true",
        help="Do not abort when golds are missing from manifest (default: abort)",
    )
    args = parser.parse_args()
    build(
        target_answerable=args.target_answerable,
        min_unanswerable=args.min_unanswerable,
        spot_seed=args.spot_seed,
        require_full_coverage=not args.allow_partial_coverage,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
