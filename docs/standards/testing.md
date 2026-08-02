# Testing

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things.

> Gate thresholds live in [../context/roadmap.md](../context/roadmap.md). Recorded results live in
> [../execution/test_evidence.md](../execution/test_evidence.md).

## The core principle

**Evals are the test suite.** A prompt change, a retrieval parameter change, or a model change
shipped without an eval run is an untested deploy — the fact that pytest is green means nothing,
because unit tests mock the model.

Conventional tests prove the code does what it was written to do. Evals prove the system does what
the product needs. Both are required and neither substitutes for the other.

## Three tiers

| Tier | Scope | Dependencies | Runs |
|---|---|---|---|
| **Unit** | Pure logic — chunking, RRF fusion, citation parsing, redaction rules, cost arithmetic | None. Model calls mocked | Every commit, seconds |
| **Integration** | API routes, repositories, RLS policies, job queue, webhook handling | Real Postgres via testcontainers; model responses from recorded cassettes | Every PR, ~1–2 min |
| **Eval** | Retrieval and generation quality against golden sets | Real models, real embeddings | Nightly, plus PRs touching `ai/`, `prompts/`, or `ingest/` |

### Why ordinary PRs never gate on live frontier-model calls

Cost and flakiness. A suite that costs money and fails randomly on unrelated PRs gets disabled
within a month, and then quality regressions ship unnoticed. Keep the fast path fast and
deterministic; run the expensive path where it earns its cost.

Integration tests use recorded model responses (VCR-style cassettes). Re-record deliberately, in
its own commit, never as a side effect of an unrelated change.

## Eval suite

Lives in `backend/evals/`. Datasets in `evals/datasets/`, runners in `evals/runners/`, output in
`evals/reports/`.

### Retrieval metrics

Scored against the (question → gold document) pairs described in
[../context/roadmap.md](../context/roadmap.md).

| Metric | Question it answers |
|---|---|
| **recall@1 / @5 / @10** | Is the right document retrieved at all? |
| **MRR** | How near the top is it? |
| **nDCG@10** | Is the whole ranking sensible, not just the first hit? |

Report all three. recall@10 alone hides a reranker that is doing nothing.

### Generation metrics

| Metric | How | Notes |
|---|---|---|
| **Groundedness** | LLM judge: is every claim supported by the cited chunks? | Stage 1 gate: ≥ 0.95 |
| **Citation precision** | Programmatic + judge: are cited chunks actually load-bearing? | Stage 1 gate: ≥ 0.90. Catches the model citing everything retrieved to look grounded |
| **Citation validity** | Programmatic: does every ID exist, and is it in `retrieved_chunk_ids`? | Hard failure, not a score. See [ai_agent_rules.md](ai_agent_rules.md) |
| **Helpfulness** | LLM judge against the reference answer | Directional |
| **Tone** | LLM judge against the tenant's voice guidelines | Directional |
| **Refusal correctness** | Does it refuse when the KB genuinely lacks the answer? | Needs deliberate negative examples in the golden set |

The golden set must contain **unanswerable questions**. A system evaluated only on answerable
questions learns to always answer, which is the failure mode that destroys trust in production.

### Redaction metrics

Separate golden set, scored in both directions:

- **Recall on PII** — what fraction of planted PII was caught. Under-redaction is a compliance
  failure.
- **Precision / over-redaction rate** — what fraction of redacted spans were not PII.
  Over-redaction strips the detail that makes a ticket answerable, and it is the direction people
  forget to measure.

### Baselines and reporting

- Each eval run writes JSON to `evals/reports/` plus a markdown diff against the stored baseline.
- CI posts the diff on the PR. **A metric moving down is a blocking review comment**, not an FYI.
- Baselines are re-established only in an explicit, isolated commit that says so. Silently
  re-baselining to make a regression disappear is the single worst thing anyone can do to this
  suite.
- Every run pins model ID, prompt version, and retrieval parameters. An unreproducible eval is not
  evidence.

## Mandatory: cross-tenant isolation test

**Non-negotiable, in CI, blocking.** The whole multi-tenancy design in
[../context/architecture.md](../context/architecture.md) is unverified without it.

```
Seed tenant A and tenant B with disjoint knowledge-base content.
Issue a suggestion request with tenant A's JWT, asking a question that is only
answerable from tenant B's KB.

Assert:
  1. The refusal path fires (insufficient knowledge).
  2. retrieved_chunk_ids contains zero tenant-B chunk IDs.
  3. The response body contains no tenant-B content.
  4. The ai_suggestions row is written with tenant_id = A.

Repeat for: direct GET by tenant-B resource UUID (expect 404, not 403),
KB list, ticket list, and the worker path with an explicit tenant_id.
```

If this test is ever skipped, quarantined, or marked xfail, the build is broken. There is no
version of "temporarily" that applies here.

## CI gates

Every PR:

| Check | Blocking |
|---|---|
| `ruff check` + `ruff format --check` | Yes |
| `mypy` — strict on `app/ai/` and `app/auth/`, standard elsewhere | Yes |
| `pytest -m "not eval"` | Yes |
| Coverage — no decrease against base branch | Yes |
| Cross-tenant isolation test | Yes |
| Migration up, then down, then up against a throwaway Supabase branch | Yes |
| Eval diff vs baseline — when `ai/`, `prompts/`, or `ingest/` changed | Yes, on regression |
| `pnpm lint` + `tsc --noEmit` — when `frontend/` or `zendesk-app/` changed | Yes |

Nightly: full eval suite against live models, results appended to
[../execution/test_evidence.md](../execution/test_evidence.md).

## Verification commands

### Stage 0 — retrieval

```bash
cd backend
# Best store + fusion weights so far (task 0.6):
uv run python -m evals.runners.retrieval \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite \
  --golden evals/datasets/retrieval_golden.jsonl \
  --dense-weight 2 \
  --tag c256_dense2
uv run python -m evals.scripts.analyze_first_stage \
  --db evals/store/auth0_chunks_bge_base_c256.sqlite \
  --out evals/reports/first_stage_audit_c256.json
# gate: recall@10 >= 0.85, MRR >= 0.60
# As of 0.6: gate not credible until BUG-014 golden remediation (task 0.7).
```

### Stage 1 — generation

```bash
docker compose up -d db          # local Postgres + pgvector
supabase db reset                # apply all migrations from scratch
uv run pytest -m "not eval"      # unit + integration
uv run python -m evals.runners.generation
uv run python -m evals.runners.redaction

uv run uvicorn app.main:app --reload
curl -N -X POST localhost:8000/v1/tickets/$TICKET_ID/suggestions \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{"kind":"draft"}'
# assert: every factual claim carries a citation marker resolving to a real kb_chunks row
```

### Stage 2 — integration

```bash
# duplicate webhook delivery must be a no-op
curl -X POST localhost:8000/v1/webhooks/zendesk \
  -H "X-Zendesk-Webhook-Signature: $SIG" -d @fixtures/ticket_created.json
curl -X POST localhost:8000/v1/webhooks/zendesk \
  -H "X-Zendesk-Webhook-Signature: $SIG" -d @fixtures/ticket_created.json

psql "$DATABASE_URL" -c \
  "select count(*) from ai_suggestions where ticket_id = '$TICKET_ID';"
# expect: 1
```

Then install the ZAF app in a Zendesk sandbox and confirm the draft streams, citations link into
the KB, and `agent_action` plus `edit_distance_ratio` are recorded when the agent sends.

## What we deliberately do not test

- Provider SDK internals — mock at our own router boundary.
- Exact generated wording — that is what the eval judges are for. Asserting on model output strings
  produces a suite that fails on every prompt improvement.
- UI pixel rendering. Test behaviour, not appearance.
