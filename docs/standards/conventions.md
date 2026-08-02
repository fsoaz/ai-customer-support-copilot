# Conventions

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things.

> Repo-wide working agreements. API specifics: [api_rules.md](api_rules.md). Model specifics:
> [ai_agent_rules.md](ai_agent_rules.md).

## Repo layout

**Target** (Stage 1+; not all present yet):

```
backend/          FastAPI + evals  → Fly.io
frontend/         Next.js admin    → Vercel
zendesk-app/      ZAF v2 sidebar   → static bundle
supabase/         migrations
docs/             context / standards / execution
```

**Today (Stage 0):** only `docs/` and `backend/evals/` (+ `backend/tests/`). See
[../context/structure.md](../context/structure.md). Target shape:
[../context/architecture.md](../context/architecture.md).

### Module boundaries in `backend/app/`

- `api/` — HTTP only. Validation, serialisation, dependency wiring. **No business logic, no SQL.**
- `ai/` — model access, retrieval, prompts, redaction. Receives a scoped session; never opens one.
- `ingest/` — connectors, chunking, embedding.
- `db/` — models and repositories. The only place SQL lives.
- `workers/` — queue consumers. The only place outside migrations that may use `service_role`.

Dependency direction is one-way: `api → ai/ingest → db`. `db` imports nothing from the layers above
it. A circular import is a design error, not something to work around with a local import.

## Git

- **Trunk-based.** Short-lived branches off `main`, merged within a day or two. No long-running
  feature branches — solo development plus long branches produces merge archaeology with no
  reviewer to justify it.
- **Conventional Commits**: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`, `perf:`.
  Scope where useful: `feat(retrieval): add RRF fusion`.
- Subject line ≤ 50 characters, imperative mood. Body only when the *why* is not obvious from the
  diff — and when it is not obvious, the body is mandatory.
- Squash-merge to `main`. `main` stays releasable at every commit.

## Migrations

- Live in `supabase/migrations/`, applied with the Supabase CLI.
- **Forward-only.** Never edit a migration after it has been merged — write a new one.
- Timestamp-prefixed filenames, one logical change each.
- Every migration is tested up → down → up in CI ([testing.md](testing.md)).
- Destructive changes are two-phase: deploy code tolerating both shapes, then drop in a later
  migration. Never in the same deploy.
- Every new tenant-scoped table gets `tenant_id`, an RLS policy with **both** `using` and
  `with check`, and an index on `tenant_id` — in the same migration that creates it, not a
  follow-up.

## Secrets and configuration

| Where | What |
|---|---|
| Fly secrets | Supabase `service_role` key, provider API keys, Langfuse keys |
| Vercel env vars | Supabase URL, Supabase anon key, public API base URL |
| `.env.example` | Committed. Every variable listed, no values |
| `.env` | **Never committed.** In `.gitignore` from the first commit |

- The **anon key is frontend-only**. The **`service_role` key is backend-only** and never appears in
  a log line, a trace, an error response, or the Zendesk app bundle.
- Configuration is read once at startup into a Pydantic `Settings` object. No `os.environ` lookups
  scattered through the code.
- The app fails fast and loudly at boot on missing required config. It never starts in a degraded
  state and discovers the problem on the first request.

## Languages and tooling

### Python (`backend/`)

- Python 3.12+, dependencies managed with **uv**. `uv.lock` is committed.
- **ruff** for linting and formatting. **mypy** strict on `app/ai/` and `app/auth/`, standard
  elsewhere.
- Type hints on every function signature. `Any` requires a comment justifying it.
- `async def` throughout the request path. A blocking call inside an async handler is a bug — it
  stalls the whole event loop.
- Custom exceptions inherit from a single `AppError` base carrying the typed error code from
  [api_rules.md](api_rules.md).

### TypeScript (`frontend/`, `zendesk-app/`)

- **pnpm**, ESLint, `strict: true`. No `any`, no `@ts-ignore` without an adjacent explanation.
- Server Components by default in Next.js; `"use client"` only where interactivity requires it.
- TanStack Query for server state, Zustand for client state, matching the original stack choice.
- API types generated from the backend OpenAPI schema. Never hand-written and never allowed to
  drift.

## Naming

| Context | Style | Example |
|---|---|---|
| Postgres tables, columns | `snake_case`, plural tables | `kb_chunks`, `edit_distance_ratio` |
| Python | `snake_case`, `PascalCase` classes | `retrieve_chunks`, `SuggestionRead` |
| TypeScript | `camelCase`, `PascalCase` components | `useSuggestion`, `CitationList` |
| JSON payloads | `snake_case` | Matches DB and Python; no translation layer |
| Env vars | `SCREAMING_SNAKE_CASE` | `SUPABASE_SERVICE_ROLE_KEY` |
| Branches | `type/short-description` | `feat/rrf-fusion` |

`tenant_id` is the universal scoping column name. Never `org_id`, `account_id`, `company_id`, or
`customer_id` for the same concept. One name, everywhere, so that grepping for it finds every place
tenancy matters.

## Documentation

`docs/` is **local records only** — the internal source of truth for how and why we build. It is
never published, shipped, embedded in the product, or shared with customers, prospects, investors,
or any other external party. If something in here needs an outside audience, it gets rewritten for
that audience somewhere else; `docs/` itself is never the artifact that leaves.

Every file carries this notice in its header. Keep it there when editing, and add it to any new file
placed under `docs/`.

It is expected to stay current.

| Directory | Contents | Updated |
|---|---|---|
| `context/` | Product, architecture, roadmap | When a decision changes |
| `standards/` | These rules | When a convention changes |
| `execution/` | Current task, work log, review notes, test evidence | Continuously |

- A PR that changes an architectural decision updates
  [../context/architecture.md](../context/architecture.md) in the same PR. Documentation drift is
  reviewed like any other defect.
- Record **why**, not what. The diff already shows what.
- **Every deferral records its revisit trigger.** "We chose X over Y" without "revisit when Z" is an
  incomplete decision, and in twelve months nobody will remember whether it was reasoning or
  accident.

## Code review

Solo development means no second reviewer, so the automated gates in [testing.md](testing.md) carry
the weight a human reviewer normally would. Do not merge past a red check by hand.

Self-review discipline: open the PR, read the full diff in the web UI, and let the eval diff post
before merging. Reading the diff in a different surface than the one you wrote it in catches a
surprising amount.
