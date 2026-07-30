# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.2 — Ingest Auth0 docs into a local chunk/embed store for hybrid retrieval experiments
**Started:** 2026-07-30
**Status:** not started

## Prior task closed

**0.1 — Auth0 proxy corpus + golden set** — done 2026-07-30. See [work_log.md](work_log.md).

### 0.1 Definition of done (closed)

- [x] Product selected (Auth0; Elastic rejected on ToS/licence) — evidenced in work_log
- [x] Documentation fetched (GitHub MIT clone) separated from parse (`fetch_docs.py` / `parse_docs_manifest.py`)
- [x] Forum threads harvested (`fetch_forum.py` → `corpus/auth0/forum/raw/`)
- [x] `backend/evals/datasets/retrieval_golden.jsonl` — **382 answerable** (+ 35 unanswerable)
- [x] ≥30 unanswerable included
- [x] 20 pairs spot-checked — 18/20 pass ([../../backend/evals/datasets/spot_check.md](../../backend/evals/datasets/spot_check.md))
- [x] Licence/ToS check recorded ([../../backend/evals/corpus/auth0/licence_notes.md](../../backend/evals/corpus/auth0/licence_notes.md))

## Why 0.2 next

The golden set labels (question → gold doc). Stage 0 still needs chunking, embeddings, hybrid
retrieval, and metric runners before the recall@10 / MRR gate can be measured.

## Definition of done (0.2 — draft)

- [ ] Chunk Auth0 docs (~512 tokens, ~15% overlap) from the fetched corpus
- [ ] Embed chunks; store locally for Stage 0 (Postgres+pgvector or equivalent harness DB)
- [ ] Cover both MIT GitHub articles and, where feasible, gold URLs that only exist on
      auth0.com/docs (synthetic `auth0-url-*` ids in the golden set)
- [ ] Smoke: retrieve for a handful of golden questions returns the gold doc in top-50 before rerank

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on the golden set. No product
code, schema, UI, or integration work starts before it clears.
