"""Unit tests for Stage 0 eval pure helpers (BUG-012)."""

from __future__ import annotations

import json

from evals.harness.golden_links import follow_redirects, normalize_path
from evals.scripts import apply_remediation
from evals.scripts.apply_remediation import approved_for_application
from evals.scripts.build_golden import diversify, pair_id, redact_question, truncate_question
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


def test_approved_for_application_requires_explicit_review() -> None:
    assert approved_for_application({"human_verdict": "agree"})
    assert approved_for_application(
        {
            "human_verdict": "disagree",
            "human_correction": {"chosen_doc_id": "corrected-doc"},
        }
    )
    assert not approved_for_application({"human_verdict": None})
    assert not approved_for_application({"human_verdict": "pending"})
    assert not approved_for_application({"human_verdict": "disagree"})


def test_approved_only_does_not_apply_pending_judgment(tmp_path, monkeypatch) -> None:
    golden = tmp_path / "golden.jsonl"
    judgments = tmp_path / "judgments.jsonl"
    spot = tmp_path / "spot.jsonl"
    sidecar = tmp_path / "sidecar.jsonl"
    report = tmp_path / "report.json"

    golden.write_text(
        json.dumps({"id": "q1", "gold_doc_id": "original", "answerable": True}) + "\n",
        encoding="utf-8",
    )
    judgments.write_text(
        json.dumps({"id": "q1", "chosen_doc_id": "replacement"}) + "\n",
        encoding="utf-8",
    )
    spot.write_text(
        json.dumps({"id": "q1", "human_verdict": None}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "apply_remediation.py",
            "--golden",
            str(golden),
            "--judgments",
            str(judgments),
            "--spot-check",
            str(spot),
            "--sidecar",
            str(sidecar),
            "--report",
            str(report),
            "--force-unverified",
            "--approved-only",
        ],
    )

    assert apply_remediation.main() == 0
    [result] = apply_remediation.load_jsonl(golden)
    assert result["gold_doc_id"] == "original"
    assert result.get("label_reviewed") is not True
