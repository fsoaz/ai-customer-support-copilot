"""Ingest pinned Auth0 MIT docs: clean → chunk → embed → SQLite harness store.

Stage 0 only — not the product FastAPI ingest path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

from evals.harness.chunking import (
    DEFAULT_CHUNK_TOKENS,
    DEFAULT_OVERLAP_RATIO,
    chunk_text,
    tokenize,
)
from evals.harness.clean import markdown_to_text
from evals.harness.embed import DEFAULT_EMBEDDING_MODEL, Embedder
from evals.harness.paths import (
    MANIFEST_PATH,
    PIN_PATH,
    RAW_DIR,
    STORE_DB_PATH,
    STORE_META_PATH,
)
from evals.harness.store import ChunkStore, StoredChunk

# Flush when this many chunk texts are pending (complete documents only).
_FLUSH_CHUNK_TARGET = 64


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_id(gold_doc_id: str, chunk_index: int) -> str:
    return f"{gold_doc_id}::c{chunk_index:04d}"


def _read_pin() -> str:
    return PIN_PATH.read_text(encoding="utf-8").strip().splitlines()[0].strip()


def _verify_raw_pin(pin: str) -> str:
    sha = subprocess.check_output(
        ["git", "-C", str(RAW_DIR), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if not sha.startswith(pin) and not pin.startswith(sha):
        raise RuntimeError(
            f"docs raw SHA {sha} does not match pin {pin}. Re-run evals.scripts.fetch_docs --force."
        )
    return sha


def ingest(
    *,
    reset: bool = True,
    limit: int | None = None,
    chunk_tokens: int = DEFAULT_CHUNK_TOKENS,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    db_path: Path = STORE_DB_PATH,
) -> dict:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"missing manifest: {MANIFEST_PATH}")
    if not RAW_DIR.is_dir():
        raise FileNotFoundError(f"missing docs raw: {RAW_DIR}; run fetch_docs first")

    pin = _read_pin()
    sha = _verify_raw_pin(pin)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = list(manifest["documents"])
    if limit is not None:
        documents = documents[:limit]

    embedder = Embedder(model_name=model_name)
    started = time.perf_counter()
    skipped_empty = 0
    ingested_docs = 0
    ingested_chunks = 0

    # Pending complete documents awaiting embed+write: list of (doc_meta_fields, chunks)
    pending: list[tuple[dict, list[tuple[int, str, int]]]] = []
    pending_chunk_n = 0

    def flush(store: ChunkStore) -> None:
        nonlocal ingested_chunks, pending_chunk_n
        if not pending:
            return
        flat_texts: list[str] = []
        for _meta, chs in pending:
            for _idx, content, _tok in chs:
                flat_texts.append(content)
        vectors = embedder.embed_documents(flat_texts)
        offset = 0
        for meta, chs in pending:
            stored: list[StoredChunk] = []
            for i, (cidx, content, tok_n) in enumerate(chs):
                stored.append(
                    StoredChunk(
                        chunk_id=_chunk_id(meta["gold_doc_id"], cidx),
                        gold_doc_id=meta["gold_doc_id"],
                        chunk_index=cidx,
                        content=content,
                        token_count=tok_n,
                        embedding=vectors[offset + i],
                    )
                )
            offset += len(chs)
            store.upsert_document(**meta)
            store.replace_chunks(meta["gold_doc_id"], stored)
            ingested_chunks += len(stored)
        store.commit()
        pending.clear()
        pending_chunk_n = 0

    with ChunkStore(db_path) as store:
        if reset:
            store.reset()

        for doc in documents:
            gold_id = doc["gold_doc_id"]
            source_path = doc["source_path"]
            path = RAW_DIR / source_path
            if not path.is_file():
                raise FileNotFoundError(f"manifest source missing on disk: {path}")

            raw = path.read_text(encoding="utf-8", errors="replace")
            text = markdown_to_text(raw)
            tokens = tokenize(text)
            if not tokens:
                skipped_empty += 1
                continue

            chunks = chunk_text(text, chunk_tokens=chunk_tokens, overlap_ratio=overlap_ratio)
            doc_meta = {
                "gold_doc_id": gold_id,
                "source_path": source_path,
                "title": doc.get("title") or source_path,
                "url_path": doc.get("url_path") or "",
                "content_hash": _content_hash(text),
                "token_count": len(tokens),
            }
            chunk_tuples = [(ch.index, ch.content, ch.token_count) for ch in chunks]
            pending.append((doc_meta, chunk_tuples))
            pending_chunk_n += len(chunk_tuples)
            ingested_docs += 1

            if pending_chunk_n >= _FLUSH_CHUNK_TARGET:
                flush(store)

            if ingested_docs % 100 == 0:
                print(f"  … {ingested_docs}/{len(documents)} docs", flush=True)

        flush(store)

        elapsed = time.perf_counter() - started
        meta = {
            "task": "0.2",
            "repo": manifest.get("repo"),
            "commit": sha,
            "expected_commit": pin,
            "embedding_model": embedder.model_name,
            "embedding_dim": embedder.dim,
            "chunk_tokens": chunk_tokens,
            "overlap_ratio": overlap_ratio,
            "tokenizer": "whitespace",
            "document_count": store.document_count(),
            "chunk_count": store.chunk_count(),
            "skipped_empty": skipped_empty,
            "manifest_document_count": len(manifest["documents"]),
            "ingest_seconds": round(elapsed, 2),
            "store_db": str(db_path),
        }
        store.set_meta("ingest_meta_json", json.dumps(meta))
        store.write_json_meta(STORE_META_PATH, meta)
        store.commit()
        return meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="Ingest only first N docs")
    parser.add_argument("--no-reset", action="store_true", help="Do not wipe store first")
    parser.add_argument("--chunk-tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    parser.add_argument("--overlap-ratio", type=float, default=DEFAULT_OVERLAP_RATIO)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--db", type=Path, default=STORE_DB_PATH)
    args = parser.parse_args()
    try:
        meta = ingest(
            reset=not args.no_reset,
            limit=args.limit,
            chunk_tokens=args.chunk_tokens,
            overlap_ratio=args.overlap_ratio,
            model_name=args.model,
            db_path=args.db,
        )
    except (
        FileNotFoundError,
        RuntimeError,
        OSError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ingest_docs failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"ingested {meta['document_count']} docs / {meta['chunk_count']} chunks "
        f"in {meta['ingest_seconds']}s → {meta['store_db']}"
    )
    print(f"meta → {STORE_META_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
