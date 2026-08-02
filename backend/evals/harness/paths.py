"""Shared filesystem paths for the Stage 0 eval harness."""

from __future__ import annotations

from pathlib import Path

EVALS_ROOT = Path(__file__).resolve().parents[1]
CORPUS_DOCS = EVALS_ROOT / "corpus" / "auth0" / "docs"
RAW_DIR = CORPUS_DOCS / "raw"
MANIFEST_PATH = CORPUS_DOCS / "manifest.json"
PIN_PATH = CORPUS_DOCS / "expected_commit.txt"
GOLDEN_PATH = EVALS_ROOT / "datasets" / "retrieval_golden.jsonl"
STORE_DIR = EVALS_ROOT / "store"
STORE_DB_PATH = STORE_DIR / "auth0_chunks.sqlite"
STORE_META_PATH = STORE_DIR / "ingest_meta.json"
