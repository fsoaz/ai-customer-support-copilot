# Local Stage 0 chunk/embed store (gitignored contents).

Regenerate after fetching the pinned Auth0 docs corpus:

```bash
cd backend
uv run python -m evals.scripts.fetch_docs       # if raw/ missing
uv run python -m evals.scripts.ingest_docs
uv run python -m evals.scripts.smoke_retrieve
uv run python -m evals.runners.retrieval
uv run python -m evals.runners.retrieval --rerank
```

Artifacts written here: `auth0_chunks.sqlite`, `ingest_meta.json`.

Current fingerprint (task 0.2): `BAAI/bge-small-en-v1.5`, 512-token chunks / 0.15 overlap,
1734 docs / 2688 chunks. See [docs/execution/test_evidence.md](../../../docs/execution/test_evidence.md).
