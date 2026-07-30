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
