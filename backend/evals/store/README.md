# Local Stage 0 chunk/embed store (gitignored contents).

Regenerate after fetching the pinned Auth0 docs corpus:

```bash
cd backend
uv run python -m evals.scripts.fetch_docs       # if raw/ missing

# Baseline (task 0.2): bge-small, 512-token chunks
uv run python -m evals.scripts.ingest_docs

# Task 0.5 side-by-side stores (do not overwrite baseline unless intended)
uv run python -m evals.scripts.ingest_docs \
  --model BAAI/bge-base-en-v1.5 \
  --db evals/store/auth0_chunks_bge_base.sqlite

uv run python -m evals.scripts.ingest_docs \
  --model BAAI/bge-base-en-v1.5 \
  --chunk-tokens 256 \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite

uv run python -m evals.scripts.smoke_retrieve --db evals/store/auth0_chunks_bge_base_c256.sqlite
# Best measured config (task 0.6): dense_weight=2
uv run python -m evals.runners.retrieval \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite --dense-weight 2
uv run python -m evals.scripts.analyze_first_stage \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite \
  --out evals/reports/first_stage_audit_c256.json
```

Ingest writes SQLite plus a meta sidecar (`ingest_meta.json` for the default DB, or
`{stem}_meta.json` for alternate `--db` paths). The runner/smoke path load meta from the opened
DB first so the query embedder matches the store.

| Artifact | Fingerprint |
|---|---|
| `auth0_chunks.sqlite` | `bge-small-en-v1.5`, 512 / 0.15, 1734 docs / 2688 chunks (task 0.2) |
| `auth0_chunks_bge_base.sqlite` | `bge-base-en-v1.5`, 512 / 0.15, 1734 / 2688 (task 0.5) |
| `auth0_chunks_bge_base_c256.sqlite` | `bge-base-en-v1.5`, **256** / 0.15, 1734 / 4364 (task 0.5); **best with `--dense-weight 2`** (task 0.6, recall@10 **0.368**) |

See [docs/execution/test_evidence.md](../../../docs/execution/test_evidence.md).
