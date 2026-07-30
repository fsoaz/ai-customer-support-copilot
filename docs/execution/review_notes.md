# Review Notes

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Critiques
> here are deliberately blunt because the audience is us.

> Design reviews and the corrections adopted. Preserves *why* the project departs from earlier
> plans, so decisions are distinguishable from accidents twelve months from now.

---

## 2026-07-30 — Review of the original design document

The project's founding design document was a strong pitch and a weak build plan. Nine findings,
each with the correction adopted.

### 1. Layer-first roadmap

**Finding:** Phase 1 was infrastructure, Phase 2 intelligence, Phase 3 agents. Nothing testable
existed until week 8.

**Correction:** Stage-based roadmap where every stage ends in something a human uses or a number
that decides whether to continue. Each stage carries an objective, blocking gate.
→ [../context/roadmap.md](../context/roadmap.md)

### 2. The riskiest assumption was scheduled last

**Finding:** RAG and retrieval landed in weeks 5–8, after four weeks of Zendesk OAuth, webhooks,
Docker, and UI. But plumbing is boring and known-solvable; **retrieval quality is what decides
whether the product is possible at all.**

**Correction:** Stage 0, weeks 1–3, is retrieval only. No product code, no schema, no UI, no
integration. Gate: recall@10 ≥ 0.85, MRR ≥ 0.60. A negative answer costs three weeks instead of
three months.

### 3. No evaluation harness

**Finding:** The largest gap. LangSmith appeared as a bullet under "next steps"; A/B testing landed
in week 12. For an LLM product this means every prompt change is a blind deploy — there is no way
to tell whether a tweak helped or destroyed quality.

**Correction:** `backend/evals/` exists from Stage 0, before any product code. Golden sets for
retrieval, generation, and redaction; metrics diffed against a stored baseline; CI runs it on any PR
touching `ai/`, `prompts/`, or `ingest/`. **Evals are the test suite.**
→ [../standards/testing.md](../standards/testing.md)

### 4. Over-engineered for zero users

**Finding:** Kafka, Kubernetes, ArgoCD, Celery, Redis Cluster, MinIO, Pinecone, LangGraph,
multi-tenancy, and a fine-tuning pipeline — a 9-person infrastructure bill for a product with no
users, to be operated by one person.

**Correction:** Postgres does queueing (`SKIP LOCKED`), events, and vectors (pgvector). One Fly.io
container. No cache until something is measurably slow. Every deferral carries a documented revisit
trigger, so this is a decision rather than an omission.
→ stack table in [../context/architecture.md](../context/architecture.md)

### 5. Four retrofit landmines in the data model

**Finding and correction:**

| Landmine | Correction |
|---|---|
| No `tenant_id` on any table | On every table from migration 1, with RLS policies carrying both `using` and `with check` |
| No prompt/model provenance on suggestions | `prompt_version`, `model_id`, `retrieved_chunk_ids`, `cited_chunk_ids`, token counts, `cost_usd`, `latency_ms` — none reconstructable later |
| `agent_accepted` as a boolean | Replaced by `agent_action` + `sent_content` + `edit_distance_ratio`. A boolean cannot distinguish "95% right" from "rewritten from scratch", discarding the highest-value quality signal in the system |
| No webhook idempotency key | `ticket_events` with `unique (provider, external_event_id)`. Helpdesk webhooks duplicate and arrive out of order as normal behaviour |

Also corrected: embeddings were specified on both `knowledge_base` and `kb_chunks`. A
document-level embedding is a meaningless average of its parts — dropped. Added `embedding_model`
and `embedding_dim` so a re-embedding migration can run both generations side by side instead of
requiring a hard cutover.

### 6. Retrieval was dense-only

**Finding:** Vector search alone, with no lexical component and no reranking. Support corpora are
dense with error codes, product names, API identifiers, and version strings — exactly the
low-frequency tokens dense embeddings blur together.

**Correction:** Hybrid — pgvector cosine plus Postgres `tsvector`, fused with RRF, then
cross-encoder rerank of top ~50 → top ~8. Plus a confidence threshold and an explicit refusal path.

### 7. PII redaction treated as a policy decision

**Finding:** Listed in the design-decisions table, with no owning component, no tests, and no
failure mode analysis.

**Correction:** A pipeline stage (`app/ai/redact.py`) with its own golden set, scored in **both**
directions. Under-redaction is a compliance failure; over-redaction strips the context that makes a
ticket answerable, and is the direction people forget to measure.

### 8. Metrics were unmeasurable, and inflated

**Finding:** "Resolution time ↓ 30–40%", "cost per ticket ↓ 20–35%" — with no baseline capture
anywhere in the plan, and no control group. These are sales figures.

**Correction:** Plan against **10–20% handle-time reduction on KB-covered tickets**; treat anything
more as upside. Baseline capture is a required, blocking step of Stage 2, before suggestions are
enabled for any tenant. Also recorded: KB coverage, not model quality, is the limiting factor — so
gap detection eventually matters more than prompt tuning.

### 9. Chrome extension as the agent UI

**Finding:** A distribution trap for SaaS. Extensions require per-customer installation, store
review, and browser-vendor policy compliance.

**Correction:** Zendesk Apps Framework v2 sidebar iframe. Installs per-tenant from the marketplace,
no store review, no install friction.

### Minor corrections

- **Stale model list.** GPT-4o, Claude 3.5 Sonnet, and Gemini 1.5 Pro were already superseded.
  Recorded as a standing rule: treat any model list in a document as stale, pin explicit versioned
  IDs in configuration, never point at a floating alias, and re-check at every stage gate.
- **Schema-per-tenant multi-tenancy.** Multiplies migration work by tenant count — untenable solo,
  and unnecessary on Supabase. Replaced with row-level `tenant_id` + RLS.
- **LangGraph in Phase 1.** V1 is a linear pipeline; a graph framework adds indirection with no
  pause/resume to justify it. Deferred to Stage 4, where human-in-the-loop actions need durable
  pause/resume — which is the case it is actually good at.
- **Three frontends at once.** Cut to one agent UI for V1; the admin dashboard arrives in Stage 3
  and the customer widget is not scheduled.
- **Timeline.** 16 weeks assumed 7–9 people. Solo, Stages 0–3 are roughly six months. Recorded
  honestly, because a schedule nobody believes is a schedule whose gates get waived.

### Findings accepted without change

The original document was right about: FastAPI and async Python; abstracting the LLM provider behind
a router; cheap models for classification and expensive ones for generation; human-in-the-loop for
actions; rule-based fallback when the model fails; RAG grounding with citation links as the
hallucination defence; and streaming plus caching as the latency answer. These carried forward
intact.
