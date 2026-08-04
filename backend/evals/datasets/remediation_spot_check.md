# Remediation spot-check (Task 0.7)

Reviewed: 20 · agree=12 · disagree=8 · disagree_rate=40.00%

All disagreements include `human_correction` so apply can incorporate them.
Raw disagree_rate > 15% indicates heuristic judge is noisy; corrections are authoritative.

**Policy after high disagree rate:** did **not** wholesale-trust heuristic on changed/none.
Expanded approval (`remediation_judgments_approved.jsonl`): spot overrides authoritative;
`same` confirmed; `none`/`changed` accepted only under overlap delta rules, else keep current.
Effective apply: 20 relabel · 5 none · 133 confirm.

## 0. `q-3b040ceb8dc6026a` — agree
- bucket: changed
- judge chose: `auth0-articles-universal-login-customization-classic-md-274b70507d75`
- note: classic UL customization answers head-tag question

## 1. `q-c07454e67b2a60f9` — disagree
- bucket: changed
- judge chose: `auth0-articles-tokens-concepts-refresh-token-rotation-md-dc9891604a4a`
- correction: `auth0-articles-api-auth-tutorials-silent-authentication-md-ee038410b386`
- note: silent auth more load-bearing for SPA Safari refresh logout than RTR

## 2. `q-5a866cc7963fe38b` — disagree
- bucket: changed
- judge chose: `auth0-articles-mfa-guides-configure-step-up-web-apps-md-d65cfe7c24aa`
- correction: `none`
- note: candidates do not answer extracting MFA method from mfa_token

## 3. `q-11e5bff30e11ce3b` — agree
- bucket: changed
- judge chose: `auth0-articles-tokens-guides-revoke-refresh-tokens-md-2187fb761f2f`
- note: (none)

## 4. `q-4e52747342845b62` — disagree
- bucket: changed
- judge chose: `auth0-articles-connections-database-password-change-md-57bd52e3ea33`
- correction: `auth0-articles-mfa-guides-mfa-api-authenticate-md-df9835c81e0e`
- note: keep ROPG+MFA auth guide over password-change

## 5. `q-2ac9d13387f5b24d` — agree
- bucket: changed
- judge chose: `auth0-articles-api-auth-tutorials-authorization-code-grant-md-4b836748faec`
- note: (none)

## 6. `q-0f653d5a2c26b614` — agree
- bucket: changed
- judge chose: `auth0-articles-email-custom-md-e6f8f4402a9d`
- note: (none)

## 7. `q-11cdacafb7b23cdd` — disagree
- bucket: changed
- judge chose: `auth0-articles-logout-guides-redirect-users-after-logout-md-463d8a66921d`
- correction: `auth0-articles-protocols-oauth2-redirect-users-md-e21ba7b9a0ef`
- note: keep redirect-users-after-login; logout redirect weaker fit

## 8. `q-8d94771aa9e35895` — disagree
- bucket: none
- judge chose: `none`
- correction: `auth0-articles-universal-login-text-customization-prompts-common-md-5d90358a3fa0`
- note: text customization answers UL signup messages; heuristic none wrong

## 9. `q-7f77c690891f8bb4` — agree
- bucket: none
- judge chose: `none`
- note: viewport issue; text-elements gold was noise

## 10. `q-b4bdbcba6345c52b` — disagree
- bucket: same
- judge chose: `auth0-articles-api-auth-user-consent-md-a04893969fa8`
- correction: `none`
- note: user-consent is incidental first-link noise for org invite pending; none

## 11. `q-2aea3072f7d7d178` — agree
- bucket: same
- judge chose: `auth0-articles-tokens-guides-create-namespaced-custom-claims-md-dcb893e07dd2`
- note: custom claims for roles in token is load-bearing

## 12. `q-b4e0e6968b9a67b2` — agree
- bucket: same
- judge chose: `auth0-articles-mfa-index-md-27f16cef8aec`
- note: (none)

## 13. `q-83ba4c5f1fa9c808` — agree
- bucket: same
- judge chose: `auth0-articles-extensions-deploy-cli-guides-create-deploy-cli-application-manually-md-018015625205`
- note: (none)

## 14. `q-c3b973a95e5574f2` — disagree
- bucket: same
- judge chose: `auth0-articles-authorization-reference-rbac-limits-md-b8ad32e1ade0`
- correction: `none`
- note: entity-limit/RBAC limits does not answer user-created M2M apps

## 15. `q-1dbf3e61382c9e5b` — agree
- bucket: same
- judge chose: `auth0-articles-users-concepts-overview-user-account-linking-md-ae352f567c56`
- note: account linking plausible for external email AD user

## 16. `q-a42b5d7d1e512493` — agree
- bucket: topup
- judge chose: `auth0-articles-compliance-index-md-8d5a7bd57b3c`
- note: (none)

## 17. `q-badab8eb37f3a2f6` — agree
- bucket: topup
- judge chose: `auth0-articles-users-guides-bulk-user-imports-md-2137b2f582a8`
- note: (none)

## 18. `q-df6d45633687664f` — disagree
- bucket: topup
- judge chose: `auth0-articles-application-auth-current-server-side-web-md-706aabbf752a`
- correction: `none`
- note: neither candidate is about Allowed Web Origins configuration

## 19. `q-cabbf5e040d8d3a1` — agree
- bucket: topup
- judge chose: `auth0-articles-mfa-guides-configure-email-md-af9bc383af73`
- note: email MFA factor config is the answering doc

