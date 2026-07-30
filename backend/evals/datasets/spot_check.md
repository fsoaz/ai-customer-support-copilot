# Spot-check — Auth0 retrieval golden set (post-QA remediation)

> **LOCAL RECORDS ONLY.** Manual review of 20 answerable pairs: is the linked docs page
> actually the answer (or load-bearing for it), or merely incidental?

**Dataset:** `evals/datasets/retrieval_golden.jsonl`  
**Reviewed:** 2026-07-30 (remediation pass)  
**Method:** seeded RNG shuffle of all answerable rows (`seed=20260730`,
`method=rng_shuffle_all_answerable` in `spot_check_candidates.jsonl`). First 20 of the 40
candidates reviewed. **Not** a deterministic head of a diversified list (BUG-006 fixed).

| # | Verdict | Thread topic (short) | Gold doc | Notes |
|---|---|---|---|---|
| 1 | pass | Python SPA token validation | validate-json-web-tokens | Direct match |
| 2 | fail | Configure SMTP via Yournotify | allowlist | Incidental; SMTP/email provider ≠ IP allowlist |
| 3 | pass | Account Linking Extension 400 | user-account-linking | Direct match |
| 4 | pass | Enforce Email MFA but SMS fires | configure-email-notifications-for-mfa | Direct match |
| 5 | pass | Session inactivity django+react | configure-session-lifetime-settings | Direct match |
| 6 | pass | Custom domain push notifications | configure-push-notifications-for-mfa | Direct match |
| 7 | fail | Login page very small on Android | customize-text-elements | Incidental; layout/viewport ≠ text copy |
| 8 | pass | .NET Management API support window | product-support-matrix | Direct match |
| 9 | pass | Transfer users between tenants w/ password | export-data | Load-bearing for migration/export path |
| 10 | pass | Same-email login conflict | user-account-linking | Direct match |
| 11 | fail | Invite Organization members link issue | user-consent-and-third-party-applications | Weak/incidental vs org invites |
| 12 | pass | invalid signature `flo` log | log-event-type-codes | Direct match for log diagnosis |
| 13 | pass | Force password change on first login | classic-experience | Related Classic Login behaviour |
| 14 | pass | Invite-only signup | send-email-invitations-for-application-signup | Direct match |
| 15 | pass | Custom DB login/getUser not invoked | create-db-connection | Direct match |
| 16 | pass | auth0.js "No verifier returned" | auth0js | Direct match |
| 17 | pass | Reset password link blank page | email-templates | Direct match |
| 18 | fail | B2B multi-tenant architecture SoT | manage-subscriptions | Incidental; architecture ≠ subscriptions |
| 19 | pass | Searchable indexed custom attributes | metadata | Direct match |
| 20 | pass | OpenStreetMap OAuth failed transaction | oauth2 social IdP | Direct match |

## Summary

- **16 / 20 pass** (80%) on a seeded random sample
- **4 fails** — first-link-in-accepted-answer noise (BUG-014; deferred through 0.2)
- Population: **357** mirror-backed answerable, **0** synthetic, **31** hand unanswerable
  (25 near-miss + 6 absurdist)

Sample JSON: `evals/datasets/spot_check_sample.json`
