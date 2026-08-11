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

## 2026-08-11 — Stage 0 — QA audit of the eval harness/runner; two bugs fixed same day

**Changed:** Independent QA pass (not tied to task 0.9) over code the original `qa_report_stage0.md`
audit did not cover: `evals/harness/*`, `evals/runners/retrieval.py`, and the scripts added in
`4cfd5b2` (`golden_links.py`, `apply_remediation.py`, `collect_candidates.py`,
`judge_candidates.py`). Full write-up in [qa_report_stage0.md §9](qa_report_stage0.md#9-second-audit--eval-harness--runner-scope-2026-08-11).

Two bugs found and fixed same day:

1. **`pytest` (default invocation) errored out before running.** `4cfd5b2` moved
   `normalize_path`/`follow_redirects` from `build_golden.py` into the new `golden_links.py` but
   left `tests/test_eval_helpers.py` importing them from the old location. 7 of 26 tests —
   including the BUG-009 (PII redaction) and BUG-013 (truncation) regression guards — were not
   collected by a bare `pytest` run. `ruff check` stayed green throughout; it cannot catch a
   cross-module missing-name import. Fixed: corrected the import source.
2. **`apply_remediation.py --approved-only` did not gate on an unreviewed verdict.** The flag's own
   help text promises it only applies judgments with `human_verdict=agree`, but the code only
   special-cased `disagree`; a `None`/pending verdict (the exact state `judge_candidates.py` writes
   before human review) fell through and got applied anyway. Not exercised by any committed data —
   latent, not a realized corruption. Fixed: extracted `approved_for_application()` as a single
   explicit allowlist (`agree`, or `disagree` with a `human_correction`), with unit + CLI-level
   regression tests for the pending-verdict case.

**Why:** Both bugs sat in the two things that decide whether Stage 0's numbers can be trusted at
all — the test suite that guards prior fixes, and the script that mutates the golden set the gate
is scored against. Neither was caught by the two automated checks that do exist (`ruff`, no CI).

**Unblocks:** Nothing blocked — task 0.9 (ranking pilot) was never dependent on this. Records the
audit so `pytest`'s green state after `4cfd5b2` isn't mistaken for "tests were checked."

**Open:**
- No CI exists yet (`.github/` absent) despite `docs/standards/testing.md` naming `pytest` and
  `ruff` as blocking PR gates — this is *why* BUG-EH-001 shipped invisibly. Still open from the
  original audit (BUG-012).
- Two P3 findings from the same audit deliberately left unfixed: duplicated
  `normalize_path`/`follow_redirects` logic between `golden_links.py` and `parse_docs_manifest.py`,
  and `4cfd5b2` itself has no work_log entry (a gap this entry does not retroactively fill for that
  commit — it predates this one).

## 2026-08-04 — Stage 0 — Task 0.8: TinyBERT CE hurts; MiniLM full run aborted

**Changed:** Doc-level CE candidates in `retrieve.py` (unique docs from fused pool). Full TinyBERT
sweeps on remediated golden at pool/candidates 100 and 200 (dense_w=2). Started MiniLM-L-12 @100;
stopped on request before completion (~3–4h CPU estimate from n=5 probe).

**Measured (vs RRF 0.393 / 0.204):** TinyBERT @100 → **0.314 / 0.172**; @200 → **0.319 / 0.172**.
Larger TinyBERT pools do not recover the loss.

**Why stop MiniLM:** Full-set CPU cost too high for this machine/session; no partial report was
written (runner only emits at end).

**Decision:** Close 0.8 on available evidence. **TinyBERT is dead.** Gate **0.85 stays**. Next
(0.9): affordable stronger-ranking pilot (GPU / quantized / small-n MiniLM) or alt second-stage —
not more TinyBERT sweeps, not silent gate lowering.

**Unblocks:** Task 0.9 planning with clear negative result on TinyBERT.

**Open:**
- MiniLM quality on this golden still unknown
- Whether 0.85 is reachable with any CPU-only CE at full n

## 2026-08-04 — Stage 0 — Task 0.7 remediation: labels helped little; ranking is the bottleneck

**Changed:** BUG-014 remediation pipeline (`collect_candidates`, `judge_candidates`,
`apply_remediation`); hoisted `golden_links`; `build_golden` skips ambiguous multi-candidate
threads instead of blind `resolved[0]`. Applied 20 relabels + 5 → unanswerable on a 158-row triage
queue after spot-check (raw heuristic disagree 40% → corrections + conservative overlap gate).
Re-baseline on same store: recall@10 **0.393** / MRR **0.204** (Δ +0.025 / +0.011).
`fused_hit@500` **0.898**; complete misses 41 → 35.

**Why:** Measured metrics were optimizing against contaminated golds. Needed a trusted baseline
before more ranking or embedder work.

**Decision:** Gate **0.85 / 0.60 stays**; it is not near-term on RRF alone. Label noise was not the
sole cause. **Pivot to Task 0.8 — ranking quality** (stronger CE over larger pool). Do not resume
pure embedder sweeps; do not silently lower the gate yet.

**Unblocks:** Task 0.8 ranking experiments on a remediated golden.

**Open:**
- Heuristic judge disagree rate was high; LLM judge (`OPENAI_API_KEY`) not run this pass
- Remaining single-candidate noise outside the triage queue still unreviewed
- MiniLM/stronger CE CPU cost vs quality tradeoff

## 2026-08-02 — Stage 0 — Task 0.6 audit: gate not solvable without golden fix

**Changed:** First-stage miss audit (`evals.scripts.analyze_first_stage`) on the c256 store;
weighted RRF + BGE query-prefix knobs on the runner. Dense-weight×2 is a new best
(recall@10 **0.368** · MRR **0.192**) — still far from the gate.

**Why audit before bge-large:** 0.5 showed bigger BGE barely moves `hit_at_any`. Burning hours on
another re-ingest without knowing whether the golden set can support 0.85 would be cargo-cult.

**Solvability call:** **Do not keep embedding-sweeping toward 0.85 on this golden set.** Pool@500
already has `fused_hit` **0.883** while recall@10 stays ~0.33 (ranking failure). BUG-014 ~20%
label noise (confirmed again on complete-miss sample) caps measured metrics below the gate.
Remediate labels first.

**Unblocks:** Task 0.7 — golden remediation (BUG-014) then re-baseline.

**Open:**
- After remediation, revisit CE rerank over large pools (TinyBERT was too weak; MiniLM too slow on CPU)
- `bge-large` still unused — only worth it after labels are trustworthy

## 2026-08-02 — Stage 0 — Task 0.5 bge-base re-ingest; modest lift, gate still FAIL

**Changed:** Side-by-side stores with `BAAI/bge-base-en-v1.5` (768-d). Fixed ingest meta ↔ `--db`
coupling (`evals/harness/ingest_meta.py`: SQLite meta → sidecar → default file). Full golden runs:

| Config | recall@10 | MRR | hit_at_any |
|---|---|---|---|
| bge-base 512, RRF | 0.3315 | 0.1668 | 0.588 |
| bge-base 512 + TinyBERT @50 | 0.3259 | 0.1680 | 0.510 |
| **bge-base 256, RRF** | **0.3565** | **0.1837** | 0.571 |
| bge-base 256 + TinyBERT @50 | 0.3454 | 0.1671 | 0.507 |

**Why:** 0.4 showed rerank cannot recover gold outside the candidate pool; 0.5 tests a stronger
bi-encoder and a smaller chunk size as the next first-stage levers.

**Why this does not clear the gate:** Best recall@10 **0.356** — Δ only ~+0.036 vs 0.4 best.
`hit_at_any` stays ~0.57. Gap remains ~**0.49** recall@10 / ~**0.42** MRR.

**Unblocks:** Task 0.6 — further first-stage work (larger embedder, query prefixes, hybrid weights,
and/or golden-label audit). Do not spend more cycles on TinyBERT pool size.

**Open:**
- BUG-014 label noise still unquantified against achievable ceiling
- `bge-large` not tried (deferred; CPU ingest already ~1.3–2.6 h for base)
- Design partner still unidentified

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
