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
