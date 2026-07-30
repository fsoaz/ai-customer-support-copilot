# Product

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things. Every number here is internal planning, never a claim made to anyone outside.

> Internal source of truth for *what* we are building and *why*. Architecture lives in
> [architecture.md](architecture.md); sequencing and gates live in [roadmap.md](roadmap.md).

## Vision

An intelligent copilot that assists customer-support agents by surfacing relevant knowledge and
drafting grounded, citation-backed responses — reducing handle time without removing the human from
the loop.

Sold as **multi-tenant SaaS**. Built by **one developer**. Both facts constrain every decision in
this repo more than any technical preference does.

## Users

| User | Needs | In V1? |
|---|---|---|
| **Tier-1 support agent** | Draft responses, relevant KB snippets, fast | **Yes — the only user we build for** |
| **Tier-2/3 specialist** | Case summarisation, cross-system lookup | No — Stage 4 |
| **Support manager** | Quality monitoring, analytics, coaching | Partially — Stage 3 admin dashboard |
| **End customer** | Self-service deflection | No — Stage 4 at the earliest |

Tier-1 agents are the wedge. Everyone else is a later expansion driven by paying-tenant demand.

## V1 scope — the wedge

**Grounded draft replies with citations.**

An agent opens a ticket in their helpdesk. A sidebar shows a suggested reply, streamed, where every
factual claim carries an inline citation linking to the knowledge-base chunk it came from. The
agent sends it, edits it, or ignores it. We record which.

That is the entire product for V1. It is chosen because it has the highest willingness-to-pay, and
because citations are the credible answer to the objection every buyer raises first — "how do I
know it isn't making things up?"

### Non-goals for V1

Explicitly **not** built, so scope drift is a visible violation rather than a judgement call:

- Auto-triage, tagging, priority scoring, routing
- Sentiment detection
- Thread summarisation and handoff notes
- Customer-facing self-service chat widget
- Agentic actions (refunds, escalations, CRM writes)
- Manager analytics and quality scoring
- Multi-provider helpdesk support (Zendesk only in V1)
- Fine-tuning

Each is a real product. None ships before the wedge has paying tenants.

## Success metrics

The metrics in the original pitch (resolution time down 30–40%, cost per ticket down 20–35%) are
sales figures. This is what we plan against:

| Metric | Target | Notes |
|---|---|---|
| Agent handle time, KB-covered tickets | **↓ 10–20%** | Primary metric. Anything above is upside |
| Draft acceptance rate | **≥ 40%** sent verbatim or lightly edited | Measured via `edit_distance_ratio`, see [architecture.md](architecture.md) |
| Groundedness | **≥ 0.95** | Every claim traceable to a cited chunk |
| CSAT | Maintained, not degraded | We are not optimising this; we are protecting it |
| Cost per draft | **< $0.03** | Determines whether the unit economics work at all |

### KB coverage is the limiting factor

No copilot answers a question the knowledge base does not contain. Suggestion quality on covered
topics saturates quickly; the difference between a mediocre product and a good one is what fraction
of incoming tickets the KB covers at all.

Consequence: **knowledge-gap detection eventually matters more than prompt tuning.** Measure
coverage (share of tickets where retrieval clears the confidence threshold) from Stage 1 and report
it to tenants as a first-class number.

### Baselines must be captured before launch

None of the metrics above is provable without a pre-period baseline. Before suggestions are enabled
for any tenant, record their existing handle time, first-contact resolution rate, and resolution
time over a comparable window.

Without this, every ROI claim we make is unfalsifiable, and the first serious buyer will say so.

## Positioning risks

| Risk | Response |
|---|---|
| Helpdesk vendors ship native AI | Compete on grounding quality and citation transparency, not breadth of features. Being narrow is the strategy |
| Trust — agents ignore the suggestions | Citations, an honest refusal path, and measurement of edit distance so the product visibly improves |
| Cost per ticket exceeds value delivered | Cost logged per suggestion from the first call; per-tenant caps enforced at the router |
| Retrieval quality never reaches useful levels | Stage 0 answers this offline, before any product code exists. See [roadmap.md](roadmap.md) |
| Solo-founder bus factor | Boring, well-documented infrastructure. Every deferral in [architecture.md](architecture.md) records its revisit trigger |
