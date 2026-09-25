# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `fix/stage3-auth-navigation`
- Target: `staging`
- Exact implementation candidate: PR 5 head `ae773aaf1847fc1e442b4dbab7119b40cb16dfaa` (`fix: close authenticated navigation review findings`). The final PR head after this evidence-only update must be read back from GitHub and is authoritative for final handoff.
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `make verify` with `DATABASE_URL` and provider credentials unset | PASS: 201 tests, 15 expected PostgreSQL/Playwright environment-gated skips, exit 0; system check, migration check, migration and collectstatic passed. |
| Same-family photo-attempt regression | `accounts.test_onboarding.OnboardingDraftTests` | PASS: rejected photo attempts 1–10 reach the decoder, attempt 11 returns 429 before another decode, and the 429 response preserves safe text fields with localized recovery copy. |
| Hosted exact-head CI | PR 5 live checks | The pre-fix head was green; the pushed `ae773aa` head requires fresh hosted checks before closeout. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Historical manifests identify capture source tree `e1be979c...ffb1`; they are retained as prior evidence and are not exact-head proof. |
| Exact-code browser capture | `/opt/data/tmp/wdos-stage3/current-head-ae773aa/` | Fresh Chromium captures from exact implementation head `ae773aaf1847fc1e442b4dbab7119b40cb16dfaa`: authenticated onboarding desktop (`1440×1000`), onboarding mobile (`390×844`), and Arabic status mobile (`390×844`). SHA-256: `2876cc2e75e03b5367c91a4ddf406e56bda741c82c32c0df65bddc1281628920`, `b841514af7ea7fc0100e6b46bf253411b781079173c1da77586f9ccea85cfd18`, `a0d6d3f2cc157c02da1ebf87c933004294115bddf8cac0365bdf3fc08d58d96a`. |
| Exact interaction evidence | `/opt/data/tmp/wdos-stage3/current-head-ae773aa/` | Chromium asserted desktop profile-menu open, mobile profile-menu open with POST logout form, and Arabic status explainer `aria-label="لماذا أرى هذه الحالة؟"`. |
| Reference comparison matrix | `docs/ui-acceptance.md`; approved-v1 Stage 2 package under `docs/approved-ui/stage-02/` | Capture identity and exercised states are recorded above. No unapproved deviation is claimed; matched-viewport side-by-side visual disposition and Rex's versioned acceptance remain owner gates. |
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

Stage 3 is **not done**. Rex acceptance, fresh exact-head hosted checks/review reconciliation, matched-reference visual disposition, and the human merge gate remain outstanding. No merge, deployment, production migration, provider configuration, or real email/send was performed. The PR is a review vehicle, not acceptance or release approval.

## Review boundaries

The evidence above establishes the listed local/capture gates only. It does not claim that visual approval is complete for every approved-v1 state, that hosted checks are green, or that product policy decisions outside the implemented contract are resolved. Reviewers must validate the exact pushed PR head and staging diff before acceptance.
