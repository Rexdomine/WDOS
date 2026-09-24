# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `feat/stage-03-onboarding`
- Target: `staging`
- Exact candidate identity: `3634e167a3113894bb1fce97e7b5df98eaa39028` (read back locally and from live PR 4 during this evidence refresh; candidate tree `99229fed2522f88c57f9a8b914ed60cfc7ef39d2`).
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `/opt/data/tmp/wdos-stage3/arabic-final-verify.log` | PASS: 169 tests, 73.348s, canonical exit 0. |
| Same-family quota regression | `accounts.test_onboarding` + `accounts.test_configuration` | PASS: 34 tests under isolated SQLite; full-draft quota returns 429 before Pillow image decoding, with revision/history unchanged. |
| Hosted exact-head CI | GitHub Actions run `36071033105` on `3634e167a3113894bb1fce97e7b5df98eaa39028` | PASS: `django`, `ui-browser`, CodeRabbit, and GitGuardian all successful. The hosted `ui-browser` job runs Stage 2 only; it is not Stage 3 browser/reference evidence. Codex code and security reviews completed on this head; the current candidate still requires exact-candidate UI evidence and Rex acceptance. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Both manifests identify the capture source tree as `e1be979c...ffb1`; this is pre-packaging evidence and does not prove exact-head equivalence. The implementation delta after capture includes server-side review/consent/route hardening, operator audit provenance, locale precedence, request-body upload protection, focused regressions, and the accepted-state template correction; these changes require exact-candidate acceptance evidence. |
| Arabic/localization repair | `arabic-final-verify.log`; `accounts/test_locale.py` | PASS on the candidate. The catalog fragment `تفضيلات الحركة` was repaired and exercised. |
| Recovery/lost-response review | `/opt/data/tmp/wdos-stage3/postcommit-independent-closeout.md` | PASS: 7 focused tests. |
| Visual recovery review | `/opt/data/tmp/wdos-stage3/recovery-final-acceptance.md` | Parent fresh-vision review reports no remaining Arabic fragment or clipping blocker. |
| Browser capture inventory | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json` and `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Machine-capture manifests are retained in the closeout workspace, not committed to the repository; they are not exact-head hosted proof and do not replace the approved-v1 comparison matrix. |
| Oversized-photo 422 state | `/opt/data/tmp/wdos-stage3/oversized-photo/manifest.json` and `/opt/data/tmp/wdos-stage3/oversized-photo/ONB-02-oversized-photo-422-*.png` | Historical PASS: 10/10 real Playwright captures at prior candidate `4c94e77840e4b05c3016b7c5d81507bdc9f0b9d8`; not exact-head evidence for `3634e16`. |

The post-capture candidate delta is server-side authorization, consent
revision binding, policy-validated operator provisioning, durable reviewer-grant audit provenance,
safe back navigation, locale override precedence, guarded dashboard routing, and accepted-state
first-use presentation. The final implementation includes a small template parity correction
in `templates/onboarding/first_use.html`; the hosted UI-browser run above does **not** exercise
Stage 3 `/onboarding/8/` and therefore does not prove this correction. Other approved onboarding
geometry and locale catalogs remain unchanged, subject to exact-candidate reference comparison.

## Release status

Stage 3 is **not done**. Rex acceptance, independent exact-candidate review, hosted CI/check reconciliation, and the human merge gate remain outstanding. No merge, deployment, production migration, provider configuration, or real email/send was performed. The PR is a review vehicle, not acceptance or release approval.

## Review boundaries

The evidence above establishes the listed local/capture gates only. It does not claim that visual approval is complete for every approved-v1 state, that hosted checks are green, or that product policy decisions outside the implemented contract are resolved. Reviewers must validate the exact pushed PR head and staging diff before acceptance.
