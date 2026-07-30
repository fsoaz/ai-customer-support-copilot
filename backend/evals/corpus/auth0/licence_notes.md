# Auth0 proxy corpus — licence and terms notes

> **LOCAL RECORDS ONLY.** Internal Stage 0 eval materials. Not published, not shipped in the
> product, not shared with customers or prospects.

## Product selected

**Auth0** — documentation + [community.auth0.com](https://community.auth0.com) (Discourse).

Elastic was considered and rejected: elastic.co Terms of Use forbid site scraping, and current
docs content is CC BY-NC-ND 4.0 (non-commercial / no-derivatives), which fails the selection
criterion "terms of use permitting the crawl" for a commercial SaaS eval corpus.

## Documentation

| Item | Detail |
|---|---|
| Source | Public GitHub clone of [auth0/docs](https://github.com/auth0/docs) |
| Licence | **MIT** (`LICENSE` in that repository) |
| Method | `git clone` via `evals/scripts/fetch_docs.py` — **not** HTML scraping of auth0.com |
| Pin | **Enforced** via `docs/expected_commit.txt` (fail on mismatch). Also recorded in `fetch_meta.json` / `manifest.json` |
| Redirects | Committed `redirects_flat.json`. Normal parse does **not** execute upstream JS; `--dump-redirects` is opt-in only |
| Use | Offline retrieval eval only; retain copyright notice when redistributing excerpts internally |

Canonical public URLs (`https://auth0.com/docs/...`) are derived from article paths plus the
committed redirects map. We do not fetch rendered HTML from auth0.com for the corpus.

### Regenerate docs raw

```bash
cd backend
uv run python -m evals.scripts.fetch_docs          # clones pinned SHA into docs/raw/
uv run python -m evals.scripts.parse_docs_manifest # uses committed redirects_flat.json
```

`docs/raw/` is gitignored (nested `.git` from the clone). See `docs/RAW_README.md`.

## Forum (community.auth0.com)

| Item | Detail |
|---|---|
| Source | Public Discourse JSON (`/c/*.json`, `/t/*.json`) |
| robots.txt | Honoured: `/search` not used; identifying User-Agent `CorpCorpusBot/0.1` |
| Rate limit | ~0.3–0.5 s sleep; multi-attempt 429 with `Retry-After`; failures → `harvest_failures.jsonl` |
| Content | User-generated Q&A; accepted answers used only to label (question → gold doc URL) |
| Use | Local eval ground truth only; raw topic JSON is gitignored and regenerable |

### Regenerate forum raw

```bash
cd backend
uv run python -m evals.scripts.fetch_forum --categories 6 --max-topics 2000
uv run python -m evals.scripts.build_golden
```

`forum/raw/` is gitignored. Index is rebuilt from raw at end of harvest. See `forum/RAW_README.md`.

## Dataset artefacts

- `evals/datasets/retrieval_golden.jsonl` — mirror-backed golds only (no `auth0-url-*` synthetics)
- `evals/datasets/coverage_report.json` — build-time coverage gate (must be 100%)
- Questions redacted at build time (`<EMAIL_n>`, `<TENANT_n>`)
- Unanswerable rows are hand-authored (`negative_slice`: `near_miss` | `absurdist`)
- Corpus is **not** embedded in the customer-facing product

## Checklist

- [x] Docs obtained under MIT from GitHub
- [x] No auth0.com HTML scrape for the docs corpus
- [x] Forum harvest robots-compliant
- [x] Pin enforced; redirects not executed by default
- [x] Internal / local-records-only use recorded
