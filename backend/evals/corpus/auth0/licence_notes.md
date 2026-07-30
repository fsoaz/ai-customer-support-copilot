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
| Pin | Commit SHA recorded in `docs/fetch_meta.json` and `docs/manifest.json` |
| Use | Offline retrieval eval only; retain copyright notice when redistributing excerpts internally |

Canonical public URLs (`https://auth0.com/docs/...`) are derived from article paths plus the
repo's `config/redirects.js` map. We do not fetch rendered HTML from auth0.com for the corpus.

## Forum (community.auth0.com)

| Item | Detail |
|---|---|
| Source | Public Discourse JSON (`/c/*.json`, `/t/*.json`) |
| robots.txt | Honoured: `/search` not used; SEO bots disallowed separately; we use an explicit research User-Agent (`CorpCorpusBot/0.1`) — never `Go-http-client` |
| Rate limit | ~0.5–1 req/s with retries on 429 |
| Content | User-generated Q&A; accepted answers used only to label (question → gold doc URL) |
| Use | Local eval ground truth only; raw topic JSON is gitignored and regenerable |

## Dataset artefacts

- `evals/datasets/retrieval_golden.jsonl` — (question, gold_doc_*) pairs for Stage 0 metrics
- Corpus is **not** embedded in the customer-facing product and is not a benchmark claim for
  external marketing
- Some golden URLs are newer than the GitHub mirror; those use synthetic `auth0-url-*` ids.
  Stage 0.2 must obtain page bodies for those URLs (GitHub alone is incomplete vs production docs).

## Checklist

- [x] Docs obtained under MIT from GitHub
- [x] No auth0.com HTML scrape for the docs corpus
- [x] Forum harvest robots-compliant
- [x] Internal / local-records-only use recorded
