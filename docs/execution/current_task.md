# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.7 — Golden-label remediation (BUG-014) + re-baseline
**Started:** 2026-08-02
**Status:** not started (unblocked after 0.6 solvability call)

## Prior work closed

**0.6 — Further first-stage + solvability call** — done 2026-08-02.
See [work_log.md](work_log.md) and [test_evidence.md](test_evidence.md).

- Audit: pool@500 `fused_hit` **0.883** but RRF recall@10 stuck ~0.33 → ranking failure
- Complete misses @500: **11.4%**; sample is dominated by BUG-014 first-link noise
- Sweeps: BGE query prefix / lex-heavy / pool@200 all flat or worse; **dense_weight=2** →
  recall@10 **0.3677** (new best, still FAIL)
- **Call:** gate not reachable without golden remediation — stop pure embedder sweeps

**0.5 — bge-base + chunk-256** — done 2026-08-02.
**0.4 — Rerank sweeps** — done 2026-08-02.
**0.3 / 0.2 / 0.1** — done earlier.

## Why 0.7 next

Measured recall treats wrong golds as retrieval misses. Spot-check noise (~20%) plus the
complete-miss sample (SMTP→allowlist, viewport→text elements, B2B arch→subscriptions, etc.)
means we are optimizing against a contaminated target. Fix labels, then re-measure on the same
best store (`bge-base` c256, dense_weight=2).

## Definition of done (0.7)

- [ ] Re-judge a substantial slice of answerable pairs (prioritize complete misses + low-rank hits)
- [ ] Update `retrieval_golden.jsonl` (and/or `build_golden` gold selection) so gold = answering doc
- [ ] Re-run full retrieval on remediated set with best config; record in test_evidence
- [ ] State whether gate 0.85 is now a credible target or must be recalibrated

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on the (trusted) golden set.
No product code, schema, UI, or integration work starts before it clears.
