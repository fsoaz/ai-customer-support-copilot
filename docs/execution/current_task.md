# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.9 — Ranking path after TinyBERT dead-end (GPU/sampled MiniLM or alt second-stage)
**Started:** 2026-08-04
**Status:** not started (unblocked after 0.8 evidence)

## Prior work closed

**0.8 — Ranking quality (CE over larger pool)** — closed 2026-08-04 (partial metrics; MiniLM aborted).
See [work_log.md](work_log.md) and [test_evidence.md](test_evidence.md).

### Definition of done (0.8)

- [x] Evaluate cross-encoder (or equivalent) rerank over pool ≥100 on remediated golden
- [x] Record recall@10 / MRR vs remediated RRF baseline (0.393 / 0.204)
- [x] State whether gate 0.85 is within reach or needs recalibration / different architecture

### 0.8 outcomes

- Harness: CE now reranks **unique docs** (best RRF chunk text per doc), not raw chunks.
- TinyBERT @100 / @200 unique docs: recall@10 **0.314 / 0.319** — **worse** than RRF **0.393**.
- MiniLM-L-12 @100: full sweep **stopped** (~3–4h CPU estimate; no metrics).
- **Call:** TinyBERT is a dead end. Gate 0.85 stays; not near-term without a stronger/faster
  second-stage. Do not more TinyBERT pool sweeps. Do not silently lower the gate.

**0.7 — Golden-label remediation (BUG-014) + re-baseline** — done 2026-08-04.
**0.6 — Further first-stage + solvability call** — done 2026-08-02.
**0.5 — bge-base + chunk-256** — done 2026-08-02.
**0.4 — Rerank sweeps** — done 2026-08-02.
**0.3 / 0.2 / 0.1** — done earlier.

## Why 0.9 next

Candidates remain recoverable (`fused_hit@500 ≈ 0.90`) but neither RRF nor TinyBERT ranks them
into top-10 at gate quality. Need either (a) MiniLM/stronger CE with affordable runtime (GPU,
quantized, or n≈50 pilot then full), or (b) a different second-stage (e.g. late-interaction /
listwise) — decide with a cheap pilot before another multi-hour CPU burn.

## Definition of done (0.9)

- [ ] Choose and run one affordable stronger-ranking pilot on remediated golden (document runtime)
- [ ] Record recall@10 / MRR vs RRF 0.393 / 0.204
- [ ] Explicit call: continue toward 0.85, recalibrate gate, or change retrieval architecture

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on the (trusted) golden set.
No product code, schema, UI, or integration work starts before it clears.
