# Stage 2 remediation verification

## Reproducible gates
- `make verify`: 100 tests executed, 5 PostgreSQL-only tests skipped locally; suite passed. System checks, migration parity and static collection passed.
- `scripts/stage2_browser_qa.py`: 77/77 browser/reference scenarios passed with a stable source digest. This includes reference captures, not 77 distinct end-to-end journeys.
- Desktop 1440 and mobile 390; all nine public routes checked in each of English, French, Portuguese, Arabic/RTL and Kiswahili.
- Synthetic local journeys: pending account→bound verification, invitation→linked status, missing/invalid/valid/replayed reset proof, suspended access, MFA enrollment→challenge→recovery code, recovery-code replay rejection and expired session.
- Password controls: hidden default, independent fields, keyboard activation and focus returned to the edited input. Localized submitting feedback was checked with a real submit event while test-only navigation prevention kept the transient state observable; this is not provider-latency evidence.
- Auth provider sends were disabled throughout local browser QA. Temporary SQLite, generated credentials and MFA values were cleaned up; screenshot masks hide sensitive fields/codes.

## Visual comparison
Frozen AUTH-01..09 desktop/mobile/state references are versioned under `docs/approved-ui/stage-02/`. The source integrity gate verified all 27 references and 37 total files; a deliberately mutated temporary copy was rejected.

The independent comparison caught and corrected stylesheet cascade regressions, missing approved 24px inter-section spacing, notice width, extra help/copyright copy, mobile control sizing and footer layout. On the final measured welcome, registration and recovery pages, title/lede/primary action/notice/footer positions exactly match the reference in both viewports. Sign-in differs by at most 0.41 CSS pixels in measured vertical positions due to the functional checkbox row. Password-eye and five-language selector behavior are approved amendments. Example personal data is deliberately not prefilled.

State-specific comparisons distinguish the authenticated/bound state from anonymous reference samples. Verification includes required masked destination and real issuance/resend state; MFA enrollment and enrolled challenge are distinct; expired sessions expose sign-in rather than restricted record details. Pink screenshot blocks are deliberate redaction masks, not rendered input colors. The final code restores reference secondary-link labels while retaining functioning contextual destinations.

## Review findings resolved
A completed source review did not identify the enrolled-MFA GET form omission; independent browser testing did. The challenge form and a direct GET regression assertion were added, then the browser flow passed, including single-use recovery. Source review alone is not acceptance proof.

## Remaining release/acceptance gates
Hosted PostgreSQL/container/browser CI and exact-head external code/security review must be checked on the published PR. Native-speaker linguistic review remains recommended. Privacy/Terms routes refer honestly to the official WODDI contact instead of inventing legal policies. Rex alone accepts the stage and owns merge/deployment approval. No UI-feature revision was deployed as part of this remediation.

See `stage-02-otp-incident.md` for the separately authorized and provider-verified staging email fix.
