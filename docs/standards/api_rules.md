# API Rules

> **LOCAL RECORDS ONLY.** `docs/` is an internal working notebook for whoever builds this repo.
> Not published, not shipped, not shown to customers, prospects, or any external party. These are
> our internal conventions — **not** the public API contract. The contract clients consume is the
> generated OpenAPI schema, and nothing in this file is a promise to an API consumer.

> FastAPI backend conventions. Data model and auth design:
> [../context/architecture.md](../context/architecture.md).

## Routing

- All routes under `/v1`. Version in the path, never in a header.
- Plural nouns, no verbs: `/v1/tickets/{id}/suggestions`, not `/v1/getSuggestions`.
- Nesting stops at two levels. Deeper relationships take a query parameter.
- `/healthz` (liveness) and `/readyz` (dependencies reachable) sit outside `/v1` and outside auth.

## Tenant scoping is mandatory

**Every data-touching route depends on `get_tenant_session`.** No exceptions.

```python
@router.post("/tickets/{ticket_id}/suggestions")
async def create_suggestion(
    ticket_id: UUID,
    body: SuggestionCreate,
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> SuggestionRead: ...
```

The dependency validates the Supabase JWT against JWKS, extracts `tenant_id` from the claims, and
opens a transaction with `set local role authenticated` and `set local request.jwt.claims`, so RLS
applies to everything the handler does.

Rules that follow from this:

- **Handlers never open their own sessions.** A handler that acquires a connection directly is
  bypassing RLS and is a security defect.
- **`tenant_id` is never accepted from a request body, query parameter, or header.** It comes from
  the verified token or it does not exist.
- The `service_role` connection is importable from exactly two places: migrations and
  `app/workers/`. A lint rule enforces this.
- Repositories filter on `tenant_id` explicitly *as well as* relying on RLS. Two independent
  mechanisms mean a cross-tenant leak needs two independent bugs.

## Idempotency

Helpdesk webhooks duplicate, retry, and arrive out of order. This is normal provider behaviour, not
an edge case.

- **Webhook ingestion** inserts into `ticket_events` with `unique (provider, external_event_id)` and
  handles the conflict as success. Duplicate delivery is a no-op, not a second suggestion and a
  second charge.
- Webhooks are **verified** (Zendesk signature) before the payload is parsed, and return `2xx`
  immediately after persisting. Processing happens on the job queue. Never do model work inside a
  webhook handler — providers time out and retry, which multiplies the work.
- **Mutating endpoints** accept an optional `Idempotency-Key` header. Same key plus same body
  returns the original response; same key plus different body returns `409`.
- Out-of-order events are resolved by comparing the provider's own timestamp, never arrival order.

## Request and response contracts

- Pydantic models for every request and response. No `dict[str, Any]` crossing a route boundary.
- Separate models per direction: `SuggestionCreate`, `SuggestionRead`, `SuggestionUpdate`. Never
  reuse the ORM model as a response schema — that is how internal columns leak.
- `snake_case` in JSON, matching the database and Python. No case translation layer.
- Timestamps are ISO 8601 UTC with an explicit offset.
- Collections return `{"items": [...], "next_cursor": "..."}`. Cursor pagination, not offset —
  offset pagination breaks under concurrent inserts.
- OpenAPI is generated from the code. Never hand-maintained.

## Errors

One envelope, everywhere:

```json
{
  "error": {
    "code": "insufficient_knowledge",
    "message": "No knowledge base content matched this ticket with sufficient confidence.",
    "request_id": "01HQ...",
    "details": {}
  }
}
```

- `code` is a stable, typed, machine-readable string. Clients branch on `code`, never on `message`.
- `message` is safe to show a human.
- **Internal detail never leaks.** No provider names, model IDs, prompt text, stack traces, or SQL
  in a client-facing response. `request_id` correlates to the full internal trace.

| Status | Used for |
|---|---|
| 400 | Malformed request |
| 401 | Missing or invalid token |
| 403 | Valid token, insufficient role |
| 404 | Not found **or** belongs to another tenant — never distinguish the two |
| 409 | Idempotency conflict, or state conflict |
| 422 | Pydantic validation failure |
| 429 | Rate limit or tenant quota exceeded, with `Retry-After` |
| 502 | Upstream provider failed after retries and fallbacks |

404-not-403 for other tenants' resources is deliberate: a 403 confirms the resource exists, which
is itself a cross-tenant information leak.

## Streaming

Draft generation streams over SSE. Latency to first token is a Stage 1 gate
([../context/roadmap.md](../context/roadmap.md)), and it cannot be met by buffering.

```
event: token
data: {"text": "Your subscription renews on "}

event: citation
data: {"chunk_id": "uuid", "kb_id": "uuid", "title": "Billing cycles", "marker": 1}

event: done
data: {"suggestion_id": "uuid", "cited_chunk_ids": ["uuid"], "latency_ms": 1830}

event: error
data: {"error": {"code": "insufficient_knowledge", "message": "..."}}
```

- Citations arrive as their own events as they resolve, so the sidebar can render markers
  progressively.
- **The suggestion row is written before `done` is emitted.** A stream the client drops must still
  be logged — otherwise the acceptance-rate denominator is wrong.
- Errors mid-stream arrive as an `error` event; the HTTP status is already sent and cannot change.
- Heartbeat comments every 15 s to survive proxy idle timeouts.

## Rate limits and resilience

- Per-tenant rate limits on suggestion creation, enforced in the router layer. Headers:
  `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
- Spend caps are enforced before the model call, not by an alert afterwards. See
  [ai_agent_rules.md](ai_agent_rules.md).
- Circuit breakers on every outbound helpdesk client. An unavailable Zendesk must degrade the
  product, not take it down.
- Explicit timeouts on every outbound call. No unbounded waits anywhere.
- Retries use exponential backoff with jitter, and only on idempotent operations.

## Observability

- Every request carries a `request_id`, propagated to logs, traces, and error responses.
- Structured JSON logs. `tenant_id` and `request_id` on every line; **never** raw customer content.
- OpenTelemetry spans across the request path; Langfuse for the model call itself.

## Security

- CORS allow-list is explicit: the Zendesk app origin and the Vercel dashboard origin. Never `*`.
- Zendesk webhook signatures verified before parsing.
- The Supabase `service_role` key exists only in Fly secrets. It never reaches the frontend, the
  Zendesk app, or a log line.
- Request body size limits on every endpoint, especially KB upload.
- Bulk endpoints are paginated and capped; there is no unbounded export.
