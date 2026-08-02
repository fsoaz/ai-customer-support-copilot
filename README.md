# ai-customer-support-copilot

A copilot for customer-support agents. It reads the ticket, retrieves from the company's knowledge
base, and drafts a reply where **every factual claim carries a citation** back to the source it came
from. The agent sends it, edits it, or ignores it — and the product measures which.

Multi-tenant SaaS. Built solo.

## Status

**Stage 0 in progress.** Tasks 0.1–0.6 done. Stage 0 gate still **FAIL** — best recall@10 ≈ 0.37
(gap ~0.48). **0.6 call:** golden labels must be remediated before more embedder sweeps
([current_task.md](docs/execution/current_task.md)). Product API/UI intentionally absent.

### Stage 0 harness (local evals only)

```bash
cd backend
uv run python -m evals.scripts.fetch_docs          # pinned Auth0 MIT docs → corpus/.../raw
uv run python -m evals.scripts.ingest_docs         # default: bge-small → evals/store/
# Best store so far (task 0.5): bge-base, 256-token chunks
uv run python -m evals.scripts.ingest_docs \
  --model BAAI/bge-base-en-v1.5 --chunk-tokens 256 \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite
uv run python -m evals.scripts.smoke_retrieve \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite
uv run python -m evals.runners.retrieval \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite --dense-weight 2   # best measured
uv run python -m evals.scripts.analyze_first_stage \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite                   # pool/channel audit
```

Measured results live in [docs/execution/test_evidence.md](docs/execution/test_evidence.md).
Reports under `backend/evals/reports/` are gitignored.

## V1 scope

Grounded draft replies with citations, delivered in a Zendesk sidebar. That is the whole product.

Triage, summarisation, self-service widgets, agentic actions, and analytics are explicitly deferred
until the wedge has paying tenants — see the non-goals in
[docs/context/product.md](docs/context/product.md).

## Stack

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
