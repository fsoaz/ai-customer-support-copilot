# Eval reports (generated, gitignored)

```bash
cd backend
uv run python -m evals.runners.retrieval
uv run python -m evals.runners.retrieval --rerank
uv run python -m evals.runners.retrieval --rerank --dense-top-k 100 --lexical-top-k 100
```

Writes timestamped `retrieval_*.json`, optional tagged copies (`retrieval_rerank_on_k50.json`, …),
and `retrieval_latest.json`.
