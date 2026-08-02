# Project Structure

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things.

> Map of what exists on disk today versus what [architecture.md](architecture.md) plans later.
> Product intent: [product.md](product.md). Sequencing: [roadmap.md](roadmap.md).

## What this repo is

A **multi-tenant SaaS copilot** for Tier-1 support agents: open a Zendesk ticket → sidebar drafts a
reply where every factual claim cites a knowledge-base chunk → agent sends/edits/ignores → product
measures which.

**Right now it is pre-product.** Stage 0 asks one question offline: can hybrid retrieval find the
right KB doc for a real support question? Product API, UI, Postgres, and Zendesk are intentionally
absent until the Stage 0 gate passes (`recall@10 ≥ 0.85`, `MRR ≥ 0.60`). Best so far: recall@10 ≈
**0.368** (dense_weight=2 on bge-base / 256 chunks) — gate still fails. Task 0.6 call: remediate
golden labels (BUG-014) before more embedder sweeps. Live status:
[../execution/current_task.md](../execution/current_task.md).

```
Repo today                          Planned later (docs only)
─────────────────                   ─────────────────────────
docs/  (planning notebook)    →     same, never shipped
backend/evals/ (retrieval)    →     FastAPI + worker on Fly.io
(nothing else)                →     Supabase Postgres + RLS
                              →     Zendesk ZAF sidebar
                              →     Next.js admin on Vercel
```

## Top-level layout

```
ai-customer-support-copilot/
├── README.md          # product pitch + Stage 0 commands
├── LICENSE
├── .gitignore         # .env, corpus raw/, store DB, reports
├── docs/              # internal working notebook (not product docs)
└── backend/           # sole code package (uv / Python 3.12)
```

Not a monorepo. No `apps/`, `packages/`, Docker, frontend, migrations, or `.env.example` yet.
Planned top-level dirs (`frontend/`, `zendesk-app/`, `supabase/`) are described in
[../standards/conventions.md](../standards/conventions.md) and appear only when Stage 1+ starts.

## `docs/` — how the project thinks

| Folder | Role |
|---|---|
| [context/](.) | **What / when / how:** [product.md](product.md), [roadmap.md](roadmap.md), [architecture.md](architecture.md), this file |
| [../standards/](../standards/) | Engineering rules: conventions, API, testing, AI agent (citations + refusal) |
| [../execution/](../execution/) | Live work: current task, work log, test evidence, QA/review notes |

Reading order: [product.md](product.md) → [roadmap.md](roadmap.md) → [architecture.md](architecture.md)
→ this file when orienting to the tree.

### Target product shape (not implemented)

```
Zendesk ZAF sidebar ──┐
                      ├── JWT ──► FastAPI (Fly.io) ──► Supabase Postgres (RLS)
Next.js admin (Vercel)┘
```

V1 wedge only: grounded cited drafts in Zendesk. Triage, summarisation, self-service, agentic
actions deferred — see [product.md](product.md).

Roadmap stages: **0** prove retrieval → **1** generation API + evals → **2** Zendesk + ingest →
**3** admin + sellable V1 → **4** later expansions.

## `backend/` — what actually runs

Single uv project ([../../backend/pyproject.toml](../../backend/pyproject.toml)): Python ≥3.12,
deps `fastembed`, `flashrank`, `httpx`, `numpy`, BeautifulSoup, pytest/ruff.

```
backend/
├── evals/                 # Stage 0 product-so-far
│   ├── harness/           # library: clean → chunk → embed → store → retrieve → metrics
│   ├── scripts/           # CLIs: fetch, ingest, smoke, golden build, first-stage audit
│   ├── runners/           # full golden-set eval
│   ├── corpus/auth0/      # pinned Auth0 MIT docs (+ forum samples)
│   ├── datasets/          # retrieval_golden.jsonl
│   ├── store/             # SQLite chunk/embed DB (mostly gitignored; side-by-side stores)
│   └── reports/           # eval JSON outputs (gitignored)
└── tests/                 # unit tests for harness/metrics/rerank
```

### Harness modules (`backend/evals/harness/`)

| Module | Job |
|---|---|
| `clean.py` / `chunking.py` | HTML/text clean; default ~512 tokens, 15% overlap (best store uses 256) |
| `embed.py` | fastembed bi-encoders; optional BGE query prefix at query time |
| `ingest_meta.py` | Per-DB ingest fingerprint (SQLite meta → sidecar → default) |
| `store.py` | SQLite: `documents`, `chunks` (+ embedding BLOB), FTS5, `meta` |
| `retrieve.py` | HybridRetriever: dense + FTS5 → weighted RRF → optional FlashRank |
| `rrf.py` / `rerank.py` / `metrics.py` | Fusion (optional weights), cross-encoder, recall/MRR/nDCG |
| `paths.py` | Corpus / golden / store path constants |

Stand-in for future `pgvector` + `tsvector`: local numpy cosine + SQLite FTS5.

### Stage 0 pipeline

```
fetch_docs → corpus/auth0/docs/raw
     ↓
ingest_docs: clean → chunk → embed → ChunkStore (SQLite + FTS5)
     ↓
query → HybridRetriever: dense + lexical → RRF (optional weights) → [optional FlashRank]
     ↓
runners.retrieval vs retrieval_golden.jsonl → evals/reports/*.json
analyze_first_stage → pool/channel ceiling curve + miss sample
```

**CLIs** (from `backend/`, via `uv run python -m …`):

- `evals.scripts.fetch_docs` / `fetch_forum` / `parse_docs_manifest` / `build_golden`
- `evals.scripts.ingest_docs` — clean → chunk → embed → SQLite (`--model` / `--db` / `--chunk-tokens`)
- `evals.scripts.smoke_retrieve` — coverage + hit@50 smoke
- `evals.scripts.analyze_first_stage` — dense/lexical/fused pool curve + miss sample
- `evals.runners.retrieval` — full golden metrics; `--rerank`, `--dense-weight`, `--bge-query-prefix`

### Corpus and data scale (local)

- Auth0 docs corpus, pinned commit; **1734** docs indexed
- Side-by-side stores: bge-small 512 (2688 chunks); bge-base 512; **bge-base 256 (4364 chunks)** — best
- Golden set: 359 answerable + 31 unanswerable
- Best measured config: bge-base / 256 chunks / RRF `dense_weight=2` → recall@10 **0.368**
- Measured numbers: [../execution/test_evidence.md](../execution/test_evidence.md)

## What is deliberately missing

No FastAPI app, Next.js admin, Zendesk app, Supabase migrations, Docker, Langfuse wiring, or LLM
draft generation. Roadmap forbids starting those until Stage 0 clears.

Active next step: **task 0.7** — golden-label remediation (BUG-014)
([../execution/current_task.md](../execution/current_task.md)). Task 0.6 call: Stage 0 gate is
**not solvable** on the current golden set without fixing labels; best measured recall@10 **0.368**
(dense_weight=2 on bge-base / 256 chunks).

## Mental model

| Layer | Status |
|---|---|
| Product vision + architecture | Documented in `docs/context/` |
| Retrieval quality hypothesis | Being tested in `backend/evals/` |
| SaaS product surface | Not started |

Treat `backend/evals/` as a **scientific instrument** for the riskiest assumption; treat `docs/` as
the design of everything that comes after the gate passes.
