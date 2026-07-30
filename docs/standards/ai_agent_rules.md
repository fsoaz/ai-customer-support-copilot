# AI / LLM Rules

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. It is not
> product documentation and not an API contract — it records how we build and why we decided
> things.

> Binding rules for any code path that calls a model. Violations are bugs, not style opinions.
> Retrieval design: [../context/architecture.md](../context/architecture.md).
> How these are verified: [testing.md](testing.md).

## 1. Grounding is mandatory

**Every factual claim in a generated draft carries an inline citation resolving to a real
`kb_chunks.id`.**

- Citations are validated after generation, not trusted. A cited ID that does not exist, or belongs
  to another tenant, fails the request — it does not get logged as a warning and returned anyway.
- `cited_chunk_ids` must be a subset of `retrieved_chunk_ids`. A model citing something it was
  never shown is a fabricated citation, which is worse than no citation.
- An uncitable claim is a **bug**. If the model produces prose that asserts something no retrieved
  chunk supports, that is a defect to fix in the prompt or the validator, not an acceptable
  degradation.

Rationale: citation transparency is the product's entire answer to "how do I know it isn't making
things up?" A citation that is not verified end-to-end is worse than none, because it manufactures
unearned trust.

## 2. The refusal path is a feature

When fused retrieval scores fall below the confidence threshold, return an explicit **"insufficient
knowledge"** response. Never generate an ungrounded draft as a fallback.

- The threshold is a tuned constant, recorded with its eval evidence in
  [../execution/test_evidence.md](../execution/test_evidence.md), not a magic number in code.
- Refusals are logged as suggestions with `kind='draft'` and no content, so refusal rate is
  measurable. Refusal rate *is* the KB coverage metric described in
  [../context/product.md](../context/product.md).
- A rising refusal rate is a knowledge-base problem to surface to the tenant, not a model problem to
  paper over.

## 3. PII redaction runs before every model call

No customer content reaches a model provider un-redacted. Presidio-based detection, applied in
`app/ai/redact.py`, before the prompt is assembled.

- Redaction has its own golden set testing **both** failure directions:
  - **Under-redaction** — PII leaks to the provider. Compliance failure.
  - **Over-redaction** — the ticket is stripped of the detail that makes it answerable. Quality
    failure, and the one people forget to test.
- Placeholders are stable and typed (`<EMAIL_1>`, `<ORDER_ID_2>`) so the model can still reason
  about relationships between redacted entities.
- Rehydration happens only in the response returned to the agent, never in logs or traces.

## 4. Prompts are versioned artifacts

- Prompts live as files under `app/ai/prompts/`. Never inline in application code, never assembled
  from string fragments scattered across modules.
- Each prompt is content-hashed. The hash is written to `ai_suggestions.prompt_version` on every
  call.
- Changing a prompt requires an eval run. See [testing.md](testing.md).

Rationale: this is what makes a quality regression **attributable**. Without it, a drop in
acceptance rate three weeks after a prompt tweak is an unsolvable mystery.

## 5. Model routing

A thin internal router (`app/ai/router.py`) owns all provider access. No module calls a provider
SDK directly.

| Task | Model class | Why |
|---|---|---|
| Draft generation | Frontier | Quality is the product |
| Reranking | Hosted reranker API | Purpose-built, cheaper than an LLM call |
| Classification, extraction | Small/fast | 20–50× cheaper, adequate accuracy |
| Fallback on provider failure | Rule-based template | Always available, never wrong-but-confident |

Rules:

- **Model IDs are configuration, never hardcoded at call sites.** Pin explicit versioned IDs;
  never point at a floating alias, because a silent provider upgrade invalidates every eval
  baseline overnight.
- Re-evaluate the model choice at each stage gate. The model list in the original project pitch
  (GPT-4o, Claude 3.5 Sonnet, Gemini 1.5 Pro) was already superseded when it was written — treat
  any model list in a document as stale by default and check the provider's current lineup.
- Every provider call has an explicit timeout and a bounded retry policy with jitter.
- On exhausted retries, fall back down the chain: frontier → smaller model → rule-based template.
  Never return a 500 to an agent mid-ticket if a template can serve.

## 6. Every call is traced, from the first call

Emit to Langfuse on every model invocation:

`tenant_id` · `prompt_version` · `model_id` · `retrieved_chunk_ids` · `cited_chunk_ids` ·
`prompt_tokens` · `completion_tokens` · `cost_usd` · `latency_ms` · `ttft_ms`

This is not observability polish added before launch. It is the data that Stage 1's gate is
measured against, and it cannot be backfilled.

Traces contain redacted content only. Raw customer text never leaves the database.

## 7. Cost control is enforced, not monitored

- Per-tenant monthly spend caps enforced **at the router**, before the call, not by an alert
  afterwards.
- Per-request token ceilings on both context and completion.
- Retrieved context is capped by token budget, not by chunk count.
- Approaching a cap degrades gracefully — cheaper model, then templates — and notifies the tenant
  admin. It never silently stops working.

`cost_usd` on every suggestion is what makes per-tenant unit economics knowable, which is what makes
Stage 3 billing possible. It cannot be reconstructed later.

## 8. Determinism where it matters

- Temperature 0 for classification, extraction, and evaluation. Low temperature for drafting.
- Eval runs pin model ID, prompt version, and retrieval parameters. An eval that cannot be
  reproduced is not evidence.
- LLM-as-judge prompts are versioned like any other prompt. Changing the judge invalidates the
  baseline and requires a re-baseline run, clearly recorded as such.

## 9. Human in the loop

V1 suggests; it never sends. No generated content reaches a customer without an agent's explicit
action.

When Stage 4 introduces actions (refunds, escalations, CRM writes), the rule tightens rather than
relaxes: **suggestions may be automatic, actions require approval.** Every action is logged with
the approving user, the suggestion that prompted it, and the state before and after.

## 10. Tenant isolation applies to the AI path too

Retrieval is executed through the tenant-scoped session
([../context/architecture.md](../context/architecture.md)). The AI layer never receives a
`tenant_id` as a plain function argument that a caller could get wrong — it inherits the scoped
session and cannot reach outside it.

The cross-tenant isolation test in [testing.md](testing.md) exercises exactly this path and is
non-negotiable in CI.
