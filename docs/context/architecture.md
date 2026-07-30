# Architecture

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things. Every number here is internal planning, never a claim made to anyone outside.

> *What* and *why* live in [product.md](product.md). *When* lives in [roadmap.md](roadmap.md).
> This document is *how*.

## Shape

```
Zendesk sidebar app (ZAF v2 iframe)     Next.js admin dashboard (Vercel)
                │                                    │
                └──────────────┬─────────────────────┘
                               │  Supabase-issued JWT
                    ┌──────────▼───────────┐
                    │  FastAPI (Fly.io)    │  one container
                    │  api / ai / ingest   │  + worker entrypoint
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Supabase Postgres   │  pgvector · tsvector
                    │  RLS on every table  │  queue · events
                    └──────────────────────┘
```

Two deploy targets: Fly.io (backend + worker) and Vercel (Next.js). One database. One identity
provider.

## Stack decisions

Each row records what we do *now* and the **trigger** that says revisit it. A stack table without
rationale becomes cargo cult within a month.

| Concern | Decision | Instead of | Why now | Revisit when |
|---|---|---|---|---|
| Backend | FastAPI, single container on Fly.io | Kubernetes + ArgoCD | One developer cannot operate a cluster and build a product | >3 independent services, or a contractual SLA |
| Frontend | Next.js App Router on Vercel | — | Admin dashboard and marketing site | — |
| Agent UI | Zendesk Apps Framework v2 sidebar iframe | Chrome extension | Extensions need per-customer install and store review; ZAF installs per-tenant from the marketplace | Never for SaaS. Extensions only for an internal deployment |
| Database | Supabase Postgres 15+ | — | Managed, pgvector included, RLS and auth in the box | — |
| Vector store | pgvector, HNSW index | Pinecone / Weaviate | One datastore, transactional consistency with the rest of the data, no extra bill | >5M chunks, or p95 vector search >200 ms |
| Full-text | Postgres `tsvector` + GIN | Elasticsearch | Half of hybrid retrieval, free with the DB | Vector+FTS fusion stops being enough |
| Background jobs | Postgres table, `FOR UPDATE SKIP LOCKED`, same image with a worker entrypoint | Celery + Redis | Zero extra infrastructure; Postgres handles thousands of jobs/min comfortably | Job throughput causes visible table contention |
| Events | `ticket_events` table | Kafka / RabbitMQ | We have no throughput problem and no second consumer | A real second consumer exists, or >1k events/s sustained |
| Cache | None | Redis Cluster | Nothing is measurably slow yet | p95 latency budget breached and profiling blames repeated reads. Then Upstash Redis via Vercel Marketplace |
| Object storage | Supabase Storage | MinIO / S3 | Already provisioned | Storage cost or egress becomes material |
| Auth | Supabase Auth, asymmetric signing keys; FastAPI validates via JWKS | FastAPI Users / Auth0 | One IdP that both Next.js and FastAPI trust — this is what removes the cross-service JWT bridge | Enterprise SSO requirements exceed Supabase Auth |
| Multi-tenancy | Row-level `tenant_id` + RLS, from migration 1 | Schema-per-tenant | Schema-per-tenant multiplies migration work by tenant count — untenable solo | Regulatory demand for physical isolation. Then: dedicated project per tenant, not schemas |
| Orchestration | Plain async Python functions | LangGraph | V1 is a linear pipeline. A graph framework adds indirection with no pause/resume to justify it | Stage 4, when human-in-the-loop actions need durable pause/resume |
| LLM access | Thin internal router module | LangChain | We need model selection, retries and cost accounting — roughly 200 lines | Never, unless a specific integration is cheaper to adopt than write |
| Observability | Langfuse + OpenTelemetry | LangSmith only | LLM tracing plus ordinary app tracing in one story; self-hostable | — |
| PII | Presidio-based redaction stage with its own golden set | A policy statement | Redaction is a component with tests and failure modes, not a decision | — |

## Authentication and tenant scoping

Supabase Auth issues the JWT. Next.js consumes it through `@supabase/ssr`. FastAPI validates it
against the project's JWKS endpoint using asymmetric signing keys.

The claim set carries `sub` (user) and `tenant_id`. `tenant_id` is written into the token via a
Supabase Auth hook at issuance; it is **never** read from a request body or header.

### RLS is inert unless the backend cooperates

A connection using the `service_role` key bypasses RLS entirely. If FastAPI holds that key and
queries freely, the RLS policies are decoration.

Every request-scoped transaction must therefore adopt the caller's identity:

```sql
begin;
  set local role authenticated;
  set local request.jwt.claims = '{"sub":"...","tenant_id":"..."}';
  -- all query work happens here, with policies enforced
commit;
```

This is wrapped in a single FastAPI dependency that yields a scoped `AsyncSession`. Route handlers
never open sessions themselves.

A separate `service_role` connection pool exists and is used by exactly two things: **migrations**
and the **background worker** (which sets `tenant_id` explicitly per job).

The point is defence in depth: with RLS enforced at the database *and* tenant filtering in the
repository layer, a cross-tenant leak requires two independent bugs rather than one. See the
mandatory isolation test in [../standards/testing.md](../standards/testing.md).

## Retrieval

The original design specified vector search alone. That is a mistake for this domain.

Support corpora are dense with **error codes, product names, API identifiers, and version
strings** — exactly the low-frequency tokens dense embeddings blur together. A customer quoting
`ERR_QUOTA_4029` needs lexical matching; a customer describing the same problem in prose needs
semantic matching. Serving both requires both.

```
query
  ├─ dense:   pgvector cosine over kb_chunks.embedding      → top 50
  └─ lexical: tsvector/GIN over kb_chunks.content_tsv       → top 50
                          │
                    RRF fusion                              → top 50
                          │
                 cross-encoder rerank                       → top 8
                          │
                 confidence threshold ──► below? refuse, do not draft
                          │
                 draft generation with mandatory citations
```

- **Chunking** starts at ~512 tokens with ~15% overlap, tuned empirically in Stage 0.
- **Reciprocal Rank Fusion** combines the two result sets without needing calibrated scores across
  retrievers.
- **Reranking** with a cross-encoder is the single largest recall-precision win available and costs
  one extra API call per query.
- **The refusal path is a feature.** Below threshold we return "insufficient knowledge" rather than
  an ungrounded draft. See [../standards/ai_agent_rules.md](../standards/ai_agent_rules.md).

## Data model

Corrects four retrofit landmines in the original schema. All four are cheap now and brutal later.

### 1. `tenant_id` on every table, from migration 1

Even while a single tenant exists. Adding a scoping column to a populated production database, and
backfilling every foreign-key path correctly, is a multi-day outage risk. Adding it now costs
nothing.

```sql
create table tenants (
  id         uuid primary key default gen_random_uuid(),
  name       text not null,
  plan       text not null default 'trial',
  created_at timestamptz not null default now()
);

create table users (
  id         uuid primary key references auth.users(id),
  tenant_id  uuid not null references tenants(id),
  email      text not null,
  role       text not null default 'agent',   -- 'agent' | 'admin' | 'owner'
  created_at timestamptz not null default now()
);
```

### 2. Embeddings live on chunks, with model and dimension recorded

The original schema put an `embedding_vector` on both `knowledge_base` and `kb_chunks`. A
document-level embedding is a meaningless average of its parts — drop it.

Recording `embedding_model` and `embedding_dim` is what makes re-embedding survivable: a migration
to a new embedding model writes new rows alongside the old, retrieval is cut over, and only then
are the old rows dropped. Without these columns the migration is a hard cutover with downtime.

```sql
create table knowledge_base (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id),
  title       text not null,
  source_type text not null,             -- 'upload' | 'confluence' | 'notion' | 'sitemap'
  source_url  text,
  content     text not null,
  content_hash text not null,            -- skip re-embedding unchanged documents
  last_synced timestamptz,
  created_at  timestamptz not null default now(),
  unique (tenant_id, source_type, source_url)
);

create table kb_chunks (
  id              uuid primary key default gen_random_uuid(),
  tenant_id       uuid not null references tenants(id),
  kb_id           uuid not null references knowledge_base(id) on delete cascade,
  chunk_index     int  not null,
  content         text not null,
  content_tsv     tsvector generated always as (to_tsvector('english', content)) stored,
  embedding       vector(1536),
  embedding_model text not null,
  embedding_dim   int  not null,
  created_at      timestamptz not null default now()
);

create index kb_chunks_embedding_idx on kb_chunks using hnsw (embedding vector_cosine_ops);
create index kb_chunks_tsv_idx       on kb_chunks using gin  (content_tsv);
create index kb_chunks_tenant_idx    on kb_chunks (tenant_id);
```

### 3. Suggestions carry full provenance and cost

None of this can be reconstructed after the fact. A quality regression is only attributable if the
prompt version, model, and retrieved context were recorded at the time.

```sql
create table ai_suggestions (
  id                  uuid primary key default gen_random_uuid(),
  tenant_id           uuid not null references tenants(id),
  ticket_id           uuid not null references tickets(id),
  kind                text not null,               -- 'draft' (V1) | 'triage' | 'summary'
  content             text not null,

  -- provenance: what produced this, exactly
  prompt_version      text not null,               -- content hash of the prompt template
  model_id            text not null,
  retrieved_chunk_ids uuid[] not null,
  cited_chunk_ids     uuid[] not null,

  -- economics
  prompt_tokens       int  not null,
  completion_tokens   int  not null,
  cost_usd            numeric(10,6) not null,
  latency_ms          int  not null,

  -- outcome: not a boolean
  agent_action        text,                        -- 'sent_verbatim'|'edited'|'discarded'|'ignored'
  sent_content        text,
  edit_distance_ratio real,

  created_at          timestamptz not null default now()
);
```

**`edit_distance_ratio` is the highest-value signal in the system.** It is the normalised edit
distance between what we suggested and what the agent actually sent. It is collected for free,
needs no survey, correlates with real quality rather than stated quality, and is the number that
proves ROI to a buyer. The original `agent_accepted boolean` throws all of that away — a draft that
was 95% right and one that was rewritten from scratch both register as "not accepted".

### 4. Webhook idempotency

Helpdesk webhooks duplicate, retry, and arrive out of order. Without a dedupe key we double-suggest
and double-charge.

```sql
create table ticket_events (
  id                uuid primary key default gen_random_uuid(),
  tenant_id         uuid not null references tenants(id),
  provider          text not null,                 -- 'zendesk'
  external_event_id text not null,
  payload           jsonb not null,
  received_at       timestamptz not null default now(),
  processed_at      timestamptz,
  unique (provider, external_event_id)
);

create table tickets (
  id             uuid primary key default gen_random_uuid(),
  tenant_id      uuid not null references tenants(id),
  provider       text not null,
  external_id    text not null,
  subject        text,
  status         text,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  unique (tenant_id, provider, external_id)
);

create table ticket_messages (
  id          uuid primary key default gen_random_uuid(),
  tenant_id   uuid not null references tenants(id),
  ticket_id   uuid not null references tickets(id) on delete cascade,
  author_type text not null,                       -- 'customer' | 'agent'
  content     text not null,
  created_at  timestamptz not null default now()
);
```

### Job queue

```sql
create table jobs (
  id            uuid primary key default gen_random_uuid(),
  tenant_id     uuid not null references tenants(id),
  kind          text not null,                     -- 'ingest_kb' | 'embed_chunks' | 'sync_tickets'
  payload       jsonb not null,
  status        text not null default 'pending',   -- pending|running|done|failed
  attempts      int  not null default 0,
  run_after     timestamptz not null default now(),
  last_error    text,
  created_at    timestamptz not null default now()
);
create index jobs_claim_idx on jobs (status, run_after) where status = 'pending';
```

Claimed with `select ... where status='pending' and run_after <= now() order by run_after
for update skip locked limit 1`. Failures increment `attempts` and set `run_after` to an
exponential backoff.

### RLS policy shape

Applied to every tenant-scoped table:

```sql
alter table kb_chunks enable row level security;

create policy tenant_isolation on kb_chunks
  for all
  using      (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid)
  with check (tenant_id = (auth.jwt() ->> 'tenant_id')::uuid);
```

`with check` is not optional — without it, a tenant can *write* rows belonging to another tenant
even though it cannot read them.

## Repo layout

```
backend/
  app/
    api/v1/           FastAPI routers
    auth/             JWKS validation, tenant-scoped session dependency
    ai/
      router.py       model selection, retries, fallback, cost capture
      retrieval/      dense, lexical, RRF fusion, rerank
      prompts/        versioned templates (content-hashed)
      redact.py       PII detection and redaction
      draft.py        grounded generation, citation extraction and validation
    ingest/           KB connectors, chunking, embedding
    workers/          queue consumer entrypoints
    db/               SQLAlchemy models, repositories
  evals/
    datasets/         golden sets: retrieval, generation, redaction
    runners/          recall@k, MRR, nDCG, LLM judge, groundedness
    reports/          CI-consumable JSON + markdown diff vs baseline
  tests/              unit, integration
supabase/
  migrations/         forward-only SQL migrations
frontend/             Next.js App Router — admin dashboard (Vercel)
zendesk-app/          ZAF v2 sidebar app (static bundle)
docs/                 this documentation
```

## Deferred deliberately

Recorded so that "we forgot" is distinguishable from "we decided":

| Deferred | Until |
|---|---|
| Kafka, Kubernetes, Celery, Redis, MinIO, ArgoCD | The trigger in the stack table fires |
| LangGraph | Stage 4 human-in-the-loop actions |
| Intercom and other providers | Stage 4, after Zendesk is proven |
| Fine-tuning | Never before 100k logged, accepted suggestions exist |
| Schema-per-tenant | A regulatory requirement that RLS cannot satisfy |
