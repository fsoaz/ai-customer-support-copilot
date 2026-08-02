"""SQLite harness store: documents, chunks, embeddings, FTS5 lexical index."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import numpy as np

SCHEMA = """
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS documents (
  gold_doc_id   TEXT PRIMARY KEY,
  source_path   TEXT NOT NULL,
  title         TEXT NOT NULL,
  url_path      TEXT NOT NULL,
  content_hash  TEXT NOT NULL,
  token_count   INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS chunks (
  chunk_id      TEXT PRIMARY KEY,
  gold_doc_id   TEXT NOT NULL REFERENCES documents(gold_doc_id) ON DELETE CASCADE,
  chunk_index   INTEGER NOT NULL,
  content       TEXT NOT NULL,
  token_count   INTEGER NOT NULL,
  embedding     BLOB NOT NULL,
  UNIQUE (gold_doc_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks(gold_doc_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
  chunk_id UNINDEXED,
  gold_doc_id UNINDEXED,
  content,
  tokenize = 'porter unicode61'
);

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class StoredChunk:
    chunk_id: str
    gold_doc_id: str
    chunk_index: int
    content: str
    token_count: int
    embedding: np.ndarray


class ChunkStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ChunkStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def reset(self) -> None:
        self._conn.executescript(
            """
            DROP TABLE IF EXISTS chunks_fts;
            DROP TABLE IF EXISTS chunks;
            DROP TABLE IF EXISTS documents;
            DROP TABLE IF EXISTS meta;
            """
        )
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def set_meta(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def get_meta(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return None if row is None else str(row["value"])

    def upsert_document(
        self,
        *,
        gold_doc_id: str,
        source_path: str,
        title: str,
        url_path: str,
        content_hash: str,
        token_count: int,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO documents(
              gold_doc_id, source_path, title, url_path, content_hash, token_count
            )
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(gold_doc_id) DO UPDATE SET
              source_path = excluded.source_path,
              title = excluded.title,
              url_path = excluded.url_path,
              content_hash = excluded.content_hash,
              token_count = excluded.token_count
            """,
            (gold_doc_id, source_path, title, url_path, content_hash, token_count),
        )

    def replace_chunks(self, gold_doc_id: str, chunks: list[StoredChunk]) -> None:
        existing = self._conn.execute(
            "SELECT chunk_id FROM chunks WHERE gold_doc_id = ?", (gold_doc_id,)
        ).fetchall()
        for row in existing:
            self._conn.execute("DELETE FROM chunks_fts WHERE chunk_id = ?", (row["chunk_id"],))
        self._conn.execute("DELETE FROM chunks WHERE gold_doc_id = ?", (gold_doc_id,))
        for chunk in chunks:
            blob = chunk.embedding.astype(np.float32).tobytes()
            self._conn.execute(
                """
                INSERT INTO chunks(
                  chunk_id, gold_doc_id, chunk_index, content, token_count, embedding
                )
                VALUES(?, ?, ?, ?, ?, ?)
                """,
                (
                    chunk.chunk_id,
                    chunk.gold_doc_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.token_count,
                    blob,
                ),
            )
            self._conn.execute(
                "INSERT INTO chunks_fts(chunk_id, gold_doc_id, content) VALUES(?, ?, ?)",
                (chunk.chunk_id, chunk.gold_doc_id, chunk.content),
            )

    def commit(self) -> None:
        self._conn.commit()

    def document_ids(self) -> set[str]:
        rows = self._conn.execute("SELECT gold_doc_id FROM documents").fetchall()
        return {str(r["gold_doc_id"]) for r in rows}

    def document_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
        return int(row["n"])

    def chunk_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS n FROM chunks").fetchone()
        return int(row["n"])

    def load_all_embeddings(self) -> tuple[list[str], list[str], np.ndarray]:
        rows = self._conn.execute(
            "SELECT chunk_id, gold_doc_id, embedding FROM chunks ORDER BY gold_doc_id, chunk_index"
        ).fetchall()
        if not rows:
            return [], [], np.zeros((0, 0), dtype=np.float32)
        chunk_ids: list[str] = []
        doc_ids: list[str] = []
        vectors: list[np.ndarray] = []
        for row in rows:
            chunk_ids.append(str(row["chunk_id"]))
            doc_ids.append(str(row["gold_doc_id"]))
            vec = np.frombuffer(row["embedding"], dtype=np.float32)
            vectors.append(vec)
        matrix = np.vstack(vectors)
        return chunk_ids, doc_ids, matrix

    def lexical_search(self, query: str, *, top_k: int = 50) -> list[tuple[str, str, float]]:
        """Return (chunk_id, gold_doc_id, bm25_rank) — lower bm25_rank is better in FTS5."""
        q = _fts_query(query)
        if not q:
            return []
        rows = self._conn.execute(
            """
            SELECT chunk_id, gold_doc_id, bm25(chunks_fts) AS score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (q, top_k),
        ).fetchall()
        return [(str(r["chunk_id"]), str(r["gold_doc_id"]), float(r["score"])) for r in rows]

    def get_chunk_texts(self, chunk_ids: list[str]) -> dict[str, str]:
        if not chunk_ids:
            return {}
        placeholders = ",".join("?" * len(chunk_ids))
        rows = self._conn.execute(
            f"SELECT chunk_id, content FROM chunks WHERE chunk_id IN ({placeholders})",
            chunk_ids,
        ).fetchall()
        return {str(r["chunk_id"]): str(r["content"]) for r in rows}

    def document_titles(self) -> dict[str, str]:
        rows = self._conn.execute("SELECT gold_doc_id, title FROM documents").fetchall()
        return {str(r["gold_doc_id"]): str(r["title"]) for r in rows}

    def document_text(self, gold_doc_id: str) -> str:
        rows = self._conn.execute(
            "SELECT content FROM chunks WHERE gold_doc_id = ? ORDER BY chunk_index",
            (gold_doc_id,),
        ).fetchall()
        return " ".join(str(r["content"]) for r in rows)

    def write_json_meta(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


_ALNUM_RE = re.compile(r"[A-Za-z0-9_]+")


def _fts_query(query: str) -> str:
    """Build a safe FTS5 OR-query from alphanumeric tokens."""
    tokens = [t.lower() for t in _ALNUM_RE.findall(query) if len(t) > 1]
    if not tokens:
        return ""
    # Deduplicate while preserving order; cap length for pathological tickets.
    seen: set[str] = set()
    uniq: list[str] = []
    for tok in tokens:
        if tok in seen:
            continue
        seen.add(tok)
        uniq.append(tok)
        if len(uniq) >= 32:
            break
    return " OR ".join(uniq)
