# ai-customer-support-copilot

A customer-support copilot in development. The planned product reads a Zendesk ticket, retrieves
from the company's knowledge base, and drafts a reply where **every factual claim carries a
citation** back to its source. A support agent reviews the draft before sending it; acceptance,
edits, and dismissals will be measured.

Multi-tenant SaaS. Built solo.

## Status

**Pre-product: Stage 0 — prove retrieval.** This repository currently runs a local retrieval
evaluation harness. Product API, draft generation, tenant isolation, and UI are not implemented.

Latest recorded evidence (2026-08-04), after golden-label remediation:

| Metric | Best recorded baseline | Stage 0 gate |
|---|---|---|
| recall@10 | 0.3927 | ≥ 0.85 |
| MRR | 0.2037 | ≥ 0.60 |

**The gate still fails.** These are internal measurements on the Auth0 proxy corpus, not product
benchmarks. The baseline uses `BAAI/bge-base-en-v1.5`, 256-token chunks, and hybrid retrieval with
reciprocal rank fusion (RRF), dense weight 2, and no reranker. The remediated golden set contains
354 answerable and 36 unanswerable questions; only answerable questions contribute to recall/MRR.

Tasks 0.1–0.7 are complete; 0.8 closed with partial evidence. TinyBERT reranking degraded quality,
and the full MiniLM run was stopped without metrics. Task **0.9** is next: an affordable pilot of
a stronger ranking approach. Product work waits until both gate thresholds pass.

See [current task](docs/execution/current_task.md) for live status and
[test evidence](docs/execution/test_evidence.md) for configurations and recorded results.

## Run the local evaluation harness

### Prerequisites

- Python **3.12+** (the repository pins 3.12 in `backend/.python-version`).
- `uv` installed and available on your PATH, plus Git for fetching the corpus.
- Network access for dependency installation, the pinned Auth0 docs clone, and initial model
  downloads. Cached models and the local corpus are reused on subsequent runs.

The baseline workflow requires no API keys, hosted database, or cloud accounts. It runs on CPU;
full ingestion and evaluation can take substantial time. The recorded bge-base/256 ingestion
took about 2.6 hours on the original machine; runtime varies by hardware.

### Install and build the index

From the repository root:

```bash
cd backend
uv sync --locked

# Fetch the Auth0 docs at the committed SHA in expected_commit.txt.
uv run python -m evals.scripts.fetch_docs

# Build the index used by the best recorded baseline.
uv run python -m evals.scripts.ingest_docs \
  --model BAAI/bge-base-en-v1.5 --chunk-tokens 256 \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite
```

The manifest and remediated golden set are already committed; rebuilding the forum dataset is
not required. Ingestion resets the selected store by default. Keep the explicit `--db` path in
subsequent commands: omitting it selects the separate default bge-small store.

### Check retrieval and measure quality

Run from `backend/` after ingestion:

```bash
# Check corpus coverage and retrieval on a small sample.
uv run python -m evals.scripts.smoke_retrieve \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite

# Evaluate the full golden set with the recorded baseline configuration.
uv run python -m evals.runners.retrieval \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite --dense-weight 2

# Optional: inspect candidate-pool coverage and retrieval misses.
uv run python -m evals.scripts.analyze_first_stage \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite \
  --out evals/reports/first_stage_audit.json
```

The runner prints recall, MRR, nDCG, and gate results, and writes JSON reports to
`backend/evals/reports/`, including `retrieval_latest.json`. **A completed run exits successfully
even when the quality gate fails**; check `gate.stage0_pass` in the report. Passing the smoke
check does not mean the Stage 0 gate passes.

Raw corpus clones, SQLite stores, and generated reports are gitignored. Corpus provenance and
usage notes live in [licence_notes.md](backend/evals/corpus/auth0/licence_notes.md).

## Development checks

From `backend/`:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Unit tests check harness behavior; retrieval changes also require a full evaluation against the
golden set. Record configurations and results in
[test_evidence.md](docs/execution/test_evidence.md).

## Repository layout

```text
backend/
  pyproject.toml · uv.lock   Python project and locked dependencies
  evals/
    harness/                Chunking, embeddings, SQLite/FTS5, retrieval, metrics
    scripts/                Corpus fetch, ingestion, diagnostics, dataset tooling
    runners/                Golden-set evaluation
    corpus/                 Corpus metadata and local raw downloads
    datasets/               Golden questions and remediation artifacts
    store/ · reports/       Generated local indexes and evaluation output
  tests/                    Unit tests
docs/                       Internal planning, standards, decisions, and evidence
```

## V1 scope

Grounded draft replies with citations, delivered in a Zendesk sidebar. That is the whole product.

Triage, summarisation, self-service widgets, agentic actions, and analytics are explicitly deferred
until the wedge has paying tenants — see the non-goals in
[docs/context/product.md](docs/context/product.md).

## Stack: current and planned

**Implemented for Stage 0:** Python, uv, FastEmbed embeddings, NumPy dense search, SQLite FTS5
lexical search, weighted RRF, and optional FlashRank cross-encoder reranking. Tests use pytest;
linting and formatting use Ruff.

**Planned product architecture** (not yet implemented):

| Layer | Choice |
|---|---|
| Backend | FastAPI, single container on Fly.io |
| Database | Supabase Postgres 15+ — pgvector, tsvector, RLS, job queue |
| Auth | Supabase Auth; FastAPI validates via JWKS |
| Retrieval | Hybrid: dense + lexical, RRF fusion, cross-encoder rerank |
| Agent UI | Zendesk Apps Framework v2 sidebar |
| Admin UI | Next.js App Router on Vercel |
| Observability | Langfuse + OpenTelemetry |

No Kafka, no Kubernetes, no Celery, no separate vector database. Each of those is deferred with a
documented trigger to revisit in
[docs/context/architecture.md](docs/context/architecture.md).

## Documentation

> **`docs/` is local records only.** An internal working notebook — planning, decisions, standards,
> and measurements. It is never published, shipped, embedded in the product, or shared with
> customers, prospects, or any external party. Nothing in it is product documentation, an API
> contract, a benchmark claim, or a commitment to anyone outside this repo.

```
docs/
  context/     product.md · architecture.md · roadmap.md · structure.md
  standards/   conventions.md · api_rules.md · testing.md · ai_agent_rules.md
  execution/   current_task.md · work_log.md · review_notes.md · test_evidence.md
               qa_report_stage0.md
```

Reading order for anyone working on this repo: [product.md](docs/context/product.md) →
[roadmap.md](docs/context/roadmap.md) → [architecture.md](docs/context/architecture.md) →
[structure.md](docs/context/structure.md) (what exists on disk today).

## Operating principles

1. **Slice, don't layer.** Every stage ends in something a human uses or a number that decides
   whether to continue.
2. **The riskiest assumption goes first.** Retrieval quality decides whether the product is
   possible. It is answered in weeks 1–3, offline, with no UI.
3. **Evals are the test suite.** A prompt or retrieval change shipped without an eval run is an
   untested deploy.
4. **Boring infrastructure until measured pain.** Every deferral records its revisit trigger.
5. **Retrofit-hostile things go in on commit 1** — `tenant_id`, RLS, prompt and model provenance,
   per-call cost accounting, webhook idempotency.

## Licence

See [LICENSE](LICENSE).
