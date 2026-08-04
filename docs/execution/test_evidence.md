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
**Dataset:** `backend/evals/datasets/retrieval_golden.jsonl` (354 answerable + 36 unanswerable after 0.7)
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

**Status:** task 0.8 paused/closed on available evidence; Stage 0 gate **not** cleared. TinyBERT CE
over pool≥100 **hurts** vs remediated RRF. MiniLM full sweep **aborted** (CPU ~3–4h; stopped).
Best measured: remediated RRF dense_w=2 recall@10 **0.393** / MRR **0.204**.

**Diagnosis (2026-08-01 FAIL):** Pre-rerank hybrid with `bge-small-en-v1.5` recovers the gold doc
in top-10 for only ~31% of answerable questions. Smoke hit@50 (60%) overstated gate readiness.
Unanswerable mean top1 RRF 0.0298 (excluded from gate metrics).

### Task 0.8 (2026-08-04) — CE rerank over larger pool (remediated golden)

Store: `auth0_chunks_bge_base_c256.sqlite`. First-stage dense_w=2. CE scores **unique docs**
(highest-RRF chunk text per doc) — see `retrieve.py` Task 0.8 change (`rerank.unit=unique_docs`).

Baseline to beat: remediated RRF dense_w=2 pool@50 → recall@10 **0.3927** / MRR **0.2037**.

| Date | Commit | Config | recall@10 | MRR | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-04 | `83e583d`+wip | RRF dense_w=2 (0.7 re-baseline) | **0.3927** | **0.2037** | FAIL | control |
| 2026-08-04 | `83e583d`+wip | TinyBERT CE @100 unique docs | 0.3136 | 0.1716 | FAIL | **hurts** Δ −0.079 |
| 2026-08-04 | `83e583d`+wip | TinyBERT CE @200 unique docs | 0.3192 | 0.1717 | FAIL | **hurts**; larger pool ≠ rescue |
| 2026-08-04 | `83e583d`+wip | MiniLM-L-12 CE @100 | — | — | — | **aborted** — est. ~3–4h CPU; stopped on request; no metrics |

Timing probe (n=5, before abort): MiniLM ~31–39s/q → full set ~3–4h on this machine.

**Gate credibility call:** FlashRank **TinyBERT is not a path to 0.85** on this corpus — it
degrades ranking vs RRF. Stronger CE (MiniLM) remains **unmeasured** at full-set scale under CPU
budget. `fused_hit@500 ≈ 0.90` still says candidates exist; ranking quality is unsolved.
Do **not** lower the gate on this evidence alone. Next ranking work needs either faster CE infra
(GPU / quantized / sampled pilot before full) or a different second-stage approach — not more
TinyBERT pool sweeps.

Reports: `retrieval_c256_d2_tiny_p100_*.json`, `retrieval_c256_d2_tiny_p200_*.json`.

### Task 0.7 (2026-08-04) — golden-label remediation re-baseline (BUG-014)

**RE-BASELINE** after remediating `retrieval_golden.jsonl` (20 relabeled, 5 → unanswerable,
133 confirmed on triage queue; answerable n **359 → 354**). Same store/config as 0.6 best:
`bge-base` c256, `dense_weight=2`. Sidecar: `retrieval_golden_pre_remediation.jsonl`.

| Date | Commit | Config | recall@10 | MRR | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-02 | `2f20435`+wip | c256 dense_w=2 (pre-remediation) | 0.3677 | 0.1923 | FAIL | prior best |
| 2026-08-04 | `83e583d`+wip | **c256 dense_w=2 remediated** | **0.3927** | **0.2037** | FAIL | **re-baseline**; Δ +0.025 / +0.011 |

First-stage audit post-remediation (`first_stage_audit_c256_remediated.json`):

| Pool k | dense_hit | lexical_hit | fused_hit | recall@10 (RRF) |
|---|---|---|---|---|
| 50 | 0.588 | 0.421 | 0.593 | 0.376 |
| 100 | 0.684 | 0.559 | 0.669 | 0.356 |
| 200 | 0.777 | 0.655 | 0.782 | 0.350 |
| 500 | 0.825 | 0.760 | **0.898** | 0.356 |

Channel @500: neither **0.099** (35 complete misses, was 41). `fused_hit@500` **0.898**.

**Gate credibility call:** **0.85 / 0.60 is still not a near-term target on RRF alone.** Label
remediation helped modestly (+2.5pp recall@10) but the gap remains ~**0.46** recall@10 /
~**0.40** MRR. Candidates are retrievable (`fused_hit@500 ≈ 0.90`); **ranking is the bottleneck**.
Do not recalibrate the gate down yet — try stronger ranking (larger pool + cross-encoder) first.
Do **not** resume pure embedder sweeps.

Reports: `retrieval_c256_dense2_remediated_*.json`, `first_stage_audit_c256_remediated.json`.

### Task 0.6 (2026-08-02) — first-stage audit + fusion/prefix sweeps

Store: `auth0_chunks_bge_base_c256.sqlite` (prior best). New knobs: `--bge-query-prefix`,
`--dense-weight` / `--lexical-weight`, pool size. Audit:
`evals.scripts.analyze_first_stage` → `evals/reports/first_stage_audit_c256.json`.

**Pool / channel audit (max_k=500):**

| Pool k | dense_hit | lexical_hit | fused_hit | recall@10 (RRF) |
|---|---|---|---|---|
| 50 | 0.557 | 0.393 | 0.560 | 0.357 |
| 100 | 0.655 | 0.524 | 0.638 | 0.332 |
| 200 | 0.752 | 0.624 | 0.758 | 0.326 |
| 500 | 0.802 | 0.733 | **0.883** | 0.332 |

Channel @500: both 0.649 · dense_only 0.153 · lexical_only 0.084 · **neither 0.114** (41 complete misses).

**Sweep results (vs c256 RRF baseline recall@10 0.3565):**

| Date | Commit | Config | recall@10 | MRR | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-02 | `2f20435`+wip | c256 RRF baseline (0.5) | 0.3565 | 0.1837 | FAIL | prior best |
| 2026-08-02 | `2f20435`+wip | + BGE query prefix | 0.3426 | 0.1801 | FAIL | slightly worse |
| 2026-08-02 | `2f20435`+wip | dense_w=1 lex_w=2 | 0.2925 | 0.1635 | FAIL | lexical-heavy hurts |
| 2026-08-02 | `2f20435`+wip | **dense_w=2 lex_w=1** | **0.3677** | **0.1923** | FAIL | **best to date** |
| 2026-08-02 | `2f20435`+wip | pool dense/lex=200 | 0.3259 | 0.1829 | FAIL | larger pool ≠ better @10 |

**Best config to date:** `bge-base` + 256-token chunks + RRF with **dense_weight=2**.
**Gap to gate:** recall@10 **0.48** short of 0.85; MRR **0.41** short of 0.60.

**Solvability call (explicit):** Stage 0 gate **0.85 / 0.60 is not reachable on this golden set
without remediation**, for two independent reasons:

1. **Ranking, not only candidate generation.** Expanding the pool to 500 lifts `fused_hit` to
   **0.883**, but RRF `recall@10` stays ~0.33. Bigger first-stage pools alone do not clear the gate.
2. **Label noise (BUG-014).** Spot-check prior **20%** wrong golds; of 12 low-overlap complete
   misses reviewed by hand, most are clear first-link noise (SMTP→allowlist, viewport→text
   elements, B2B architecture→subscriptions, magic-link→refresh tokens). Measured recall treats
   those as retrieval failures.

**Decision:** stop pure embedding-model / fusion sweeps as the primary path. Next task is
**golden-label remediation** (re-judge misses + fix `build_golden` gold selection), then re-measure
on the remediated set. Only then revisit stronger embedders / CE rerank of large pools.

Reports: `first_stage_audit_c256.json`, `retrieval_c256_{bge_prefix,lex2,dense2,pool200}.json`.

### Task 0.5 sweeps (2026-08-02) — bge-base re-ingest + chunk-256

Side-by-side stores (baseline `bge-small` kept). Meta resolved per-DB via SQLite
`ingest_meta_json` / `{stem}_meta.json`. Runner: `uv run python -m evals.runners.retrieval --db …`.

| Date | Commit | Config | recall@10 | MRR | hit_at_any | Pass | Notes |
|---|---|---|---|---|---|---|---|
| 2026-08-02 | `2f20435`+wip | bge-small + TinyBERT @50 (0.4 best) | 0.3203 | 0.1658 | ~0.57 | FAIL | prior best |
| 2026-08-02 | `2f20435`+wip | bge-base 512, RRF only | 0.3315 | 0.1668 | 0.588 | FAIL | Δ +0.011 @10 vs small baseline |
| 2026-08-02 | `2f20435`+wip | bge-base 512 + TinyBERT @50 | 0.3259 | 0.1680 | 0.510 | FAIL | rerank flat/slightly down @10 |
| 2026-08-02 | `2f20435`+wip | **bge-base 256, RRF only** | **0.3565** | **0.1837** | 0.571 | FAIL | **best to date** |
| 2026-08-02 | `2f20435`+wip | bge-base 256 + TinyBERT @50 | 0.3454 | 0.1671 | 0.507 | FAIL | rerank hurts vs off |

**Best config after 0.5 (superseded by 0.6 dense_weight=2):** `BAAI/bge-base-en-v1.5` + 256-token
chunks / 0.15 overlap + hybrid RRF top-50 (no rerank).
**Gap to gate (after 0.5):** recall@10 **0.49** short of 0.85; MRR **0.42** short of 0.60.
**Diagnosis:** stronger bi-encoder + smaller chunks move the needle (~+0.036 recall@10 vs 0.4 best)
but first-stage `hit_at_any` at pool@50 still ≈ 0.57. Rerank still cannot close the gate.
See task 0.6 for the solvability call and current best.

Reports: `evals/reports/retrieval_bge_base_512_*.json`, `…_bge_base_c256_*.json`.

### Task 0.4 sweeps (2026-08-02) — rerank on/off + candidate pool

Same store/fingerprint as 0.2. Runner: `uv run python -m evals.runners.retrieval [--rerank]`.

| Date | Commit | Config | recall@10 | MRR | Pass | Notes |
|---|---|---|---|---|---|---|
| 2026-08-01 | `5eb5097`+wip | RRF only (baseline) | 0.3148 | 0.1625 | FAIL | hit_at_any 0.565 |
| 2026-08-02 | `5eb5097`+wip | + TinyBERT CE @50 | **0.3203** | **0.1658** | FAIL | **best to date**; Δ negligible |
| 2026-08-02 | `5eb5097`+wip | + TinyBERT CE @100 | 0.3036 | 0.1579 | FAIL | denser pool hurt @10 |
| 2026-08-02 | `5eb5097`+wip | MiniLM-L-12 CE @50 | — | — | — | **no metrics** — process killed after ~90 min @ ~700% CPU; shell exited error. Not viable for full-set CPU sweeps |

**0.4 best (superseded by 0.5):** `bge-small` + hybrid RRF top-50 + `ms-marco-TinyBERT-L-2-v2` rerank.
**Diagnosis:** first-stage bottleneck — rerank cannot help when gold is outside the candidate pool.

Reports: `evals/reports/retrieval_rerank_on_k50.json`, `…_k100.json`.

### Task 0.5 ingest fingerprints (2026-08-02)

| Field | bge-base 512 | bge-base 256 |
|---|---|---|
| Store | `auth0_chunks_bge_base.sqlite` | `auth0_chunks_bge_base_c256.sqlite` |
| Embedding | `BAAI/bge-base-en-v1.5` (768-d) | same |
| Chunk / overlap | 512 / 0.15 | 256 / 0.15 |
| Docs / chunks | 1734 / 2688 | 1734 / 4364 |
| Ingest seconds | 4590 | 9464 |
| Corpus commit | `5258d17ede3eea0ed0e330d15f8921a542564f68` | same |

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
