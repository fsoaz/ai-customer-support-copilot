# Work Log

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Write
> candidly here — including about what went wrong — because nobody outside reads it.

> Append-only. Newest entry at the top. Decisions and their reasoning — not a commit list, which
> git already provides.

## Entry format

```markdown
## YYYY-MM-DD — Stage N — Short title

**Changed:** what was done
**Why:** the reasoning, especially for anything non-obvious
**Unblocks:** what becomes possible now
**Open:** questions or risks carried forward
```

Write an entry when a decision is made, a gate is attempted, an assumption is invalidated, or a
direction changes. Do not write one for routine implementation that the diff explains by itself.

---

## 2026-08-02 — Stage 0 — Task 0.4 rerank wired; sweeps show first-stage bottleneck

**Changed:** Cross-encoder rerank via FlashRank ONNX (`evals/harness/rerank.py`), `--rerank` on
`evals.runners.retrieval` (default off). Sweep results on the 0.2 store:

| Config | recall@10 | MRR | Notes |
|---|---|---|---|
| RRF only (0.3 baseline) | 0.3148 | 0.1625 | rerank off |
| + TinyBERT @50 | **0.3203** | **0.1658** | best so far |
| + TinyBERT @100 pool | 0.3036 | 0.1579 | worse |
| MiniLM-L-12 @50 | — | — | killed after ~90 min @ ~700% CPU; shell exited error; **no report written** |

**Why FlashRank:** ONNX, no torch; matches Stage 0 "local, cheap sweeps" constraint.

**Why this does not clear the gate:** `hit_at_any` ≈ 0.57 on the baseline — nearly half of
answerable questions never place the gold doc in the RRF candidate set. Rerank only reshuffles
what first-stage retrieval already found. Gap to gate ≈ **0.53** recall@10 / **0.43** MRR.

**Unblocks:** Task 0.5 — re-ingest with a stronger bi-encoder (and/or chunking variants).

**Open:**
- BUG-014 label noise still unquantified against achievable ceiling
- Design partner still unidentified
- Consider GPU or batched CE if MiniLM-class rerank is revisited later

## 2026-08-01 — Stage 0 — Task 0.3 baseline retrieval metrics (gate FAIL)

**Changed:** Added `evals/harness/metrics.py` and `evals.runners.retrieval`. First full golden-set
run against the 0.2 SQLite harness (no rerank):

| Metric | Threshold | Measured | Pass |
|---|---|---|---|
| recall@1 | — | 0.0975 | — |
| recall@5 | — | 0.2284 | — |
| recall@10 | ≥ 0.85 | **0.3148** | **FAIL** |
| MRR | ≥ 0.60 | **0.1625** | **FAIL** |
| nDCG@10 | — | 0.1900 | — |

Unanswerable (n=31) excluded from those averages; mean top1 RRF ≈ 0.030 (near_miss / absurdist
reported by slice). Report: `evals/reports/retrieval_latest.json` (gitignored).

**Why record a failing gate:** Stage 0 principle — gates are objective. A soft baseline that looks
"promising" in smoke (6/10 @50) hid how far @10 actually is. Sweeps start from a real number.

**Unblocks:** Task 0.4 — parameter sweeps (model, chunking, RRF, rerank) toward the gate.

**Open:**
- Gap is large (~0.53 recall@10, ~0.44 MRR) — expect rerank + stronger embedder as highest leverage
- BUG-014 label noise (~20%) still caps achievable recall; revisit before calling the gate close
- Design partner still unidentified

## 2026-08-01 — Stage 0 — Task 0.2 ingest/embed harness live

**Changed:** Built a local Stage 0 retrieval harness (not product FastAPI):

- `evals/harness/` — whitespace chunking (512 / 15% overlap), markdown clean, fastembed
  (`BAAI/bge-small-en-v1.5`), SQLite + FTS5 store, dense+lexical → RRF (pre-rerank)
- `evals.scripts.ingest_docs` / `smoke_retrieve`
- Ingested pinned Auth0 MIT corpus → **1734** docs / **2688** chunks (107 empty after clean skipped)
- **359/359** answerable golden `gold_doc_id`s covered; smoke hit@50 **6/10**

**Why SQLite harness (not Postgres/pgvector yet):** Stage 0 forbids product schema; task explicitly
allows an equivalent local store. Same hybrid shape (dense + lexical + RRF) ports to pgvector later.

**Why local ONNX embeddings:** Stage 0 sweeps must not depend on a paid embedding API or burn quota
before the gate. Model name + dim recorded in `ingest_meta.json`.

**Unblocks:** Task 0.3 — full golden-set metric runners and parameter sweeps toward recall@10 / MRR.

**Open:**
- Smoke 4/10 misses — expect denser embedding model, rerank, or chunk tuning in 0.3 sweeps
- 107 empty cleaned articles skipped (none were answerable golds)
- Design partner still unidentified
- Cross-encoder rerank still absent (planned after baseline dense+lexical numbers)

## 2026-07-30 — Stage 0 — QA remediation; golden set gateable (pre-0.2)

**Changed:** Closed P0/P1 findings from [qa_report_stage0.md](qa_report_stage0.md).

| Bug | Fix |
|---|---|
| BUG-004 | Committed `backend/` + datasets + corpus metadata |
| BUG-001 | Dropped synthetic `auth0-url-*` golds; reharvested; **357** mirror-backed answerable at **100%** coverage |
| BUG-002 | Removed forum link-absence → unanswerable heuristic |
| BUG-003 | Replaced absurdist-majority negatives with 25 near-miss + 6 absurdist (`negative_slice`) |
| BUG-005/007/008 | `expected_commit.txt` pin enforced; parse uses committed `redirects_flat.json` (no default `node require`) |
| BUG-006/009/010/011/012/013 | Seeded spot-check; PII redaction; harvest failure ledger; index rebuild; pytest; head+tail truncate |

**Why BUG-001 = drop + reharvest (not scrape auth0.com):** same ToS discipline as rejecting Elastic.
Thin mirror-backed set (~220) was grown by more Discourse harvest, not production HTML.

**Unblocks:** Task 0.2 ingest/embed against a golden set whose recall ceiling is no longer 0.576.

**Open:**
- ~20% first-link label noise remains (BUG-014) — revisit before gate call
- Design partner still unidentified
- Metric runner still absent (0.3)

## 2026-07-30 — Stage 0 — Auth0 proxy corpus selected; golden set built (task 0.1)

**Changed:** Implemented Stage 0 task 0.1. Scaffolded `backend/` with uv. Fetched Auth0 docs from
GitHub (MIT) at commit recorded in `evals/corpus/auth0/docs/fetch_meta.json`, built
`manifest.json` via redirects. Harvested solved topics from `community.auth0.com` (Discourse JSON,
robots-safe). Wrote `evals/datasets/retrieval_golden.jsonl` (**382** answerable + **35**
unanswerable). Spot-check 18/20 pass. Licence notes in `evals/corpus/auth0/licence_notes.md`.

**Why Auth0 (not Elastic):** Elastic.co Terms of Use forbid scrapers; `elastic/docs-content` is
CC BY-NC-ND 4.0 — fails "terms permitting the crawl" for a commercial SaaS eval corpus. Auth0 docs
are MIT on GitHub; forum exposes `has_accepted_answer` and frequently cites `auth0.com/docs/...`.
Domain is dense with OAuth/OIDC error codes and identifiers.

**Why not HTML-scrape auth0.com:** Docs content comes from the MIT GitHub mirror. Forum harvest uses
public Discourse `.json` only. Some golden URLs are newer than the GitHub tree; those rows use
synthetic `auth0-url-*` gold ids so Stage 0.1 is not blocked — Stage 0.2 must still obtain content
for those URLs.

**Unblocks:** Task 0.2 — chunk/embed/ingest and hybrid retrieval experiments against this golden set.

**Open:**
- Synthetic gold ids (`auth0-url-*`) lack local article bodies until 0.2 fetches or maps them.
- Design partner still unidentified (parallel critical path).
- ~10% label noise in spot-check (incidental docs links in accepted answers).

## 2026-07-30 — Stage 0 — Project planning; scope and stack locked

**Changed:** Populated the entire `docs/` scaffold — `context/` (product, architecture, roadmap),
`standards/` (conventions, api_rules, testing, ai_agent_rules), `execution/` (this log, current
task, review notes, test evidence). No application code written.

Locked constraints:

| Decision | Choice |
|---|---|
| Business model | Multi-tenant SaaS |
| Team | Solo developer |
| Data available | None — no tickets, no knowledge base |
| Infrastructure | Supabase + Vercel |
| Runtime | FastAPI backend (Fly.io) + Next.js frontend (Vercel) |
| V1 wedge | Grounded draft replies with citations. Everything else deferred |

**Why:** The project began as a design document that read as a strong pitch but not an executable
plan — layer-first roadmap, riskiest unknown scheduled last, no eval harness, and a 9-person
infrastructure stack for a product with zero users. Full critique and the corrections adopted are
in [review_notes.md](review_notes.md).

The most consequential reordering: retrieval quality moved from week 5–8 to **Stage 0, weeks 1–3**,
offline, with no product code. It is the assumption that decides whether the product is possible,
and it should cost three weeks to test, not three months.

The second: `tenant_id`, RLS, prompt/model provenance, per-call cost accounting, and webhook
idempotency all land in the **first migration and the first model call**. Each is cheap now and
brutal to retrofit.

**Unblocks:** Stage 0 task 0.1 — build the proxy corpus. See [current_task.md](current_task.md).

**Open:**
- Which public product to use for the proxy corpus is not yet chosen (task 0.1).
- No design partner identified. This is on the critical path from week 1, since Stage 2's gate
  cannot be measured without a live support team.
- Model IDs deliberately unpinned in the docs; they get pinned in configuration at Stage 1 and
  re-checked at every stage gate.
