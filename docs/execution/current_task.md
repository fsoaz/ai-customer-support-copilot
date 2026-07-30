# Current Task

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Nothing
> here is a commitment to anyone outside — it is a private note-to-self about what is being worked
> on right now.

> One active task at a time. Rewritten as work advances; history goes to [work_log.md](work_log.md).

**Stage:** 0 — Prove retrieval ([../context/roadmap.md](../context/roadmap.md))
**Task:** 0.1 — Select the proxy-corpus product and build the (question → gold doc) extractor
**Started:** 2026-07-30
**Status:** not started

## Why this first

We have no tickets and no knowledge base. Stage 0 must answer one question — *can hybrid retrieval
find the right document for a real support question?* — and it cannot be answered without ground
truth.

Synthetic questions graded against synthetic answers produce self-fulfilling evals: generator and
grader share the same blind spots, the numbers look excellent, and they predict nothing. So the
first task is acquiring real ground truth cheaply.

The strategy: pick a public product whose community forum answers link back to its documentation.
That link is free, genuine retrieval ground truth.

## Definition of done

- [ ] Product selected, with the selection criteria below evidenced in a short note appended to
      [work_log.md](work_log.md)
- [ ] Documentation crawled and stored as raw source (fetch separated from parsing, so parsing can
      be re-run without re-crawling)
- [ ] Forum threads harvested where an accepted answer links to a documentation page
- [ ] `backend/evals/datasets/retrieval_golden.jsonl` written, **300–500 pairs**, schema:
      ```json
      {"id": "...", "question": "...", "gold_doc_url": "...", "gold_doc_id": "...",
       "source_thread_url": "...", "answerable": true}
      ```
- [ ] **At least 30 deliberately unanswerable questions** included with `"answerable": false` —
      questions the docs genuinely do not cover. Without these, the refusal path is untestable and
      the system will learn to always answer
- [ ] 20 pairs manually spot-checked: is the linked page really the answer, or incidental?
- [ ] Corpus licence and terms-of-use check recorded

## Selection criteria for the product

- Public documentation, hundreds of pages — small doc sets make retrieval trivially easy and the
  eval meaningless
- Public forum with an accepted-answer mechanism (Discourse, Stack Exchange tag, GitHub Discussions)
- Questions resembling **support tickets**, not programming puzzles
- Terms of use permitting the crawl
- A domain dense with error codes, identifiers, and version strings — that is what makes hybrid
  retrieval worth proving

## Not in this task

Chunking, embedding, retrieval implementation, and the metric runners are tasks 0.2–0.4. This task
produces the dataset only.

## Blocking gate ahead

Stage 0 does not close until `recall@10 ≥ 0.85` and `MRR ≥ 0.60` on this golden set. No product
code, schema, UI, or integration work starts before it clears.

## Parallel track — not blocked by this

**Design-partner search is on the critical path and starts now**, week 1, not week 10. Stage 2's
gate cannot be measured without a live support team, and the proxy corpus does not substitute for
one real organisation's tickets and KB. See [../context/roadmap.md](../context/roadmap.md).
