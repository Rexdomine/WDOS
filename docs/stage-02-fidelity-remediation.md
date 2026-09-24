# Stage 2 authentication UI fidelity remediation

## Authority and boundary

- Canonical visual reference: approved WDOS UI v1, `AUTH-01` through `AUTH-09`, desktop/mobile/state files under `/opt/data/projects/WDOS/design-review/v1/`.
- Frozen v1 master SHA-256: `a1a3de8851acf5d76b6552cbae21279d808182e84d9793e702772275e396549b`.
- Approved amendments used here: five-language selector, password reveal control, and the supplied WODDI logo. Candidate v2 is not treated as approved replacement authority.
- Audit authority: `/opt/data/projects/WDOS/.hermes/stage2-ui-audit/findings.json`.
- Canonical screen count remains nine. `/auth/help/`, `/auth/privacy/`, and `/auth/terms/` are supplemental named routes (`HELP`, `PRIVACY`, `TERMS`), not synthetic `AUTH-10..12` screens.
- Working tree base: `0c9b3bb5a52d14d9b2b5b9aae9580a0387e6821a`. Drax was prohibited from committing, so the final candidate commit SHA and screenshot identity must be added by Groot/NightWing after this work is committed.

## Finding-to-code-and-test matrix

| Audit ID | Remediation | Code | Regression evidence | Implementation status |
|---|---|---|---|---|
| S2-01 | Restored separate WGMN/WNNN rows, hierarchy, spacing, and approved refinement rules. | `templates/accounts/auth.html`; `accounts/static/accounts/refinements.css` | `AuthUiFidelityTests.test_shared_shell_contains_reference_structure`; `test_reference_refinements_are_not_overridden_by_review_leftovers` | Fixed in code/tests. |
| S2-02 | Shared five-language selector now renders on every auth and supplemental screen with RTL retained. | `templates/accounts/auth.html`; `accounts/locales.json` | `AuthUIStateRegressionTests.test_all_public_screens_have_language_privacy_terms_help_and_cream_notice`; locale suite | Fixed in code/tests. |
| S2-03 | Removed review/configuration metadata; restored translated Privacy notice, Terms, Get help, and the approved product-label footer without invented copyright copy. | `templates/accounts/auth.html`; `accounts/locales.json`; `accounts/views.py` | shared-shell and all-public-screen regressions | Fixed in code/tests. |
| S2-04 | Added actionable safe help and official `https://thewoddi.org/contact.html` destination without invented review promises. | `accounts/views.py`; `templates/accounts/auth.html`; `accounts/urls.py` | `test_public_help_and_policy_routes_are_supplemental_not_canonical_ids`; `test_help_is_actionable_and_explicitly_has_no_secret_or_bypass_path` | Fixed in code/tests. |
| S2-05 | Restored the full-width cream shield notice on AUTH-01..09 with screen-appropriate translated copy. | `templates/accounts/auth.html`; `accounts/static/accounts/live.css`; `accounts/locales.json` | `test_all_public_screens_have_language_privacy_terms_help_and_cream_notice` | Fixed in code/tests. |
| S2-06 | Reused canonical `design.css` and exact canonical `refinements.css`; removed destructive shell overrides; restored field size, label suffix, spacing, and mobile geometry. | `accounts/static/accounts/refinements.css`; `accounts/static/accounts/live.css`; `accounts/views.py`; `templates/accounts/auth.html` | canonical refinement byte comparison and form-structure tests | Fixed in code/tests; screenshot acceptance remains with parent review. |
| S2-07 | Every primary action has the approved leading SVG arrow, with RTL direction handling. | `templates/accounts/arrow.html`; `templates/accounts/auth.html`; `accounts/static/accounts/live.css` | `AuthUiFidelityTests.test_every_primary_control_has_a_leading_arrow_icon` | Fixed in code/tests. |
| S2-08 | Restored compact Keep me signed in / Forgot password row and exact checkbox label. | `accounts/forms.py`; `templates/accounts/auth.html`; `accounts/static/accounts/live.css` | `test_login_remember_and_verification_forms_have_exact_fields` | Fixed in code/tests. |
| S2-09 | Removed generic/self navigation; restored explicit welcome, login, registration, recovery, invitation, reset, and MFA exits. | `templates/accounts/auth.html`; `accounts/urls.py` | explicit-navigation and welcome/registration regressions | Fixed in code/tests. |
| S2-10 | Verification now accepts only the code for a server-validated pending account and displays a safely masked bound destination. | `accounts/forms.py`; `accounts/views.py`; `templates/accounts/auth.html` | `test_verification_is_bound_masked_and_has_real_resend_cooldown`; `test_unbound_verification_has_no_identity_form_or_resend` | Fixed in code/tests. |
| S2-11 | Resend is POST/CSRF-only, bound to the pending session, disabled for 60 seconds from the actual latest issuance timestamp, and still enforced by backend throttles. | `accounts/views.py`; `accounts/urls.py`; `templates/accounts/auth.html`; `accounts/static/accounts/auth.js` | bound resend/cooldown regression | Fixed in code/tests. |
| S2-12 | Verification, invitation, recovery request, and reset success variants remove stale forms and provide one truthful next action. | `accounts/views.py`; `templates/accounts/auth.html` | `test_success_states_remove_stale_forms_and_offer_truthful_next_action`; `test_already_linked_invitation_has_no_claim_form`; existing flow tests | Fixed in code/tests. |
| S2-13 | Invitation code is first and contact label is exactly “Email on invitation.” | `accounts/forms.py` | `test_invitation_field_order_and_contact_label_match_reference` | Fixed in code/tests. |
| S2-14 | Reset form is hidden by default, revealed only after fragment capture, and missing-proof state is localized without a hidden-field error. Proofs do not appear in response markup. | `accounts/forms.py`; `accounts/views.py`; `templates/accounts/auth.html`; `accounts/static/accounts/auth.js` | direct-reset locale regression; `ResetFragmentBrowserSemanticsTests` | Fixed in code/tests. |
| S2-15 | Missing, malformed, invalid, expired, and used proofs render the approved unusable-link state, hide the password form, and link directly to recovery. | `accounts/views.py`; `templates/accounts/auth.html` | malformed/invalid/used proof regression; retry proof non-echo regression | Fixed in code/tests. |
| S2-16 | MFA setup initially presents only Begin MFA setup; code verification appears only after setup begins. | `accounts/views.py`; `templates/accounts/auth.html` | `test_mfa_setup_then_enrollment_order_and_lost_factor_support`; existing privileged MFA flow | Fixed in code/tests. |
| S2-17 | Authenticator instructions and private setup key render above the code field with wording matching the visual order. | `templates/accounts/auth.html`; `accounts/locales.json` | MFA order assertion | Fixed in code/tests. No setup secret is recorded in remediation evidence. |
| S2-18 | MFA challenge supplies a real account-help/support action, explicitly preserves ownership/MFA checks, and offers no bypass or fake review submission. | `accounts/views.py`; `templates/accounts/auth.html`; `accounts/locales.json` | MFA lost-factor and help safety regressions | Fixed in code/tests. |
| S2-19 | Password-confirmed pending login binds the account id/security version and status presents a direct Verify contact action. | `accounts/views.py`; `templates/accounts/auth.html` | `test_pending_password_login_restores_verify_action_and_bound_destination`; existing pending-login flow | Fixed in code/tests. |
| S2-20 | Pending/restricted/expired/MFA/signed-out status variants use a distinct status card and prominent context action without exposing unauthenticated record data. | `accounts/views.py`; `templates/accounts/auth.html`; `accounts/static/accounts/live.css` | `test_restricted_and_expired_statuses_are_prominent_and_private`; pending-state regression | Fixed in code/tests. |

## Cross-cutting security and localization evidence

- State-changing actions remain POST + CSRF protected. Verification and resend trust only a server-bound pending account id/security version.
- Anonymous locale/public GET requests do not intentionally create database sessions; the existing session regression remains in the full suite.
- Reset proofs remain fragment-to-POST, one-use, expiry/version bound through the existing service. A temporary retry proof is encrypted before server-side session storage and is never rendered back.
- MFA and recovery-code one-use/version checks remain in the existing service and flow tests. Lost-factor help does not restore access.
- All new UI keys exist in English, French, Portuguese, Arabic, and Swahili; dynamic names, destinations, and other user content are not translated.
- Local tests use local/throwaway databases and do not dispatch provider mail.

## Outstanding acceptance evidence

Implementation and regression mappings cover S2-01..20. Parent browser/reference comparison and the subsequent corrections are recorded in `stage-02-remediation-verification.md`. The published PR supplies the authoritative candidate SHA and hosted CI evidence. Final stage acceptance remains with Rex; this mapping does not grant merge or deployment permission.
