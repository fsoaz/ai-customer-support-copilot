# Spot-check — Auth0 retrieval golden set

> **LOCAL RECORDS ONLY.** Manual review of 20 answerable pairs: is the linked docs page
> actually the answer (or load-bearing for it), or merely incidental?

**Dataset:** `evals/datasets/retrieval_golden.jsonl`  
**Reviewed:** 2026-07-30  
**Method:** Diverse sample by `gold_doc_id` (first 20 unique gold docs)

| # | Verdict | Thread topic (short) | Gold doc | Notes |
|---|---|---|---|---|
| 1 | pass | Enterprise SAML IdP-initiated SSO via API | identity-provider-initiated-single-sign-on | Direct match |
| 2 | pass | Add org_id to ROPG access token | resource-owner-password-flow | Correct flow doc; org claim details may need Actions too |
| 3 | pass | SAML cert vs signingCert | sign-and-encrypt-saml-requests | Direct match |
| 4 | pass | Force MFA enroll via Universal Login | login-trigger | Actions login trigger is the documented approach |
| 5 | pass | IP range for tenant domain | allowlist | Direct match |
| 6 | pass | Custom Action typings for event/api | post-login-event-object | Direct match |
| 7 | pass | Disable signup in embedded Lock | lock-configuration | Direct match |
| 8 | pass | Passwordless email + multiple domains | multiple-custom-domains | Direct match |
| 9 | fail | Node 22 upgrade "unexpected end of file" | write-your-first-action | Incidental Actions intro; not a Node runtime page |
| 10 | pass | Password reset on first login (admin-created) | customize/actions | Actions are the correct mechanism |
| 11 | pass | Multiple allowed web origins / redirect | redirect-users-after-login | Direct match |
| 12 | pass | Persist auth across apps/domains (MFE) | configure-silent-authentication | Direct match |
| 13 | pass | ACUL docs vs linked GitHub repo | acul sdk-quickstart | Thread is about that doc page |
| 14 | fail | Playwright + Authorization Code Flow | update-access-token-lifetime | Token lifetime page is incidental to e2e testing question |
| 15 | pass | invalid_grant refresh token in Next.js | configure-refresh-token-expiration | Direct match |
| 16 | pass | No 3rd-party refresh_token Azure AD | token-vault | Direct match |
| 17 | pass | Expiration for signup URL | send-email-invitations-for-application-signup | Related invitation/signup URL guidance |
| 18 | pass | Android redirect after login | enable-android-app-links-support | Direct match |
| 19 | pass | Auth0 + Okta existing user linking | link-user-accounts | Direct match |
| 20 | pass | Email with SSO in Identifier First | customize-signup-and-login-prompts | Direct match |

## Summary

- **18 / 20 pass** (90%)
- **2 fails** — accepted-answer docs link was tangential (runtime upgrade; Playwright testing)
- Acceptable for Stage 0.1 ground truth; expect some label noise. Do not treat 100% label purity as required before retrieval work (0.2+)

Sample JSON for these 20 rows: `evals/datasets/spot_check_sample.json`
