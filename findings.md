# Stage 3 findings

## Canonical gate and locale evidence (resume)
- ui-browser exists as a job inside .github/workflows/ci.yml; a separate ui-browser.yml is not required. Current browser job covers Stage 2 only.
- Canonical PostgreSQL gate is make verify; container smoke currently hardcodes migration_rows == 21, which must be reconciled with additive Stage 3 migrations rather than discovered after push.
- accounts/onboarding.py render_step currently hardcodes en/ltr: Stage 3 localization/RTL remains a real implementation gap, not merely missing screenshots.
- Local QA /auth/login/ returned HTTP 200 on port 18089 on resume.

## Resume evidence
NightWing report /opt/data/cache/delegation/subagent-summary-0-20260924_113820_791999.txt identifies onboarding_review.py account lock versus invite_person.py person lock: concurrent invitation issuance can strand identity. Minimum proof is real PostgreSQL two-connection race in both winning orders. Earlier gap-audit base-only snapshot is stale. Approved-reference visual deviations and policy-input blockers remain unresolved.
- WDOS-21 / WDOS-3 verified In Progress; kickoff comment 10102. Stage2 WDOS-20 verified Done.
- Base staging bc9d346d800aa1b1bb244026d3448992ca288869; isolated branch feat/stage-03-onboarding.
- Drax CLI sandbox denied namespace creation. Rex explicitly authorized direct Groot implementation; no sandbox/kernel policy changed.
- Approved v1 ONB01..08 include exact desktop/mobile and component-state references; synthetic names, network, age threshold and geography are not policy.
- Stage3 policy register lacks approved eligibility, consent text, geographic catalogue, duplicate-resolution policy and actor authority mapping. No production default may fill those in.
- Existing Person, Account, Invitation, AccessGrant and account middleware are reused. OnboardingDraft is one-to-one with Account, not a second identity.
- RED: first onboarding URLs returned 404. GREEN: protected first screen works. RED: writes returned 405 / every page showed ONB01. GREEN: 16 entry/draft tests pass using isolated SQLite.
- Generic DATABASE_URL in terminal environment targeted unavailable loopback Postgres; all subsequent test commands explicitly isolate DATABASE_URL and provider credentials. No external emails sent.
- Remaining work includes full submission/consent, photo persistence, accepted/review transitions, exact UI/mobile/RTL/locales, real Postgres concurrency, independent review and PR. No complete UI claim.


---
## Preserved Stage 2 history — superseded by Stage 3 record above

# Findings

20 audited issues govern this remediation; actual approved reference source must be reused, not reinterpreted. Root context had stale PR1/credential-blocker records; live source base is merged PR2. OTP root cause not yet verified.

## Verified public support destination
Read-only GET/extraction of https://thewoddi.org/contact.html succeeded; official WODDI Contact Us page includes HQ contact/form. It can be offered as a general WODDI contact route, not a promised WDOS-specific SLA or automatic account review. Never include OTPs/passwords/recovery codes in contact URL query or prefilled message. No approved legal policy text located; Privacy/Terms must not invent promises.

## Known source-specific state requirements
Reset proof arrives in URL fragment (not available on server GET): missing-proof client state must be honest; preserve fragment-to-hidden-POST + history removal, handle server POST invalid proof explicitly. Verification requires pending_registration_account id+security_version; a valid password login to pending can establish that same bound context safely. Do not loosen verify ownership merely to prefill email. Resend feedback uses real server timestamps/cooldown but must not reveal account existence. MFA starts via POST begin=1; empty code must not block setup; initial/enrollment/challenge states distinct.

## Final remediation handoff
- All S2-01..20 have implementation and regression mappings in docs/stage-02-fidelity-remediation.md.
- Parent verification: 100 tests (5 PostgreSQL-only skips); 77/77 browser/reference scenarios; source stability passed.
- Exact reference CSS cascade and previously omitted 24px spacer restored after independent rendered comparison; supplemental states reviewed separately from default reference samples.
- Browser-discovered missing enrolled MFA challenge fixed and replay tested.
- Dedicated staging OTP configuration corrected with explicit authorization; one app-triggered OTP provider-delivered. No UI feature deploy or merge.
- Published PR identity and exact-head CI/review evidence recorded in GitHub; stage acceptance remains Rex-gated.