# WDOS Stage 3 delivery evidence

## Candidate

- Branch: `feat/stage-03-onboarding`
- Target: `staging`
- Exact verified implementation head: `d63023091340fdd3a6b27a30e9572b0c68b74600`; hosted exact-head CI run: `36042906233` (Django and UI-browser passed). This evidence record is documentation-only after that implementation head; the final PR head is always read back from GitHub.
- This record is evidence packaging only; it does not grant acceptance, merge, deployment, provider changes, real sends, or Jira completion.

## Verification map

| Gate | Evidence | Result / limit |
|---|---|---|
| Canonical regression | `/opt/data/tmp/wdos-stage3/arabic-final-verify.log` | PASS: 169 tests, 73.348s, canonical exit 0. |
| Refreshed source integrity | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json`, `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Both manifests identify the capture source tree as `e1be979c...ffb1`; this is pre-packaging evidence. The implementation delta after capture is limited to server-side review/consent/route hardening, operator audit provenance, locale precedence, request-body upload protection via the first-position limiting upload handler, and focused regressions; the accepted-state template correction is covered by hosted UI-browser evidence. |
| Arabic/localization repair | `arabic-final-verify.log`; `accounts/test_locale.py` | PASS on the candidate. The catalog fragment `تفضيلات الحركة` was repaired and exercised. |
| Recovery/lost-response review | `/opt/data/tmp/wdos-stage3/postcommit-independent-closeout.md` | PASS: 7 focused tests. |
| Visual recovery review | `/opt/data/tmp/wdos-stage3/recovery-final-acceptance.md` | Parent fresh-vision review reports no remaining Arabic fragment or clipping blocker. |
| Browser capture inventory | `/opt/data/tmp/wdos-stage3/verified-ui/manifest.json` and `/opt/data/tmp/wdos-stage3/recovery-visual/machine-capture-manifest.json` | Machine-capture manifests are retained in the closeout workspace, not committed to the repository; the older `visual-correction-parent-verification.md` hash is superseded and is not used as candidate evidence. |

The post-capture candidate delta is server-side authorization, consent
revision binding, policy-validated operator provisioning, durable reviewer-grant audit provenance,
safe back navigation, locale override precedence, guarded dashboard routing, and accepted-state
first-use presentation. The final implementation includes a small template parity correction
in `templates/onboarding/first_use.html`; its accepted-state pill is covered by the hosted
UI-browser run above. Other approved onboarding geometry and locale catalogs remain unchanged.

## Release status

Stage 3 is **not done**. Rex acceptance, independent exact-candidate review, hosted CI/check reconciliation, and the human merge gate remain outstanding. No merge, deployment, production migration, provider configuration, or real email/send was performed. The PR is a review vehicle, not acceptance or release approval.

## Review boundaries

The evidence above establishes the listed local/capture gates only. It does not claim that visual approval is complete for every approved-v1 state, that hosted checks are green, or that product policy decisions outside the implemented contract are resolved. Reviewers must validate the exact pushed PR head and staging diff before acceptance.
