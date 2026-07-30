# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.2 — Ingest Auth0 docs into a local chunk/embed store for hybrid retrieval experiments
**Started:** 2026-07-30
**Status:** not started (unblocked after QA remediation)

## Prior work closed

**0.1 — Auth0 proxy corpus + golden set** — done, then **QA-remediated** 2026-07-30.
See [work_log.md](work_log.md) and [qa_report_stage0.md](qa_report_stage0.md).

### Golden set (post-remediation)

- `backend/evals/datasets/retrieval_golden.jsonl` — **357 answerable** (100% in MIT manifest,
  **0** synthetic) + **31 unanswerable** (25 near-miss + 6 absurdist)
- Spot-check: seeded sample, 16/20 pass — [../../backend/evals/datasets/spot_check.md](../../backend/evals/datasets/spot_check.md)
- Docs pin: `backend/evals/corpus/auth0/docs/expected_commit.txt`

## Why 0.2 next

Labels exist and are gateable (corpus coverage 100%). Stage 0 still needs chunking, embeddings,
hybrid retrieval, and metric runners before recall@10 / MRR can be measured.

## Definition of done (0.2)

- [ ] Chunk Auth0 docs (~512 tokens, ~15% overlap) from the **pinned MIT GitHub** corpus only
- [ ] Embed chunks; store locally for Stage 0 (Postgres+pgvector or equivalent harness DB)
- [ ] Every answerable `gold_doc_id` in the golden set must resolve to an ingested document
      (coverage already 100% at label time — keep it that way after chunk/embed)
- [ ] Smoke: retrieve for a handful of golden questions returns the gold doc in top-50 before rerank

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on the golden set. No product
code, schema, UI, or integration work starts before it clears.
