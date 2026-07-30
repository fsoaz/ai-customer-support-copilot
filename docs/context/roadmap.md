# Roadmap

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things. Every date and estimate here is internal planning, never a commitment made to anyone
> outside.

> Scope and metrics: [product.md](product.md). Technical design: [architecture.md](architecture.md).

## Principles

1. **Slice, don't layer.** Every stage ends with something a human uses or a number that decides
   whether to continue. The original plan built infrastructure for four weeks, then intelligence
   for four more — nothing testable until week eight.
2. **The riskiest assumption goes first.** Plumbing (OAuth, webhooks, containers) is boring and
   known-solvable. Retrieval quality is neither. It is answered in Stage 0, offline, with no UI.
3. **Gates are objective and blocking.** Each stage below ends with a measurable threshold. Failing
   it means iterating within the stage, not proceeding to the next one. A gate that gets waived
   once is not a gate.
4. **Boring infrastructure until measured pain.** Every deferral has a documented revisit trigger
   in [architecture.md](architecture.md).

## Calendar reality

The original plan was 16 weeks. It also assumed 7–9 people. **Stages 0–3 below are roughly six
months of solo full-time work** to a sellable V1. That is the honest number; planning against the
16-week figure guarantees the gates get waived.

---

## Stage 0 — Prove retrieval (weeks 1–3)

No product code. No UI. No integrations. No database schema beyond what the harness needs.

The entire question: **can hybrid retrieval find the right knowledge-base document for a real
support question?** If it cannot, nothing built on top of it matters, and that should cost three
weeks to discover, not three months.

### Work

- Build the proxy corpus (see [The no-data problem](#the-no-data-problem) below).
- Ingestion path: fetch, clean, chunk (~512 tokens, ~15% overlap), embed into `kb_chunks`.
- Hybrid retrieval: pgvector cosine + `tsvector` full-text, fused with RRF, cross-encoder rerank of
  top ~50 → top ~8.
- `backend/evals/` with retrieval metrics: recall@1/5/10, MRR, nDCG.
- Parameter sweep: chunk size, overlap, fusion weights, rerank on/off, embedding model. Every run
  recorded in [../execution/test_evidence.md](../execution/test_evidence.md).

### Gate

| Metric | Threshold |
|---|---|
| recall@10 | **≥ 0.85** |
| MRR | **≥ 0.60** |

Below this, prompt engineering cannot save the product. Keep iterating on retrieval, or conclude
the corpus is unrepresentative and rebuild it.

---

## Stage 1 — Grounded generation backbone (weeks 4–9)

API only. Exercised through pytest and a CLI. Still no UI, still no helpdesk integration.

### Work

- Supabase schema and migrations. `tenant_id` and RLS on every table **in the first migration**.
- Supabase Auth wired up; FastAPI JWKS validation; the tenant-scoped session dependency.
- PII redaction ahead of every LLM call, with a golden set testing both directions —
  over-redaction destroys the context the model needs.
- Draft generation with mandatory inline citations resolving to real `kb_chunks.id` values.
- Refusal path when retrieval confidence falls below threshold.
- LLM router: per-task model selection, retries, rule-based template fallback.
- Provenance, token and cost logging on every call, plus Langfuse tracing.
- Generation evals: groundedness, citation precision, helpfulness, tone.
- CI wired so any PR touching `ai/` or `prompts/` runs the eval suite and posts a diff against the
  stored baseline.

### Gate

| Metric | Threshold |
|---|---|
| Groundedness | **≥ 0.95** |
| Citation precision | **≥ 0.90** |
| p95 time-to-first-token | **< 1.5 s** |
| Cost per draft | **< $0.03** |
| Cross-tenant isolation test | **passing in CI** |

---

## Stage 2 — First real integration (weeks 10–16)

### Work

- Zendesk OAuth, ticket sync, webhook ingestion with `external_event_id` dedupe and replay
  tolerance.
- Zendesk Apps Framework v2 sidebar app: streams the draft, renders citations as links into the KB.
- Capture `agent_action`, `sent_content`, `edit_distance_ratio` on every suggestion.
- **Capture the design partner's baseline metrics before enabling suggestions.** Handle time,
  first-contact resolution, resolution time, over a comparable prior window. Without a pre-period
  baseline every claim in [product.md](product.md) is unfalsifiable.
- Swap the proxy corpus for the design partner's real KB and tickets. Re-run the Stage 0 and
  Stage 1 evals against real data — expect the numbers to drop, and treat recovering them as the
  work of this stage.

### Gate

| Metric | Threshold |
|---|---|
| Drafts sent verbatim or lightly edited (`edit_distance_ratio` < 0.3) | **≥ 40%** over two weeks of live use |
| Cross-tenant data incidents | **zero** |

---

## Stage 3 — Make it a product (weeks 17–24)

The difference between a working system and something a stranger can buy.

### Work

- Self-serve tenant onboarding and KB connector configuration.
- KB connectors beyond single-file upload: Confluence, Notion, sitemap crawl. Scheduled re-sync
  with incremental re-embedding keyed on `content_hash`.
- Next.js admin dashboard: KB management, prompt versions, quality metrics, usage and cost.
- Usage metering per tenant and Stripe billing, keyed to the cost data logged since Stage 1.
- Operational hardening: per-tenant rate limits, circuit breakers on the Zendesk client, structured
  audit logging, GDPR/LGPD data-deletion path.

### Gate

| Metric | Threshold |
|---|---|
| Paying tenants onboarded with no manual intervention from us | **2** |

---

## Stage 4 — Expand (week 25+)

Only now, and only guided by what paying tenants actually ask for. In rough priority order:

- Knowledge-gap detection (highest expected value — see the coverage argument in
  [product.md](product.md))
- Auto-triage: tagging, priority, routing
- Thread summarisation and handoff notes
- LangGraph agentic actions with human-in-the-loop approval
- Manager analytics and quality scoring
- Intercom as a second provider
- Customer-facing self-service widget

Nothing here is scheduled. The gate for starting any of it is a paying tenant asking for it.

---

## The no-data problem

We have no tickets and no knowledge base. Stage 0 nonetheless requires ground truth.

**Do not start with synthetic tickets.** Synthetic questions validated against synthetic answers
produce self-fulfilling evals: the generator and the grader share the same blind spots, the numbers
look excellent, and they predict nothing about real performance.

### Proxy corpus strategy

Pick a public product whose community forum answers link back to its documentation. That link is
free retrieval ground truth.

1. Choose one product with public docs and a public Q&A forum. Discourse instances, Stack Exchange
   tags, and GitHub Discussions all work.
2. Ingest its documentation as the knowledge base.
3. Mine forum threads for real user questions whose accepted answer links to a docs page. **That
   linked page is the gold document.**
4. Target **300–500 pairs** — enough for recall@k and MRR to be statistically meaningful.

This yields genuine user questions, in genuine user phrasing, against genuine documentation, with
zero labelling cost. It is the closest available proxy for the real thing.

Selection criteria for the product: documentation large enough to make retrieval non-trivial
(hundreds of pages), a forum with an accepted-answer mechanism, questions that resemble support
tickets rather than programming puzzles, and terms of use that permit the crawl.

### Secondary corpora

The Twitter Customer Support dataset and the Bitext intent dataset are useful for **tone and intent
calibration only**. Neither carries document-level ground truth, so neither can score retrieval.

### Design partner track — runs in parallel from week 1

The proxy corpus buys enough signal to build against. It does not substitute for one real support
organisation's tickets and knowledge base.

**Finding a design partner is on the critical path, not beside it.** Real data replaces the proxy
corpus at Stage 2, and Stage 2's gate cannot be measured without a live team using the product.
Start the search in week 1, not week 10.

What we need from them: read access to historical tickets, their knowledge base, a Zendesk sandbox,
and 3–5 agents willing to use a beta. What they get: the product free during the pilot and
influence over the roadmap.
