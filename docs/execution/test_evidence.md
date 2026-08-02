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
**Dataset:** `backend/evals/datasets/retrieval_golden.jsonl` (359 answerable + 31 unanswerable)
**Runner:** `uv run python -m evals.runners.retrieval`

| Date | Commit | Metric | Threshold | Measured | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-01 | `5eb5097`+wip | recall@1 | — (reported) | 0.0975 | — | Baseline; no rerank |
| 2026-08-01 | `5eb5097`+wip | recall@5 | — (reported) | 0.2284 | — | Baseline; no rerank |
| 2026-08-01 | `5eb5097`+wip | recall@10 | ≥ 0.85 | **0.3148** | **FAIL** | **Gate metric** — first full run |
| 2026-08-01 | `5eb5097`+wip | MRR | ≥ 0.60 | **0.1625** | **FAIL** | **Gate metric** |
| 2026-08-01 | `5eb5097`+wip | nDCG@10 | — (reported) | 0.1900 | — | Baseline; no rerank |

**Configuration to record with each run:** embedding model, chunk size, chunk overlap, RRF weights,
reranker model, top-k before and after rerank.

**Status:** task 0.4 sweeps done; Stage 0 gate **not** cleared. Next: task 0.5 stronger bi-encoder.

**Diagnosis (2026-08-01 FAIL):** Pre-rerank hybrid with `bge-small-en-v1.5` recovers the gold doc
in top-10 for only ~31% of answerable questions. Smoke hit@50 (60%) overstated gate readiness.
Unanswerable mean top1 RRF 0.0298 (excluded from gate metrics).

### Task 0.4 sweeps (2026-08-02) — rerank on/off + candidate pool

Same store/fingerprint as 0.2. Runner: `uv run python -m evals.runners.retrieval [--rerank]`.

| Date | Commit | Config | recall@10 | MRR | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-01 | `5eb5097`+wip | RRF only (baseline) | 0.3148 | 0.1625 | FAIL | hit_at_any 0.565 |
| 2026-08-02 | `5eb5097`+wip | + TinyBERT CE @50 | **0.3203** | **0.1658** | FAIL | **best to date**; Δ negligible |
| 2026-08-02 | `5eb5097`+wip | + TinyBERT CE @100 | 0.3036 | 0.1579 | FAIL | denser pool hurt @10 |
| 2026-08-02 | `5eb5097`+wip | MiniLM-L-12 CE @50 | — | — | — | **no metrics** — process killed after ~90 min @ ~700% CPU; shell exited error. Not viable for full-set CPU sweeps |

**Best config to date:** `bge-small` + hybrid RRF top-50 + `ms-marco-TinyBERT-L-2-v2` rerank.
**Gap to gate:** recall@10 **0.53** short of 0.85; MRR **0.43** short of 0.60.
**Diagnosis:** first-stage bottleneck — rerank cannot help when gold is outside the candidate pool.
Next leverage is a stronger embedding model / chunking (task 0.5), not a heavier cross-encoder.

Reports: `evals/reports/retrieval_rerank_on_k50.json`, `…_k100.json`.

### Task 0.2 ingest fingerprint (2026-08-01)

| Field | Value |
|---|---|
| Commit pin | `5258d17ede3eea0ed0e330d15f8921a542564f68` |
| Embedding | `BAAI/bge-small-en-v1.5` (384-d, fastembed, L2-normalized) |
| Chunk | 512 whitespace tokens, 0.15 overlap |
| Store | SQLite + FTS5 (`evals/store/auth0_chunks.sqlite`) — 1734 docs / 2688 chunks |
| Coverage | 359/359 answerable `gold_doc_id`s |
| Smoke hit@50 (n=10, pre-rerank) | 6/10 |

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
