"""Unit tests for Stage 0 eval pure helpers (BUG-012)."""

from __future__ import annotations

from evals.scripts.build_golden import (
    diversify,
    follow_redirects,
    normalize_path,
    pair_id,
    redact_question,
    truncate_question,
)
from evals.scripts.parse_docs_manifest import doc_id_for
from evals.scripts.parse_docs_manifest import normalize_path as docs_normalize_path


def test_normalize_path_strips_md_index_and_fragment() -> None:
    assert normalize_path("/foo/bar.md#section") == "/foo/bar"
    assert normalize_path("foo/index") == "/foo"
    assert docs_normalize_path("/a/b/?q=1") == "/a/b"


def test_follow_redirects_chain() -> None:
    redirects = {"/a": "/b", "/b": "/c"}
    assert follow_redirects("/a", redirects) == "/c"
    assert follow_redirects("/missing", redirects) == "/missing"


def test_doc_id_for_stable() -> None:
    a = doc_id_for("articles/login/index.md")
    b = doc_id_for("articles/login/index.md")
    assert a == b
    assert a.startswith("auth0-")


def test_diversify_round_robins_docs() -> None:
    rows = [
        {"gold_doc_id": "d1", "id": "1"},
        {"gold_doc_id": "d1", "id": "2"},
        {"gold_doc_id": "d2", "id": "3"},
        {"gold_doc_id": "d3", "id": "4"},
    ]
    out = diversify(rows, target=3)
    assert len(out) == 3
    assert {r["gold_doc_id"] for r in out} == {"d1", "d2", "d3"}


def test_pair_id_deterministic() -> None:
    assert pair_id("hello", "doc", 1) == pair_id("hello", "doc", 1)
    assert pair_id("hello", "doc", 1) != pair_id("hello", "doc", 2)


def test_redact_question_emails_and_tenants() -> None:
    q = "Contact ray.garg@zappsec.com on myapp.us.auth0.com with client_secret"
    out = redact_question(q)
    assert "@" not in out
    assert "<EMAIL_1>" in out
    assert "<TENANT_1>" in out
    assert "<CLIENT_SECRET>" in out


def test_truncate_keeps_head_and_tail() -> None:
    text = "HEAD-" + ("x" * 3000) + "-TAIL_QUESTION?"
    out = truncate_question(text, limit=200)
    assert out.startswith("HEAD-")
    assert "TAIL_QUESTION?" in out
    assert "…" in out
    assert len(out) <= 200
