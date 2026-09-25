# WDOS Stage 3 — member onboarding and first-use activation

## Authority
Rex authorized Stage 3 end-to-end using Jira on 2026-09-24. Jira execution WDOS-21, parent Epic WDOS-3; both read back In Progress. Stage 2 WDOS-20 read back Done. Approved v1 ONB-01..ONB-08 governs UI; v2 is not accepted. No auto-merge, deployment, production migration, real sends, policy invention or Stage 4.

## Workspace
- Branch: feat/stage-03-onboarding
- Worktree: /opt/data/projects/wdos-stage3
- Base: origin/staging bc9d346d800aa1b1bb244026d3448992ca288869 (merged Stage 2)
- Governance: /opt/data/projects/WDOS/development-baseline/ and PROJECT_CONTEXT.md
- Jira: WDOS-21 (execution), WDOS-3 (Epic).

## Skills and gates
HEAVY stateful full-stack slice. Skills loaded: payments-and-stateful-integrations-preflight, groot-software-orchestration, drax-ai-automation-engineer, nightwing-qa-review, rex-planning-with-files, jira-project-content-operations, codex.
Drax is implementation lane; independent NightWing is review lane; Groot owns scope/Jira/review reconciliation. Verify CLI before launch. No silent fallback or sandbox bypass if unavailable. Codex gpt-6-astra sandbox smoke failed with namespace denial. Rex explicitly selected direct Groot implementation for Stage 3 via clarification; independent NightWing remains required. No sandbox/kernel policy changed.

## Bounded scope
ONB-01..08: member/candidate/community first-use profile, explicit WGMN/WNNN selection/evidence, geography/local-home assignment, versioned consent choices/history, draft/resume, review/submit, duplicate/conflict and pending review, permitted first-use home. Preserve one permanent Person and separate role/membership identity. Reuse Stage 2 invitation/auth security without broad refactors. Unapproved policies stay pending and must not activate access.

## Phases
1. [complete] Restore Jira task/Epic, governing scope and approved references; record boundary/state invariants and unresolved policy decisions.
2. [in_progress] Repair and complete bounded UI/API/persistence/permissions with additive migrations and focused failure-first tests through Drax.
3. [pending] Execute fresh/upgrade migration and concurrency tests, full regression, real browser desktop/mobile/RTL and supported-locale UI comparisons. Record every drift.
4. [pending] Independent NightWing review; remediate verified in-scope findings only; focused PR to staging; serialize exact-head Codex/security reviews; all CI green.
5. [pending] Jira evidence and Rex review handoff. No Done until actual acceptance and release gates. No merge by automation.

## Next step
Rex explicitly resumed full Stage 3 delivery, requiring active workers and no internal-checkpoint stalls. Test-only concurrency correction is confirmed: parent and independent NightWing PostgreSQL runs each passed 2 tests; bounded verdict PASS WITH NOTES. Current gates: full canonical regression and actual approved-v1 browser comparison in parallel, then consolidate evidenced repairs, exact-candidate verification, independent NightWing, PR to staging, hosted CI/review reconciliation, Rex acceptance handoff. Configured model only. No auto-merge/deployment/real sends or policy invention. Earlier quota blocker is resolved.

## Resume checkpoint
HEAVY continuation. HEAD 70bdea7 plus uncommitted UI/photo work. Backend checkpoint has an independent NightWing blocking race finding. Full PostgreSQL run: 152 tests, one SynchronousOnlyOperation in reset-browser setup. Remaining ordered gates: bounded backend repair → approved-v1 UI/localization/browser parity → canonical tests/migration proof → independent exact-candidate review → PR to staging/hosted checks and review reconciliation → Rex acceptance/merge → Jira completion readback. No auto-merge/deploy or invented production policy.

## Stateful boundary preflight (initial, to be refined from sources)
Client supplies draft fields and expected revision; authenticated account/person and authorization remain server-owned. DB is durable authority. Services own atomic save/submit/consent history and per-person identity. Browser response loss after commit must be recoverable by reload without duplicate submissions/history. No new provider calls or queues planned; Stage 2 invitation/email worker remains separate. Additive migration must preserve current accounts/grants and historical consent.
Contract state progression: draft -> checked -> submitted -> accepted / review needed -> first use. Explicit eligibility/country/local-home policy is required for acceptance; missing policy cannot grant roles or guess a chapter. No state transitions or policy values inferred from demo text.
Required failure proof: concurrent tab/revision conflict; duplicate submit/replay; forbidden cross-person edits; forged role/network/geography; suspended/revoked session; incomplete draft; missing/changed consent version; unavailable chapter; invitation expiry/replay; crash around DB commit; upgrade/fresh parity. Preview samples are never production fixtures.

## Completion evidence
Backend checkpoint 70bdea7 implemented and independently reviewed with a blocking identity race. Earlier focused tests passed; full PostgreSQL regression failed one reset-browser setup test. UI/photo changes remain uncommitted and unaccepted. Two bounded, nonoverlapping backend/presentation workers dispatched on resume. Jira resume evidence posted/read back. No Stage 3 PR/merge/deployment or completion claimed.


---
## Preserved Stage 2 history — superseded by Stage 3 record above

# Fix Stage 2 UI fidelity and OTP delivery

## Goal
Repair all S2-01..20 findings from /opt/data/projects/WDOS/.hermes/stage2-ui-audit/findings.json; exact approved UI v1 acceptance for every stage; investigate missing OTP; deliver fresh PR to staging for Rex. No merge/deployment/live mail or provider configuration mutations without separate authorization.

## Current Phase
in_progress — M1 shared UI restoration and read-only delivery diagnosis. HEAVY, phased; Drax implementation, Groot verification, independent NightWing review.

## Next Step
Restore the shared auth shell to the actual approved HTML/CSS while inspecting WDOS-only Render/Brevo read-only evidence.

## Milestones
1. Reference/authority, baseline, boundaries and OTP diagnosis — in_progress.
2. Shared shell and per-screen/state repairs with regressions — pending.
3. Playwright desktop/mobile/five-language/reference comparison; all 20 issues accounted — pending.
4. Exact candidate canonical tests, independent review, fresh PR, hosted CI and code/security review — pending.
5. Verified PR handoff; distinguish code-ready from live OTP/provider/inbox evidence — pending.

## Authority
Approved v1 AUTH01–09 desktop/mobile/workflow states; source /opt/data/projects/WDOS/design-review/v1; frozen PDF SHA in DESIGN_APPROVAL.md. Approved five languages/eye controls retained. Review ribbons/mock identities excluded. Unapproved UI differences block acceptance in every stage; no substitutions or invented legal/support policy.

## Stateful preflight
- Browser → Django: CSRF, same-origin, allowlisted locale, untrusted input; never trust client identity/proof/status.
- Django → DB: Account, verification/recovery Token, invitation/person, MFA/session remain distinct; existing server lifecycle is authoritative. UI must project actual state, not fabricate success.
- Request → EmailIntent: durable encrypted outbox; worker → DB claim/lease → Brevo HTTP → provider acceptance. Provider acceptance is not inbox placement. Only read-only provider GETs in diagnosis.
- States: account pending/active/suspended; proof live/expired/used/revoked; MFA setup/challenge/confirmed/recovery; mail pending/sending/accepted/failed/unknown per existing model. Preserve existing guards and lawful transitions; no new auto-activation or MFA bypass.
- Identity/idempotency: token/invitation/account/person/mail-intent identities separate; resend cannot reuse obsolete proof; no duplicate send/replay/redeem. Stable existing outbox identities own retries.
- Crash windows: before enqueue = no send; committed pending survives request loss; provider acceptance with response loss = ambiguous, not blindly retried; accepted without local commit requires existing reconciliation. UI must not say delivered from enqueue.
- Expiry: reuse authoritative token/session/lease clocks and existing locked checks at before/equal/after expiry; resend feedback cannot authorize a send earlier than server throttle.
- Parity: register/resend/verify, recover/reset, MFA enrollment/challenge/recovery and pending/suspended/expired status; all five catalogs; deployed env and worker vs local test settings; no schema changes unless justified.
- Regressions: missing/invalid/used reset proof, localized hidden errors, pending verify action, repeated invitation success, lost-factor no bypass, language persistence through existing flush/cycle/logout, noncreating anonymous GET, outbox failure/unknown and no-send config diagnostics.

## Evidence
Baseline make verify exited 0 on fresh origin/staging 0c9b3bb5a52d14d9b2b5b9aae9580a0387e6821a; log /opt/data/projects/WDOS/.hermes/stage2-fidelity-baseline.log. Old worktree left unchanged.

## Final remediation handoff
- All S2-01..20 have implementation and regression mappings in docs/stage-02-fidelity-remediation.md.
- Parent verification: 100 tests (5 PostgreSQL-only skips); 77/77 browser/reference scenarios; source stability passed.
- Exact reference CSS cascade and previously omitted 24px spacer restored after independent rendered comparison; supplemental states reviewed separately from default reference samples.
- Browser-discovered missing enrolled MFA challenge fixed and replay tested.
- Dedicated staging OTP configuration corrected with explicit authorization; one app-triggered OTP provider-delivered. No UI feature deploy or merge.
- Published PR identity and exact-head CI/review evidence recorded in GitHub; stage acceptance remains Rex-gated.