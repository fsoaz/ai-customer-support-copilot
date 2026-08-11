# QA Report — Stage 0 Eval Corpus & Golden Set

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. Findings
> here are deliberately blunt because the audience is us. Nothing in this file is a benchmark
> claim, a product commitment, or a statement about anyone else's software.

**Reviewed:** 2026-07-30
**Scope:** `backend/evals/` — golden set, corpus manifests, and the four Stage 0 scripts.
**Explicitly out of scope:** product API, UI, schema, auth, integrations. None exist yet
(see [current_task.md](current_task.md)); reviewing them would mean inventing findings.
**Method:** static read of all four scripts plus programmatic audit of
`retrieval_golden.jsonl`, `manifest.json`, `redirects_flat.json`, `index.jsonl`, and the raw
corpus tree. Every number below was measured, not estimated.

**Status: remediated and re-verified 2026-07-30 — see [§8](#8-remediation-verification--2026-07-30).**
Sections 1–7 are preserved as written at audit time and are **no longer current**. They record what
was found, so the corrections stay distinguishable from accidents later. Read §8 for present state.

**A second, narrower audit ran 2026-08-11 over code this report did not cover (the harness/runner,
not the golden-set builder) — see [§9](#9-second-audit--eval-harness--runner-scope-2026-08-11),
remediated same day.**

---

## 1. Executive summary

**Verdict: do not run the Stage 0 gate against this golden set as it stands.**
**Risk level: critical.** **Effort: moderate rework** — corpus coverage fix plus a relabel pass.
The scripts' shape is sound; nothing needs rebuilding.

Three risks, in order:

1. **The gate is mathematically unpassable.** 162 of 382 answerable pairs (42.4%) point at gold
   documents that are not in the fetched corpus. Ceiling on recall@10 is **0.576**. The gate needs
   0.85. No retrieval tuning closes that gap — it is a corpus problem wearing a metric's clothes.
2. **The refusal metric is poisoned.** 32 of 35 unanswerable rows are absurdist hand-written
   questions; the 3 real ones are mislabelled and are in fact answerable. Refusal correctness will
   read near-perfect and mean nothing.
3. **The deliverable is not in version control.** `git ls-files backend` returns 0. Task 0.1 is
   marked done and its artefacts are linked from three documents, but one `git clean -fd` deletes
   the work.

## 2. Smoke test — **fail**

The dataset parses clean: 417 rows, one uniform schema, zero duplicate IDs, zero duplicate
questions under two normalisation schemes, zero orphan gold IDs, zero gold-label leakage into
unanswerable rows. Structural hygiene is genuinely good. The semantic smoke test fails on first
contact: 42% of answers point outside the searchable corpus, so the retrieval experiment task 0.2
is about to build cannot be scored honestly.

## 3. Scorecard

| Domain | Score | Rationale |
|---|---|---|
| Dataset structural integrity | 8 / 10 | Uniform schema, no dupes, no orphans, no leakage, content-addressed IDs. Lost points for 26 truncated questions |
| Label correctness | 3 / 10 | 42% unretrievable gold; 3 of 3 forum negatives mislabelled; spot-check found 2 of 20 incidental links |
| Negative-example design | 2 / 10 | 32 of 35 absurdist. No near-miss negatives — the only kind that tests refusal |
| Reproducibility | 3 / 10 | Corpus untracked and gitignored (415 MB); `backend/` untracked; upstream clone unpinned by default |
| Script robustness | 6 / 10 | Good: tenacity backoff, `Retry-After` honoured, idempotent skip, fetch/parse split, ruff clean. Bad: silent drops on repeat-429 and on 4xx |
| Security hygiene | 4 / 10 | Executes upstream JS via `node -e require()` inside an unpinned third-party clone. Unredacted third-party PII in the dataset |
| Test infra vs standard | 1 / 10 | [../standards/testing.md](../standards/testing.md) defines three tiers. Zero tests, no pytest in deps or `uv.lock`, no CI |

---

## 4. Issue register

### BUG-001 — 42% of gold documents are not in the corpus

**Domain:** data integrity **Severity:** critical **Priority:** P0

**Steps to reproduce**

1. Load `backend/evals/datasets/retrieval_golden.jsonl` → 382 answerable rows.
2. Load `backend/evals/corpus/auth0/docs/manifest.json` → 1841 documents, 10 146 URL keys.
3. Count rows whose `gold_doc_id` starts `auth0-url-` — the synthetic prefix minted at
   `build_golden.py:178` when the manifest lookup misses.

**Expected:** every answerable gold document exists in the indexed corpus.

**Actual:** 162 of 382 = **42.4%** synthetic. Cross-check: **zero** of those 162 URLs appear in
`url_to_id` under any alias, so they are not a normalisation near-miss — the pages are absent.
They are the modern auth0.com/docs information architecture, which the MIT GitHub mirror does not
carry: `/customize/actions`, `/secure/tokens/token-vault`,
`/customize/custom-domains/multiple-custom-domains`, and so on.

**User impact:** recall@10 ceiling 0.576 against a 0.85 gate. Stage 0 either fails permanently or
the gate gets waived — and a waived gate is the single failure mode
[../context/roadmap.md](../context/roadmap.md) exists to prevent.

**Recommendation:** decide before 0.2 spends embedding cost. Either fetch the 162 live URLs into
the corpus, or drop them and rebuild the answerable set from mirror-covered pairs only. The second
path leaves ~220 pairs, thin against the 300–500 target, so it implies harvesting more forum
topics. Do not average metrics across both populations under any circumstances.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:139-178` (`resolve`,
`allow_synthetic`); 0.2 definition-of-done bullet 3 in [current_task.md](current_task.md).

### BUG-002 — Forum "unanswerable" rows are actually answerable

**Domain:** label correctness **Severity:** critical **Priority:** P0

**Steps to reproduce** Filter for `answerable=false` and non-empty `source_thread_url` → 3 rows.

**Expected:** unanswerable means the knowledge base genuinely lacks the answer.

**Actual:** the label is assigned by *absence of a docs link in the accepted answer*
(`build_golden.py:297-323`). The three rows are "How to set SAML RelayState in Actions?",
"Organizations + custom RBAC roles best practice", and "Create Auth0 session manually for custom
SSO". All three have accepted answers. All three are documented topics.

**User impact:** a system that correctly answers these is scored as a refusal failure — training
the wrong direction on the exact metric [../standards/testing.md](../standards/testing.md) names
as the one that destroys trust in production.

**Recommendation:** delete the link-absence heuristic. Unanswerable must be an explicit human
label, never an inference from missing metadata.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:297-341`.

### BUG-003 — Negatives are absurdist rather than near-miss

**Domain:** eval design **Severity:** high **Priority:** P1

**Steps to reproduce** Read `HAND_UNANSWERABLE`, `build_golden.py:29-62`. 32 of the 35 shipped
negatives come from this list.

**Expected:** negatives a real support ticket could plausibly contain — plausible-sounding
features Auth0 does not have, or real questions the KB does not cover.

**Actual:** "translate Universal Login into Klingon", "stream logs into a fax machine", "COBOL
mainframe connector for AS/400", "buy credits with airline miles".

**User impact:** any retriever scores near-perfectly on these; cosine similarity to the corpus is
near zero. The metric reads 1.0 while hiding that the system hallucinates happily on realistic
gaps. False confidence at precisely the gate that decides whether the product is viable.

**Recommendation:** replace roughly 25 of the 32 with near-miss negatives — real Auth0 vocabulary,
plausible mechanism, genuinely not in the docs. Keep a handful of absurdist ones as a sanity floor,
tracked as a separate slice so the two never average together.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:29-62`.

### BUG-004 — `backend/` is untracked

**Domain:** process / reproducibility **Severity:** high **Priority:** P0

**Steps to reproduce** `git ls-files backend | wc -l` → `0`. `git status` → `?? backend/`.

**Expected:** a closed task's deliverable is committed.

**Actual:** 13 source and dataset files plus 8 corpus metadata files, all uncommitted.
[current_task.md](current_task.md) marks 0.1 done and links these paths; [work_log.md](work_log.md)
records the completion.

**User impact:** the golden set, all four scripts, and the manifest exist on one disk with no
history. `git clean -fd` deletes Task 0.1 in full.

**Recommendation:** commit before any 0.2 work begins.

**Suggested fix location:** repo root — `git add backend`.

### BUG-005 — The golden set cannot be rebuilt from a clean clone

**Domain:** reproducibility **Severity:** high **Priority:** P1

**Steps to reproduce**

1. `.gitignore:14-15` excludes `**/docs/raw/` and `**/forum/raw/`.
2. `build_golden.py:236` hard-exits without `forum/raw/`.
3. On a fresh clone `forum/raw/` is absent — only `forum/raw/.gitkeep` is negated, and
   `docs/raw/.gitkeep` does not exist on disk at all.

**Expected:** a documented regeneration path, or a content-addressed corpus.

**Actual:** the 415 MB corpus is local-only. Regeneration means re-harvesting 1304 live forum
topics, which is a moving target — community threads get edited, deleted, and re-accepted.

**User impact:** the golden set is unauditable and cannot be re-derived by anyone else, including
future-us. That undermines every number Stage 0 produces.

**Recommendation:** either commit the small derived artefacts sufficient for a rebuild (already
true for `manifest.json`, `redirects_flat.json`, and `index.jsonl`), or store `forum/raw/`
out-of-band with a committed checksum manifest. Record the choice in [work_log.md](work_log.md).

**Suggested fix location:** `.gitignore:14-17`; missing
`backend/evals/corpus/auth0/docs/raw/.gitkeep`.

### BUG-006 — The spot-check sample is not random

**Domain:** QA methodology **Severity:** high **Priority:** P1

**Steps to reproduce**

1. `build_golden.py:373-375` writes `spot_check_candidates.jsonl` as `answerable[:40]`.
2. Verified: candidate IDs are exactly the first 40 answerable rows, in order.
3. `spot_check.md` reviewed 20 rows drawn from that head.

**Expected:** a random sample, so that "90% pass" estimates set-wide label accuracy.

**Actual:** a deterministic head of a round-robin-diversified list (`_diversify`,
`build_golden.py:387-404`). The first 40 rows are 40 *distinct* gold documents by construction —
the most diverse, least repeated slice of the set. `spot_check.md` describes this as a "diverse
sample by `gold_doc_id`", which is an accurate description of the mechanism, and is then used to
license a claim about the whole set.

**Evidence:** the reviewed 20 were 9 synthetic / 11 mirror-backed (45% vs a 42.4% population rate)
— representative on that axis by luck, not design.

**User impact:** "18/20 pass (90%)" carries no confidence interval and does not generalise to the
342 unreviewed rows.

**Recommendation:** re-sample with a seeded RNG across all answerable rows, stratified by synthetic
vs mirror-backed. Report pass rate per stratum with a Wilson interval. Record the seed in the file.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:372-375`; the method line in
`backend/evals/datasets/spot_check.md`.

### BUG-007 — Manifest build executes upstream third-party JavaScript

**Domain:** security **Severity:** high **Priority:** P1

**Steps to reproduce**

1. `fetch_docs.py:34-53` clones `github.com/auth0/docs` at HEAD — no pin by default.
2. `parse_docs_manifest.py:43-47` runs `node -e "require('./config/redirects.js')"` with
   `cwd=RAW_DIR`.

**Expected:** parsing untrusted upstream data does not execute it.

**Actual:** `require()` evaluates a file from a freshly-cloned external repository, in-process,
with the developer's full privileges.

**User impact:** anything that lands in that upstream file — an upstream compromise, or simply a
bad merge — runs locally on the next `parse_docs_manifest.py`. Low likelihood, high blast radius.
Operating principle 5 puts retrofit-hostile controls in on commit 1; this is one of them.

**Recommendation:** make the pin required rather than opt-in, and treat `redirects_flat.json` as a
committed artefact regenerated deliberately. If the dump stays, run node with no network access
and diff its output against the committed version before accepting it.

**Suggested fix location:** `backend/evals/scripts/parse_docs_manifest.py:28-50`;
`backend/evals/scripts/fetch_docs.py:23-58`.

### BUG-008 — The corpus pin is recorded, not enforced

**Domain:** reproducibility **Severity:** medium **Priority:** P1

**Steps to reproduce** Run `fetch_docs.py` twice, weeks apart, without `--commit`.

**Expected:** the same corpus, or a loud failure.

**Actual:** the default path is a `--depth 1` clone of HEAD. The already-present branch
(`fetch_docs.py:25-29`) reads whatever SHA is on disk and writes it into `fetch_meta.json` —
recording reality rather than verifying intent. Today `manifest.json` and `fetch_meta.json` agree
on `5258d17e`; nothing keeps that true.

**User impact:** two Stage 0 runs weeks apart silently score against different corpora, making
retrieval deltas uninterpretable — which is the whole point of running them.

**Recommendation:** read the expected SHA from a committed file and fail loudly on mismatch instead
of overwriting the record.

**Suggested fix location:** `backend/evals/scripts/fetch_docs.py:23-58`.

### BUG-009 — Unredacted third-party PII in the dataset

**Domain:** security / compliance **Severity:** medium **Priority:** P2

**Steps to reproduce** Run `[\w.+-]+@[\w-]+\.[\w.]+` across all 417 questions.

**Expected:** per [../standards/testing.md](../standards/testing.md), redaction is a first-class
concern with its own golden set and a recall metric in both directions.

**Actual:** 7 rows contain real-looking email addresses (`ray.garg@zappsec.com`, `arno@gmail.com`,
`user@abv.bg`, and others), 10 contain tenant domains, and 1 mentions `client_secret`. All verbatim
from public forum posts.

**User impact:** these questions get sent to third-party embedding and LLM providers on every eval
run. Low volume and public in origin — but it is other people's PII, and this repo's own standard
says to measure redaction in both directions.

**Recommendation:** redact emails and tenant domains at build time using stable placeholders, and
keep the pre-redaction pairs out of the committed dataset. The placeholders double as free
redaction-recall fixtures for Stage 1.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:181-196`
(`question_from_topic`).

### BUG-010 — The harvest drops topics silently

**Domain:** data completeness **Severity:** medium **Priority:** P2

**Steps to reproduce** Read `fetch_forum.py:47-59` and `:122-144`.

**Expected:** every solved topic either lands on disk or is recorded as a failure.

**Actual:** three silent-loss paths.

1. A 429 is retried exactly once (`:49-53`); a second 429 falls through to `raise_for_status()`,
   is caught by the bare `except Exception` in the topic loop, and is logged only to stdout with
   no durable record.
2. A 404 returns `{}`, which falls to `:143` `continue` with no log at all.
3. In the category loop, any `HTTPStatusError` `break`s out of that category's remaining pages
   (`:108-110`).

**User impact:** 1304 topics were harvested; how many were dropped is unknowable after the fact.
Corpus completeness is an unverified assumption sitting underneath the gate.

**Recommendation:** write a durable failure ledger (topic ID, status, reason), honour `Retry-After`
in a loop rather than once, and have the run summary report category breaks as errors.

**Suggested fix location:** `backend/evals/scripts/fetch_forum.py:47-59`, `:108-110`, `:136-144`.

### BUG-011 — `index.jsonl` does not match `raw/`

**Domain:** data integrity **Severity:** medium **Priority:** P2

**Steps to reproduce** `ls forum/raw | wc -l` → **1304**. `wc -l index.jsonl` → **1232**, with
1232 unique IDs, so there are no duplicates — 72 raw files are simply absent from the index.

**Expected:** the index enumerates the raw corpus.

**Actual:** `:130-133` skips already-present topics *before* the index write, and the index is
opened append-only (`:98`), so a re-run never backfills.

**User impact:** anything treating `index.jsonl` as the corpus manifest under-counts by 5.5%.
`build_golden.py` happens to glob `raw/` directly, so today's numbers are unaffected — this is a
trap laid for the next script rather than a live defect.

**Recommendation:** rebuild the index from `raw/` at the end of the run instead of appending during
it.

**Suggested fix location:** `backend/evals/scripts/fetch_forum.py:98`, `:129-157`.

### BUG-012 — No test infrastructure

**Domain:** test infra vs standard **Severity:** medium **Priority:** P2

**Steps to reproduce** No `test_*.py` outside `.venv`; no `conftest.py`;
`grep 'name = "pytest"' uv.lock` → 0 matches; no `.github/`.

**Expected:** [../standards/testing.md](../standards/testing.md) defines unit, integration, and
eval tiers, with unit tests running on every commit.

**Actual:** none of the three exist. `ruff check` passes clean and constitutes the entire automated
quality gate.

**User impact:** `normalize_path`, `follow_redirects`, `_diversify`, and `synthetic_doc_id` are
exactly the "pure logic" the standard names for unit tests, and every one of them silently shapes
the gold labels. A regression in any of them corrupts the dataset invisibly.

**Recommendation:** add pytest and unit tests for those four functions now, while their intended
behaviour is still fresh. Defer the integration and eval tiers until there is an application.

**Suggested fix location:** `backend/pyproject.toml` (dev dependency group); new `backend/tests/`.

### BUG-013 — Questions truncated mid-sentence

**Domain:** data quality **Severity:** low **Priority:** P2

**Steps to reproduce** Count questions ending in `…` → **26** rows, of which 24 sit exactly at the
2000-character cap.

**Expected:** truncation preserves the actual question.

**Actual:** `build_golden.py:193-195` hard-cuts at 2000 characters from the start of the post.
Forum posts routinely open with logs and config dumps and put the question last.

**User impact:** some queries no longer contain the question being asked, depressing recall for
reasons that have nothing to do with retrieval quality.

**Recommendation:** truncate from the middle, keeping head and tail, or cap on the post's
interrogative span. Flag affected rows so they can be excluded from the headline metric.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:193-195`.

### BUG-014 — Gold label is "first docs link in the accepted answer"

**Domain:** label correctness **Severity:** low **Priority:** P3

**Steps to reproduce** `build_golden.py:284-286` — `gold_id, gold_url = resolved[0]`.

**Expected:** gold is the document that answers the question.

**Actual:** gold is whichever docs URL appears first in the accepted answer. Both spot-check
failures are this exact mode: #9 (Node 22 upgrade → `write-your-first-action`) and #14 (Playwright
→ `update-access-token-lifetime`).

**User impact:** roughly 10% label noise, already measured and accepted in `spot_check.md`.
Reasonable for Stage 0 — recorded here so it is not forgotten when the gate reads 0.83 and someone
wonders why.

**Recommendation:** leave as-is through 0.2. Before the gate call, re-review any pair whose gold
document ranks poorly. Separating retrieval misses from label noise is the difference between a
real failure and a false one.

**Suggested fix location:** `backend/evals/scripts/build_golden.py:277-296`.

### Minor findings

| ID | Severity / Priority | Finding | Fix location |
|---|---|---|---|
| BUG-015 | low / P3 | Dead no-op block: `if len(answerable) >= target_answerable * 2: pass`, with a comment describing an early-stop that was never implemented. Reads as a deliberate guard, does nothing | `build_golden.py:326-328` |
| BUG-016 | low / P3 | Alias resolution is O(docs × redirects) — 1841 × 4141 ≈ 7.6 M chain walks. Runs once, so tolerable; invert the redirect map to canonical→sources if the corpus grows | `parse_docs_manifest.py:107-136` |
| BUG-017 | low / P3 | `assert parts.startswith("articles/")` used for control flow. Stripped under `python -O`, silently producing malformed URL paths and therefore wrong `gold_doc_id` values. Raise instead | `parse_docs_manifest.py:81-88` |
| BUG-018 | low / P3 | `.gitignore` negates `**/docs/raw/.gitkeep` but the file does not exist (the forum one does). Harmless today — `fetch_docs.py` creates the directory — but the intent is half-applied | `backend/evals/corpus/auth0/docs/raw/.gitkeep` |

---

## 5. Missing, that a reasonable reader would expect

1. **Metric runner.** No `evals/runners/`, no recall/MRR/nDCG code.
   [../standards/testing.md](../standards/testing.md) names the directory and
   [test_evidence.md](test_evidence.md) names the command
   (`uv run python -m evals.runners.retrieval`); nothing implements either. The Stage 0 gate is
   currently uncomputable by any code in this repo. That is 0.3 scope — noted so the gate does not
   arrive unimplemented.
2. **Dataset validator.** Every check in this report was ad-hoc. Schema, duplicate, orphan, and
   leakage validation belongs in CI, running on every dataset rebuild.
3. **Corpus coverage report.** Nothing surfaces "percentage of gold documents actually indexed" —
   the one metric that would have caught BUG-001 at build time. `build_golden.py:380-384` warns on
   pair *count* and never on coverage.
4. **Stratified metric slicing.** Mirror-backed vs synthetic, forum negative vs hand-written
   negative, truncated vs whole. A single averaged recall figure hides all four populations.

## 6. What is done well

1. **Fetch and parse are separated, and it pays off.** `fetch_docs.py` → `parse_docs_manifest.py` →
   `build_golden.py` lets the manifest rebuild without re-cloning, and re-runs skip existing
   topics. This is the structure most eval corpora get wrong.
2. **Structural hygiene is genuinely clean.** 417 rows, one uniform schema, zero duplicate IDs,
   zero duplicate questions under two normalisation schemes, zero orphan gold IDs, zero gold-label
   leakage into unanswerable rows. Content-addressed IDs (`pair_id`, `doc_id_for`) make the set
   diffable across rebuilds. Ruff clean.
3. **The scraping is well-behaved and honest about it.** Documented robots.txt compliance (`/c/`
   and `/t/` only, never `/search`), an identifying user agent, tenacity backoff, explicit
   `Retry-After` handling, a 0.35 s default sleep. Licence check recorded; Elastic rejected on
   ToS grounds. Rare discipline.
4. **The spot-check exists and reports its own failures.** 18/20 with both failures described
   accurately rather than rationalised, plus an explicit "expect some label noise" caveat. The
   sampling method is wrong (BUG-006); the intellectual honesty is not.

## 7. Recommended order

1. **BUG-004** — commit `backend/`. Five seconds, and everything else depends on it.
2. **BUG-001** — decide corpus coverage before 0.2 spends embedding cost.
3. **BUG-002 and BUG-003** — relabel the negatives while the corpus decision is being made.
4. **BUG-005, BUG-007, BUG-008** — reproducibility and the node-execution path, before the corpus
   is refetched.
5. Everything else can follow 0.2.

---

## 8. Remediation verification — 2026-07-30

**Verdict: gateable.** Every claim below was re-measured against the working tree at `55fd631`, not
accepted from the remediation summary.

**Commits:** `14306a8` (Stage 0.1 artefacts, BUG-004) → `3a68209` (drop nested docs clone
submodule) → `55fd631` (full remediation). Working tree clean.

**Locked decision:** drop synthetic gold labels and reharvest from the MIT mirror. No auth0.com
scrape. This is the (b) branch of BUG-001's recommendation, and it is what the numbers below
reflect.

### Headline, re-measured

| Claim | Measured | Result |
|---|---|---|
| 359 answerable, 0 synthetic | 359 / 0 | ✅ |
| 100% in MIT manifest | 359 of 359 resolve; 0 orphan | ✅ |
| 31 unanswerable, 25 near-miss + 6 absurdist | `negative_slice` counter exact | ✅ |
| Spot-check seeded, 16/20 | `seed=20260730`, `rng_shuffle_all_answerable` | ✅ |
| Pytest 7 passed | `7 passed in 0.06s` | ✅ |

### Issue disposition — 18 of 18 closed or deliberately deferred

| ID | Status | Evidence |
|---|---|---|
| BUG-001 | fixed | 0 synthetic (was 162 / 42.4%); `coverage_report.json` records `coverage_pct: 100.0` |
| BUG-002 | fixed | 0 forum-derived negatives; all 31 unanswerable are hand-authored |
| BUG-003 | fixed | 25 near-miss added, absurdist cut 32 → 6; `negative_slice` field makes the slices separable |
| BUG-004 | fixed | `backend/` tracked at `14306a8`; 26 files under version control |
| BUG-005 | fixed | `RAW_README.md` in both raw dirs, `forum/sample/` committed, `expected_commit.txt` pins the clone |
| BUG-006 | fixed | Seeded RNG over all answerable rows; method and seed recorded in `spot_check.md` |
| BUG-007 | fixed | `node -e` now opt-in behind `--dump-redirects`; default reads the committed `redirects_flat.json` |
| BUG-008 | fixed | `expected_commit.txt` = `5258d17e`, enforced by `fetch_docs.py` rather than recorded after the fact |
| BUG-009 | fixed | 0 email addresses in questions (was 7); `test_redact_question_emails_and_tenants` guards it |
| BUG-010 | fixed | `harvest_failures.jsonl` ledger; `Retry-After` honoured in a loop; category breaks recorded |
| BUG-011 | fixed | `rebuild_index()` writes from `raw/`; index 1842 = raw 1842 (was 1232 vs 1304) |
| BUG-012 | fixed | `backend/tests/test_eval_helpers.py`, 7 tests over the four label-shaping helpers |
| BUG-013 | fixed | 0 truncated questions (was 26); `test_truncate_keeps_head_and_tail` guards it |
| BUG-014 | deferred | Deliberate, documented in `spot_check.md`. Revisit before the gate call — see risk 1 below |
| BUG-015 | fixed | Dead no-op block removed |
| BUG-016 | deferred | Correct call — runs once |
| BUG-017 | fixed | `raise ValueError` replaces the bare `assert` |
| BUG-018 | fixed | `RAW_README.md` supersedes the `.gitkeep` approach in both raw dirs |

Also shipped, against §5 of this report: `coverage_report.json` — the artefact that would have
caught BUG-001 at build time.

### Three things to record before the gate runs

1. **Label noise is now honestly 20%, and it eats the gate's headroom.** 4 of 20 fail on an
   unbiased sample, against the old biased 90%. This is not a regression — it is the true rate
   surfacing, which is the entire point of fixing BUG-006. Consequence: with a 0.85 gate and ~20%
   label noise, any recall@10 landing roughly between 0.70 and 0.85 is **undecidable** without
   re-reviewing the misses. Decide the adjudication rule now, while it is still neutral. Deciding
   it after seeing 0.79 is exactly how a gate gets waived.
2. **Gold-document concentration rose.** 222 unique gold docs → **162**, across 359 pairs — 2.2
   pairs per document, max reuse 12 (was 9). Unavoidable under the locked decision, since dropping
   synthetics removed the long tail. Consequence: recall@10 is scored over 162 targets out of 1841
   corpus documents, and a retriever that happens to nail `user-account-linking` (12),
   `create-namespaced-custom-claims` (11), and `default-login-url` (9) banks 9% of the set from
   three pages. Report per-document variance next to the mean, or the headline number flatters.
3. **Harvest yield was 1482 of 1842 topics discarded (80%)** — no docs link in the accepted answer.
   Expected, not a defect. Recorded so the next harvest does not rediscover it. The non-zero exit
   on that job was a deliberate kill once the pair target was met, not a build failure.

### Residual, fixed in this pass

`spot_check.md` recorded the population as 357 against an actual 359 — a rebuild after the line was
written. Corrected to 359. Cosmetic, but [test_evidence.md](test_evidence.md) holds that a gate
whose passing nobody can point to did not pass, and records with drifting numbers erode exactly
that.

---

## 9. Second audit — eval harness & runner scope (2026-08-11)

**Reviewed:** 2026-08-11. **Scope:** `evals/harness/*`, `evals/runners/retrieval.py`, and every
script added by `4cfd5b2` (`golden_links.py`, `apply_remediation.py`, `collect_candidates.py`,
`judge_candidates.py`) — the code §1–8 above explicitly did not cover, since it didn't exist yet at
the first audit. **Explicitly out of scope:** product API, UI — still absent.
**Method:** ran the actual test suite (the committed `.venv` was unusable in the review environment
— stale interpreter symlink — so a throwaway venv was built from `pyproject.toml`), ran
`ruff check`, and did a full static read of every file in scope.

**Status: remediated and re-verified 2026-08-11, same day as the finding.**

### 9.1 Smoke test — fail (at time of finding), pass after fix

`cd backend && pytest -q` — the default invocation, no flags — errored out during collection rather
than running:

```
ImportError: cannot import name 'follow_redirects' from 'evals.scripts.build_golden'
```

With `--continue-on-collection-errors`, the other 3 test files' 17 tests passed; `tests/
test_eval_helpers.py`'s 7 did not run at all. The retrieval math itself (RRF, metrics, chunking,
rerank plumbing, hybrid retrieve, SQLite store) read as correct on inspection — this audit found no
defects in that code, only in the two files below.

### 9.2 Issue register

**BUG-EH-001 — `pytest` (default invocation) could not collect `tests/test_eval_helpers.py`**

**Domain:** test infra **Severity:** high **Priority:** P0 → **fixed**

**Root cause:** `4cfd5b2` moved `normalize_path`/`follow_redirects` out of
`evals/scripts/build_golden.py` into the new `evals/harness/golden_links.py` (157 lines changed in
`build_golden.py` alone) but never updated `tests/test_eval_helpers.py`, which still imported both
names from the old location.

**User impact:** the 7 uncollected tests included `test_redact_question_emails_and_tenants` and
`test_truncate_keeps_head_and_tail` — the regression guards written for BUG-009 (PII reaching
third-party embedding/LLM providers) and BUG-013 (mid-sentence truncation) in §4 above. Neither was
being exercised by any command a developer runs by default. `ruff check` passed clean throughout —
it cannot detect a name imported from a module that no longer exports it. No CI exists
(`.github/` absent) to have caught it either, despite [../standards/testing.md](../standards/testing.md)
naming `pytest -m "not eval"` as a blocking PR gate.

**Fix:** `tests/test_eval_helpers.py` now imports `follow_redirects`/`normalize_path` from
`evals.harness.golden_links`.

**Suggested fix location:** `backend/tests/test_eval_helpers.py:5-11` (import block).

---

**BUG-EH-002 — `apply_remediation.py --approved-only` did not gate on a pending verdict**

**Domain:** input validation / logic **Severity:** medium **Priority:** P2 → **fixed**

**Steps to reproduce (pre-fix)**

1. `judge_candidates.py` writes `remediation_spot_check.jsonl` with `human_verdict: null` for every
   row before human review (`judge_candidates.py:186,197`; its own stdout says
   `human_verdict=null`).
2. Run `apply_remediation.py --approved-only` before any row is reviewed.
3. The gate only special-cased `human_verdict == "disagree" and no human_correction` → skip.
   Any other value, including `null`/pending, fell through to `apply_one()` and was applied.

**Expected:** per the flag's own `--help` text — *"Only apply judgments whose id has
human_verdict=agree"* — a pending row should not be applied.

**User impact:** the flag is unused elsewhere in the codebase and unreferenced in docs, so no
committed data was corrupted by it — this was a latent defect, not a realized one. But it is the
one control whose entire purpose is "don't touch the golden set until a human signs off," and it
failed at that job for the exact pending state its own sibling script produces. The golden set is
the input to every recall@10/MRR number Stage 0 has recorded.

**Fix:** extracted `approved_for_application(spot_row)` as a single explicit allowlist —
`human_verdict == "agree"`, or `"disagree"` with a `human_correction` present — replacing the old
skip-only-if-disagree-without-correction conditional. Added
`test_approved_for_application_requires_explicit_review` (unit) and
`test_approved_only_does_not_apply_pending_judgment` (CLI-level, drives `apply_remediation.main()`
end-to-end against a synthetic `human_verdict: null` row and asserts the golden row is left
untouched).

**Suggested fix location:** `backend/evals/scripts/apply_remediation.py:108` (new helper),
`:187-198` (call site, pre-fix).

### 9.3 Minor findings — left open, deliberately

| ID | Severity/Priority | Finding | Fix location |
|---|---|---|---|
| MIN-EH-003 | low/P3 | `normalize_path`/`follow_redirects` are duplicated verbatim between `evals/harness/golden_links.py` and `evals/scripts/parse_docs_manifest.py` instead of one importing the other — the same kind of drift that caused BUG-EH-001 | `backend/evals/scripts/parse_docs_manifest.py:64-90` |
| MIN-EH-004 | low/P3 | `4cfd5b2` (22 files, +3003/-513) has no corresponding `work_log.md` entry, breaking this project's own "history goes to work_log.md" convention | [work_log.md](work_log.md) |

### 9.4 Remediation verification — 2026-08-11

Re-measured against the working tree, not accepted from the fix summary.

| Claim | Measured | Result |
|---|---|---|
| Full default `pytest -q` suite passes | `26 passed` | ✅ |
| `tests/test_eval_helpers.py` alone | `9 passed` (7 original + 2 new regression tests) | ✅ |
| `ruff check .` | `All checks passed!` | ✅ |
| `git diff --check` (whitespace) | clean | ✅ |
| New CLI regression test fails against pre-fix logic | traced by hand: pre-fix, a `human_verdict: null` spot row falls through the `!= "agree"` branch (no `continue`) and reaches `apply_one()`, changing `gold_doc_id`; the test asserts it stays `"original"` — a real regression guard, not a tautology | ✅ |

### 9.5 Issue disposition

| ID | Status |
|---|---|
| BUG-EH-001 | fixed |
| BUG-EH-002 | fixed |
| MIN-EH-003 | deferred — correct call, low blast radius, runs once per script invocation |
| MIN-EH-004 | deferred — process gap, not a code defect; noted so it isn't repeated |
