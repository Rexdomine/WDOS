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
