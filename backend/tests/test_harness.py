"""Unit tests for Stage 0 chunking, clean, RRF, and store helpers."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from evals.harness.chunking import chunk_text, tokenize
from evals.harness.clean import markdown_to_text
from evals.harness.rrf import collapse_chunks_to_docs, reciprocal_rank_fusion
from evals.harness.store import ChunkStore, StoredChunk


def test_tokenize_splits_on_whitespace() -> None:
    assert tokenize("hello  world\nAuth0") == ["hello", "world", "Auth0"]


def test_chunk_text_size_and_overlap() -> None:
    tokens = [f"t{i}" for i in range(100)]
    text = " ".join(tokens)
    chunks = chunk_text(text, chunk_tokens=20, overlap_ratio=0.15)
    assert chunks
    assert all(c.token_count <= 20 for c in chunks)
    # Overlap 3 → step 17; last chunk may be shorter.
    assert chunks[0].content.startswith("t0 ")
    # Second window should start at token 17.
    assert chunks[1].content.startswith("t17 ")


def test_chunk_text_short_doc_single_chunk() -> None:
    chunks = chunk_text("one two three", chunk_tokens=512, overlap_ratio=0.15)
    assert len(chunks) == 1
    assert chunks[0].token_count == 3


def test_chunk_text_empty() -> None:
    assert chunk_text("   \n") == []


def test_markdown_to_text_strips_frontmatter_and_links() -> None:
    raw = """---
title: Hello
---
# Heading

See [docs](https://example.com) and `code`.

```js
const x = 1;
```
"""
    out = markdown_to_text(raw)
    assert "title:" not in out
    assert "Heading" in out
    assert "docs" in out
    assert "https://example.com" not in out
    assert "const x = 1" in out


def test_rrf_prefers_consensus() -> None:
    # b is rank-1 in both lists → clear winner over split a/c.
    fused = reciprocal_rank_fusion([["b", "a", "c"], ["b", "c", "a"]], k=60)
    ids = [i for i, _ in fused]
    assert ids[0] == "b"
    assert set(ids) == {"a", "b", "c"}


def test_rrf_weights_prefer_heavier_list() -> None:
    # Disjoint tops: heavier list's rank-1 must beat the lighter list's rank-1.
    fused = reciprocal_rank_fusion(
        [["x", "a"], ["c", "y"]],
        k=60,
        weights=[1.0, 5.0],
    )
    ids = [i for i, _ in fused]
    assert ids[0] == "c"


def test_collapse_chunks_to_docs_keeps_best() -> None:
    ranked = [
        ("c1", "docA", 0.9),
        ("c2", "docB", 0.8),
        ("c3", "docA", 0.7),
    ]
    docs = collapse_chunks_to_docs(ranked)
    assert docs == [("docA", 0.9), ("docB", 0.8)]


def test_store_roundtrip_and_lexical(tmp_path: Path) -> None:
    db = tmp_path / "t.sqlite"
    dim = 8
    with ChunkStore(db) as store:
        store.upsert_document(
            gold_doc_id="doc1",
            source_path="articles/a.md",
            title="SAML SSO",
            url_path="/saml",
            content_hash="abc",
            token_count=10,
        )
        vec = np.ones(dim, dtype=np.float32)
        vec /= np.linalg.norm(vec)
        store.replace_chunks(
            "doc1",
            [
                StoredChunk(
                    chunk_id="doc1::c0000",
                    gold_doc_id="doc1",
                    chunk_index=0,
                    content="Configure SAML identity provider initiated SSO",
                    token_count=7,
                    embedding=vec,
                )
            ],
        )
        store.commit()
        assert store.document_count() == 1
        assert store.chunk_count() == 1
        ids, docs, matrix = store.load_all_embeddings()
        assert ids == ["doc1::c0000"]
        assert docs == ["doc1"]
        assert matrix.shape == (1, dim)
        hits = store.lexical_search("SAML SSO", top_k=5)
        assert hits
        assert hits[0][0] == "doc1::c0000"


def test_ingest_meta_sidecar_and_sqlite_roundtrip(tmp_path: Path) -> None:
    from evals.harness.ingest_meta import (
        INGEST_META_KEY,
        load_ingest_meta,
        meta_sidecar_path,
    )

    db = tmp_path / "auth0_chunks_bge_base.sqlite"
    payload = {
        "task": "0.5",
        "embedding_model": "BAAI/bge-base-en-v1.5",
        "embedding_dim": 768,
        "chunk_tokens": 512,
    }
    sidecar = meta_sidecar_path(db)
    assert sidecar.name == "auth0_chunks_bge_base_meta.json"

    with ChunkStore(db) as store:
        store.set_meta(INGEST_META_KEY, json.dumps(payload))
        store.write_json_meta(sidecar, payload)
        store.commit()
        loaded = load_ingest_meta(db_path=db, store=store)
    assert loaded["embedding_model"] == "BAAI/bge-base-en-v1.5"
    assert loaded["task"] == "0.5"

    # Prefer SQLite over a stale/wrong sidecar.
    sidecar.write_text('{"embedding_model": "WRONG"}\n', encoding="utf-8")
    loaded2 = load_ingest_meta(db_path=db)
    assert loaded2["embedding_model"] == "BAAI/bge-base-en-v1.5"
