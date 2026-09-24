# Stage 3 progress

## Confirmed onboarding localization blocker — repair active
Parent recovered partial browser harness, ran it, then traced persistent Arabic failure to actual application code: accounts/onboarding.py render_step hardcodes lang=en and direction=ltr. This is not a browser-locale fixture problem. Locale repair delegated to sa-0-23cc5d32 using existing locale/catalog patterns, preserving approved-v1 layout and scope; required real-language text/lang/dir tests, not attribute-only substitution. Existing canonical155 pass predates this forthcoming edit and cannot establish final candidate readiness. Presentation worker changed wizard/CSS only with8 focused tests; pixels still require final recapture. NightWing CI-password suspicion refuted by credential-safe local comparison: URL password matches service password; literal redaction token false. No production credential correction needed. No merge/deployment.

## Full regression verified; UI/CI closure active
Canonical make verify authoritative run exited 0: 155 tests passed, no skips/errors/failures (49.575s). The preceding exit2 was a missing isolated database precondition; the worker provisioned that database before the successful fresh run. Log: /opt/data/tmp/wdos-stage3/resume-regression/canonical-make-verify-authoritative.log. Fresh migrations passed; no pending migrations afterward is not by itself a separate Stage2-to-Stage3 upgrade proof. Initial UI worker's absent-route claim rejected: actual wdos_project/urls.py already includes accounts.onboarding_urls at line7. Superseded copied runtime proc_007444a05c26 stopped. Active bounded workers sa-0-309051c2 (CI stale migration-count correction) and sa-1-c4728b3a (actual-source browser capture/comparison). No Stage3 UI acceptance, release approval, merge or deployment claimed.

## Authorized test-only correction confirmed
Candidate test SHA256: 8a3b55fd6cd805403dc4f783f02311651536318274f1d5442ecedd2b8cf2bb83. Parent PostgreSQL run: 2 tests passed (1.703s). Independent NightWing confirmation: PASS WITH NOTES, 2 tests passed (1.889s), hash matched before/after; report /opt/data/cache/delegation/subagent-summary-0-20260924_123617_708734.txt. Real review POST and invite_person compete in both winner orderings, observed pg_blocking_pids Lock wait, asserted identity/invitation/outbox outcomes. Prior auth/count/cleanup findings resolved. Nonblocking reviewer notes: mixed contender_started event ownership in approval winner can produce scheduling-sensitive false failure; early join assertions could obscure diagnostics. Deferred rather than expanding the bounded correction. No production-code expansion, merge or deployment. This closes only the authorized test correction, not Stage 3 or release readiness. Full regression, UI fidelity and Stage 3 release gates remain outstanding.

## Authorized test-only correction returned; independent review active
Configured-model Drax changed only accounts/test_onboarding_concurrency.py (parent file-hash baseline verified, except parent planning logs). Worker reports both focused tests fail: actual approval returned 403; reverse ordering observed no lock wait. Parent inspected actual test source: fixture/session, absolute row counts, imported TestCase collection and thread-cleanup concerns require adjudication; no product-race conclusion is justified yet. Independent read-only NightWing sa-0-38fcc3d7 dispatched against exact current files to classify failures and return minimum test-only corrections. No production changes, merge or deployment.

## Authorized test-only continuation — transport blocked
Rex authorized one narrowly scoped test-only correction followed by independent review, with no production expansion/merge/deploy. Captured /opt/data/tmp/wdos-stage3/test-only-baseline.json (149 files). Drax dispatch failed before worker start: configured openai-codex provider quota exhausted (429), credentials reported valid. No worker ran and no test-code change or reviewer verdict was produced. Do not retry equivalent transports backed by the same exhausted provider or bypass ownership with parent implementation.

## Final bounded repair adjudication
Parent read actual repair/test source and executed accounts.test_onboarding_concurrency + accounts.test_onboarding_review on isolated PostgreSQL: 12 passed. Post-lock different-person rejection now exists before invitation/outbox writes. However concurrency acceptance remains BLOCKED: approval-first manually assigns Account.person instead of calling review and signals waiting before command entry (no observed database lock wait); invitation-first is sequential, never invokes review, and only checks Invitation.exists(). These tests do not prove the claimed two real winner orderings. Two bounded backend repair runs consumed; no third automatic repair authorized. Preserve candidate and request a narrowly bounded test-proof correction decision.

## Backend repair parent adjudication
First worker returned partial lock edits without concurrency regressions. Parent found approval-first remains unsafe: invite_person discards locked accounts and never rejects an already-linked different Person. Sent one final bounded repair to sa-0-755a686c requiring post-lock revalidation and executable PostgreSQL both-order races. Parent separately verified submission + ResetFragmentBrowserSemanticsTests against explicit isolated PostgreSQL: 15 tests passed, including repaired Playwright ORM setup and consent resubmission. This does not prove identity-race closure.

## Presentation repair parent verification
Drax returned scoped template/CSS changes for checkbox composition, select chevron and Continue icon. Parent inspected actual git diff and git diff --check passed. Parent ran accounts.test_onboarding_ui using explicit isolated PostgreSQL on port 55484 with a separate test database: 8 tests passed. Worker default-port-5432 test failure was an environment-targeting error, not a demonstrated product failure. No changed-candidate screenshot/desktop-mobile visual pass yet; presentation remains needs_review.

## Resume workflow readback
WDOS-20 Done; WDOS-21 and WDOS-3 In Progress. Resume comment 10103 posted to WDOS-21 and exact body read back. Backend delegate sa-0-be831882 owns identity/consent/reset-test repair; presentation delegate sa-0-514a3f9a owns onboarding template/static reference repairs. Parent owns planning and integration verification. Neither worker is allowed commits, external sends, production or Jira writes.

## Resumed at Rex request
Verified branch feat/stage-03-onboarding, HEAD 70bdea7 and preserved dirty UI/photo tree. Read full NightWing report: invitation issuance/review do not share identity serialization; reviewer did not execute Django tests. Previous full PostgreSQL evidence is 152 tests with one reset-browser async-context error, not a full pass. Resuming through a bounded Drax implementation delegate and independent confirmation.
## 2026-09-24
Done: Jira kickoff/readback, isolated lane, reference inventory, Drax smoke and approved direct-Groot fallback; first RED/GREEN entry and durable draft slice.
Executed: isolated manage.py test accounts.test_onboarding.OnboardingEntryTests accounts.test_onboarding.OnboardingDraftTests — 16 passed. New additive migration 0003_onboarding_draft generated.
Now: submission and consent history with fail-closed policy configuration.
Next: first-use and reviewer transitions, runtime regressions, exact visual QA, independent NightWing, PR and CI.
Not done: Stage3 end-to-end implementation/acceptance/release. No PR, merge or deployment claimed.


---
## Preserved Stage 2 history — superseded by Stage 3 record above

# Progress

Fresh fix/stage2-ui-fidelity-otp worktree created from origin/staging. Baseline make verify passed. Root bootstrap preserved existing history. Preflight and all-stage visual acceptance rule recorded.

## Final remediation handoff
- All S2-01..20 have implementation and regression mappings in docs/stage-02-fidelity-remediation.md.
- Parent verification: 100 tests (5 PostgreSQL-only skips); 77/77 browser/reference scenarios; source stability passed.
- Exact reference CSS cascade and previously omitted 24px spacer restored after independent rendered comparison; supplemental states reviewed separately from default reference samples.
- Browser-discovered missing enrolled MFA challenge fixed and replay tested.
- Dedicated staging OTP configuration corrected with explicit authorization; one app-triggered OTP provider-delivered. No UI feature deploy or merge.
- Published PR identity and exact-head CI/review evidence recorded in GitHub; stage acceptance remains Rex-gated.