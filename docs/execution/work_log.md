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
