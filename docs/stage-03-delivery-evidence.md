# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `feat/stage-03-onboarding`
- Target: `staging`
- Exact product candidate identity before this evidence-only update: PR 4 head `d6865e6841b111142fa9ce5cef49bbfa45d02ac0` (`fix: make accepted first-use links read-only`). The live PR head after this documentation update, hosted checks, and review verdict must be read back from GitHub and are authoritative for final handoff.
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `make verify` with `DATABASE_URL` and provider credentials unset | PASS: 201 tests, 15 expected PostgreSQL/Playwright environment-gated skips, exit 0; system check, migration check, migration and collectstatic passed. |
| Same-family photo-attempt regression | `accounts.test_onboarding.OnboardingDraftTests` | PASS: rejected photo attempts 1–10 reach the decoder, attempt 11 returns 429 before another decode, and the 429 response preserves safe text fields with localized recovery copy. |
| Hosted exact-head CI | See the exact-head closeout ledger and live PR 4 checks | PASS/FAIL must be read back against the current PR head; the hosted `ui-browser` job runs Stage 2 only and is not Stage 3 browser/reference evidence. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Historical manifests identify capture source tree `e1be979c...ffb1`; they are retained as prior evidence and are not exact-head proof. |
| Exact-code browser capture | `/opt/data/tmp/wdos-stage3/current-head-visual/manifest.json` and its 18 PNGs | Fresh Chromium captures from exact implementation head `d6865e6841b111142fa9ce5cef49bbfa45d02ac0`: ONB-01..08 at desktop/mobile, plus Arabic ONB-01 desktop/mobile; route HTTP status, `lang`, and `dir` are recorded. The capture source is the implementation head immediately before this documentation-only update. |
| Arabic/localization repair | `arabic-final-verify.log`; `accounts/test_locale.py` | PASS on the candidate. The catalog fragment `تفضيلات الحركة` was repaired and exercised. |
| Recovery/lost-response review | `/opt/data/tmp/wdos-stage3/postcommit-independent-closeout.md` | PASS: 7 focused tests. |
| Visual recovery review | `/opt/data/tmp/wdos-stage3/recovery-final-acceptance.md` | Parent fresh-vision review reports no remaining Arabic fragment or clipping blocker. |
| Browser capture inventory | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json` and `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Machine-capture manifests are retained in the closeout workspace, not committed to the repository; they are not exact-head hosted proof and do not replace the approved-v1 comparison matrix. |
| Oversized-photo 422 state | `/opt/data/tmp/wdos-stage3/oversized-photo/manifest.json` and `/opt/data/tmp/wdos-stage3/oversized-photo/ONB-02-oversized-photo-422-*.png` | Historical PASS: 10/10 real Playwright captures at prior candidate `4c94e77840e4b05c3016b7c5d81507bdc9f0b9d8`; not exact-head evidence for `28990f6`. |

The post-capture candidate delta is server-side authorization, consent
revision binding, policy-validated operator provisioning, durable reviewer-grant audit provenance,
safe back navigation, locale override precedence, guarded dashboard routing, and accepted-state
first-use presentation. The exact-code browser run above now exercises the accepted-state
first-use template correction at its source head. A fresh side-by-side comparison against the
approved-v1 reference package is still a Rex acceptance obligation; this record does not claim
that visual acceptance or Rex acceptance is complete.

## Release status

Stage 3 is **not done**. Rex acceptance, independent exact-candidate review, hosted CI/check reconciliation, and the human merge gate remain outstanding. No merge, deployment, production migration, provider configuration, or real email/send was performed. The PR is a review vehicle, not acceptance or release approval.

## Review boundaries

The evidence above establishes the listed local/capture gates only. It does not claim that visual approval is complete for every approved-v1 state, that hosted checks are green, or that product policy decisions outside the implemented contract are resolved. Reviewers must validate the exact pushed PR head and staging diff before acceptance.
