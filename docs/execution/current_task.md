# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.5 — Stronger first-stage retrieval (embedding model / chunking re-ingest)
**Started:** 2026-08-02
**Status:** not started (unblocked after 0.4 sweeps)

## Prior work closed

**0.4 — Rerank path + parameter sweeps** — done 2026-08-02.
See [work_log.md](work_log.md) and [test_evidence.md](test_evidence.md).

- Cross-encoder wired via FlashRank (`--rerank`, default off)
- Best so far: TinyBERT rerank @50 → recall@10 **0.320** · MRR **0.166** (Δ +0.005 / +0.003 vs off)
- Larger candidate pool (k=100) **hurt** slightly
- MiniLM-L-12 @50: killed after ~90 min CPU (~700%); shell exited error; **no metrics**
- Gap to gate remains ~0.53 recall@10 / ~0.43 MRR — bottleneck is first-stage recall
  (`hit_at_any` ≈ 0.57; rerank cannot recover gold outside the candidate pool)

**0.3 — Metric runners + baseline** — done 2026-08-01.
**0.2 — Ingest/embed harness** — done 2026-08-01.
**0.1 — Auth0 proxy corpus + golden set** — done, QA-remediated 2026-07-30.

## Why 0.5 next

Rerank barely moves the gate metrics. ~43% of answerable questions never see the gold doc in the
fused candidate set. Closing the gap requires a stronger bi-encoder and/or chunking changes, which
means re-ingest.

## Definition of done (0.5)

- [ ] Re-ingest with at least one stronger embedding model (e.g. `bge-base-en-v1.5`)
- [ ] Optional: chunk size/overlap variant stored side-by-side or as a tagged DB
- [ ] Full golden-set run (rerank off and on) recorded in [test_evidence.md](test_evidence.md)
- [ ] Quantify whether `hit_at_any` and recall@10 move enough to justify further sweeps

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on the golden set. No product
code, schema, UI, or integration work starts before it clears.
