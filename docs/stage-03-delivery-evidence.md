# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `fix/stage3-auth-navigation`
- Target: `staging`
- Exact implementation candidate: PR 5 head `d760c1c8b04a2f6997fb991c3394feeb7cf335fe` (`fix: localize foundation logout shell`). This head was read back from GitHub before capture and is authoritative for this evidence package.
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `make verify` with `DATABASE_URL` and provider credentials unset | PASS: 201 tests, 15 expected PostgreSQL/Playwright environment-gated skips, exit 0; system check, migration check, migration and collectstatic passed. |
| Same-family photo-attempt regression | `accounts.test_onboarding.OnboardingDraftTests` | PASS: rejected photo attempts 1–10 reach the decoder, attempt 11 returns 429 before another decode, and the 429 response preserves safe text fields with localized recovery copy. |
| Hosted exact-head CI | PR 5 live checks | PASS on exact head `d760c1c8b04a2f6997fb991c3394feeb7cf335fe`: `ui-browser`, `django`, `GitGuardian Security Checks`, and `CodeRabbit` all successful. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Historical manifests identify capture source tree `e1be979c...ffb1`; they are retained as prior evidence and are not exact-head proof. |
| Exact-code browser capture | `/opt/data/tmp/wdos-stage3/current-head-d760c1c8/` | Fresh Chromium accepted-workspace captures from exact head `d760c1c8b04a2f6997fb991c3394feeb7cf335fe`: foundation shell desktop `1440×1000`, mobile `390×844`, French mobile `390×844`, and Arabic RTL mobile `390×844`. SHA-256: desktop `0f2f8222dedca53fcb625c28d0b0f7fa77b2ed9be0e5d17800d6e719abc2e65c`, mobile `a7d9869a525e80a3aae1e2035887b74f1f2316a423369b923063ddd3132084f3`, French `c9238a9f2970818dbe948d006c9aa0a1b49c332d37237c65f837ba3f61de5171`, Arabic `297cf95f91fe6cfb09ca4bf75255e9e7e6cf607c4da492b1c6378cd9a91328b5`. |
| Exact interaction evidence | `/opt/data/tmp/wdos-stage3/current-head-d760c1c8/manifest.json` and `.hermes/stage2-fidelity-qa/report.json` | PASS: canonical 77-scenario Chromium audit; accepted foundation shell asserts one CSRF-protected POST `/auth/logout/` form at desktop/mobile, no horizontal overflow, persisted French `ltr`, and Arabic `rtl`. |
| Reference comparison matrix | `docs/ui-acceptance.md`; approved-v1 identity `WDOS Complete UI Review v1`; screen IDs `CORE-01`, `CORE-06-SIGNOUT`, and `ONB-01..ONB-08` | Matched candidate/reference pairs are the foundation desktop/mobile captures above plus the canonical onboarding/reference capture set in `.hermes/stage2-fidelity-qa/`. No unapproved deviation is claimed; Rex's versioned visual acceptance remains an owner gate. |
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
