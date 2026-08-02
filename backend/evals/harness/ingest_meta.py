"""Resolve ingest fingerprints for a given harness store DB.

Priority: SQLite ``meta.ingest_meta_json`` → sidecar beside the DB → default
``ingest_meta.json`` (only when evaluating the default store path).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from evals.harness.paths import STORE_DB_PATH, STORE_META_PATH

if TYPE_CHECKING:
    from evals.harness.store import ChunkStore

INGEST_META_KEY = "ingest_meta_json"


def meta_sidecar_path(db_path: Path) -> Path:
    """JSON path paired with ``db_path``.

    Default store keeps the historical name ``ingest_meta.json``.
    Alternate stores use ``{stem}_meta.json`` beside the SQLite file.
    """
    resolved = db_path.resolve()
    if resolved == STORE_DB_PATH.resolve():
        return STORE_META_PATH
    return db_path.with_name(f"{db_path.stem}_meta.json")


def load_ingest_meta(*, db_path: Path, store: ChunkStore | None = None) -> dict:
    """Load ingest meta for ``db_path``, preferring DB-embedded JSON."""
    if store is not None:
        raw = store.get_meta(INGEST_META_KEY)
        if raw:
            return json.loads(raw)
    elif db_path.is_file():
        from evals.harness.store import ChunkStore as _ChunkStore

        with _ChunkStore(db_path) as opened:
            raw = opened.get_meta(INGEST_META_KEY)
            if raw:
                return json.loads(raw)

    sidecar = meta_sidecar_path(db_path)
    if sidecar.is_file():
        return json.loads(sidecar.read_text(encoding="utf-8"))

    # Last resort: default file only when evaluating the default DB.
    if db_path.resolve() == STORE_DB_PATH.resolve() and STORE_META_PATH.is_file():
        return json.loads(STORE_META_PATH.read_text(encoding="utf-8"))
    return {}
