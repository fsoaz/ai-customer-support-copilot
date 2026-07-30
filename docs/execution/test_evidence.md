# Test Evidence

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. These
> numbers are internal measurements against our own golden sets — they are **not** benchmark
> claims, marketing figures, or anything to quote to a prospect.

> Recorded results for every stage gate. Gates are *recorded*, not remembered — a gate whose
> passing nobody can point to did not pass.
>
> Thresholds: [../context/roadmap.md](../context/roadmap.md).
> How they are measured: [../standards/testing.md](../standards/testing.md).

## Rules

- Every gate attempt is recorded, **including failures**. A failed attempt with its diagnosis is the
  most useful row in this file.
- Every row pins the commit SHA, model ID, and prompt version. An unreproducible result is not
  evidence.
- Re-baselining is recorded as its own explicit row stating that it is a re-baseline. Silently
  moving a baseline to make a regression disappear is the worst thing that can be done to this
  file.

## Row format

```markdown
| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
```

Nightly eval runs append here automatically; manual gate attempts are added by hand with a short
diagnosis.

---

## Stage 0 — Prove retrieval

**Gate:** recall@10 ≥ 0.85 · MRR ≥ 0.60
**Dataset:** `backend/evals/datasets/retrieval_golden.jsonl` (target 300–500 pairs, ≥ 30 marked
unanswerable)
**Runner:** `uv run python -m evals.runners.retrieval`

| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
|---|---|---|---|---|---|---|
| — | — | recall@1 | — (reported) | — | — | Not yet run |
| — | — | recall@5 | — (reported) | — | — | Not yet run |
| — | — | recall@10 | ≥ 0.85 | — | — | **Gate metric** |
| — | — | MRR | ≥ 0.60 | — | — | **Gate metric** |
| — | — | nDCG@10 | — (reported) | — | — | Not yet run |

**Configuration to record with each run:** embedding model, chunk size, chunk overlap, RRF weights,
reranker model, top-k before and after rerank.

**Status:** not started. Blocked on task 0.1 — see [current_task.md](current_task.md).

---

## Stage 1 — Grounded generation backbone

**Gate:** groundedness ≥ 0.95 · citation precision ≥ 0.90 · p95 TTFT < 1.5 s · cost/draft < $0.03 ·
cross-tenant isolation test passing

| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
|---|---|---|---|---|---|---|
| — | — | Groundedness | ≥ 0.95 | — | — | LLM judge; judge prompt version must be pinned |
| — | — | Citation precision | ≥ 0.90 | — | — | Catches citing everything retrieved to look grounded |
| — | — | Citation validity | 100% | — | — | Programmatic; hard failure, not a score |
| — | — | Refusal correctness | — (reported) | — | — | Needs the unanswerable subset |
| — | — | p95 TTFT | < 1.5 s | — | — | Streaming; measured end-to-end, not model-only |
| — | — | Cost per draft | < $0.03 | — | — | From `ai_suggestions.cost_usd` |
| — | — | PII recall | — (reported) | — | — | Under-redaction = compliance failure |
| — | — | Over-redaction rate | — (reported) | — | — | The direction people forget to measure |
| — | — | Cross-tenant isolation | pass | — | — | **Non-negotiable, blocking in CI** |

**Status:** not started.

---

## Stage 2 — First real integration

**Gate:** ≥ 40% of drafts sent verbatim or lightly edited (`edit_distance_ratio` < 0.3) over two
weeks of live use · zero cross-tenant incidents

| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
|---|---|---|---|---|---|---|
| — | — | Acceptance rate | ≥ 40% | — | — | Two-week window, live agents, real KB |
| — | — | Cross-tenant incidents | 0 | — | — | |
| — | — | Webhook idempotency | 1 suggestion per duplicated event | — | — | Manual verification, [../standards/testing.md](../standards/testing.md) |

**Baseline capture — required before suggestions are enabled:**

| Metric | Window | Value | Captured |
|---|---|---|---|
| Median handle time | — | — | — |
| First-contact resolution rate | — | — | — |
| Median resolution time | — | — | — |
| Ticket volume | — | — | — |

Without these rows filled in *before* launch, every claim in
[../context/product.md](../context/product.md) is unfalsifiable.

**Expected:** Stage 0 and Stage 1 metrics will drop when the proxy corpus is replaced by the design
partner's real KB. That drop is information, not failure. Record both numbers; recovering them is
the work of this stage.

**Status:** not started.

---

## Stage 3 — Make it a product

**Gate:** 2 paying tenants onboarded with no manual intervention

| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
|---|---|---|---|---|---|---|
| — | — | Self-serve onboarded paying tenants | 2 | — | — | Manual intervention disqualifies the tenant from counting |

**Status:** not started.
