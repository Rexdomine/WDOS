# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `fix/stage3-auth-navigation`
- Target: `staging`
- Exact implementation candidate at capture time: PR 5 head `8c8698b17effde91db78d5c797b44f156d627b66` (`fix: mark localized foundation control language`). The exact-head interaction capture manifest is recorded below.
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `make verify` with `DATABASE_URL` and provider credentials unset | PASS: 201 tests, 15 expected PostgreSQL/Playwright environment-gated skips, exit 0; system check, migration check, migration and collectstatic passed. |
| Same-family photo-attempt regression | `accounts.test_onboarding.OnboardingDraftTests` | PASS: rejected photo attempts 1–10 reach the decoder, attempt 11 returns 429 before another decode, and the 429 response preserves safe text fields with localized recovery copy. |
| Hosted exact-head CI | PR 5 live checks | Pending on exact head `8c8698b17effde91db78d5c797b44f156d627b66`: `django`, `GitGuardian Security Checks`, and `CodeRabbit` successful; `ui-browser` in progress at capture time. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/runtime.json` and `manifest.json` | Capture run `1790322779649435136`, Chromium 1187, source hash `8f4cada01cb4b7b5f1eb030f464dc2880ea9c7640deefe465715ffd80363f6c5`; this is the checked-out PR head recorded above, not the Stage 2 AUTH harness. |
| Exact-code browser capture | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json` | Dedicated onboarding harness completed 82 real Chromium captures: ONB-01..08 at desktop/mobile in English, Arabic, French, Portuguese, and Kiswahili, plus ONB-02 validation and draft-reload states. Representative exact-candidate hashes: ONB-01 desktop `dd79c20e4b50e32d612367df57cf24777d190dd488cee5d579e1e887414e9708`, ONB-01 mobile `8cc2045b357d58547d629551fb5f24380602f364e29aee1b7e6e9b9f49b83cd7`, ONB-02 desktop `1d27908f7b1f728abe4f70ad9f5f9b4e30be66ea561d98cef945342c97a92fa3`, ONB-02 mobile `ccb6318665747a6eaf994379f5136919fb7fa78007493963d51c5df30960f6a8`, ONB-08 desktop `c779748b05adebdda49306aba754ed80516541d17a0226f9e7616ef631858e88`, and ONB-08 mobile `900e13f09c1304721f3039bc5742b198417ec4a60121a84990895bf3f79d0732`. |
| Exact interaction evidence | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/state-coverage-review.md` | PASS for real route entry, locale/direction binding, ONB-02 validation, draft reload, and reviewer permission boundary. The state review explicitly lists uncovered approved variants; they are not silently claimed as passed. |
| Reference comparison matrix | Approved-v1 identity `WDOS Complete UI Review v1`; canonical source `/opt/data/projects/WDOS/design-review/v1/ONB-01..08-*.html` and rendered references `/opt/data/tmp/wdos-stage3/refs/ONB-01-{desktop,mobile}.png`, `/opt/data/tmp/wdos-stage3/refs/ONB-02-{desktop,mobile}.png` | The actual onboarding candidate/reference artifacts are listed here, not `.hermes/stage2-fidelity-qa/`. Representative reference hashes: ONB-01 desktop `13d9e5f8cfad1e98f7d585d4cfce852eea2a1aa7a7202438d423509c1832f7e1`, ONB-01 mobile `e436a29c943c8f25f85a0a963b16ef608518929cd9544c7784745fbd7047a3f2`, ONB-02 desktop `597b54776e0bf75a5249355a38acff60f9926f42c1f56cb87bac4fc214c52459`, and ONB-02 mobile `4ee075b1fb7f1b98d67a6d3d789f7695c4840762256f1af88604757500a5c0c3`. Rex's versioned visual acceptance remains an owner gate. |
| Arabic/localization repair | `arabic-final-verify.log`; `accounts/test_locale.py` | PASS on the candidate. The catalog fragment `تفضيلات الحركة` was repaired and exercised. |
| Recovery/lost-response review | `/opt/data/tmp/wdos-stage3/postcommit-independent-closeout.md` | PASS: 7 focused tests. |
| Visual recovery review | `/opt/data/tmp/wdos-stage3/recovery-final-acceptance.md` | Parent fresh-vision review reports no remaining Arabic fragment or clipping blocker. |
| Browser capture inventory | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json` and `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Machine-capture manifests are retained in the closeout workspace, not committed to the repository; they are not exact-head hosted proof and do not replace the approved-v1 comparison matrix. |
| Exact-head changed interaction states | `/opt/data/tmp/wdos-stage3/exact-head-8c8698b/manifest.json` | PASS: 7 real Chromium captures at desktop/mobile for the foundation shell, opened onboarding profile menu (English desktop/mobile and Arabic mobile), and opened status explainer (English and Arabic mobile); all asserted no horizontal overflow. |
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
