# Stage 2 — authentication security and operations

Status: implementation candidate, not accepted or activated. Stage 2 maps AUTH-01..09. Django `auth.User` is preserved; additive `accounts` records own WDOS security state. No leadership/office/membership is created by registration or invitation claim. Approved v1 CSS, fonts and logo are copied unchanged; `live.css` supplies working-form accessibility and responsive adjustments. English/email-only review; Arabic linguistic approval, phone transport, legal wording and final IT policies are not invented.

## Boundary and state contract

- Browser → Django: native POST forms, CSRF, validated bounded inputs, no role/person claims; recovery secret in fragment then hidden POST, not query/access log. GET does not consume proofs. Hidden fields are untrusted.
- Django → DB: transaction and account lock serialize token/MFA/link/session-version changes. Account pending → active only on contact proof. Suspension never cleared by login/recovery. Verified account and permanent Person remain distinct; invitation claims only an existing intended person, never silently merge identities. One-to-one Person linkage plus person lock prevents two accounts claiming the same record.
- Session: password → pending MFA → authenticated for staff, superusers or any scoped grant. Admin uses the same gateway. Current account, active user, security version, absolute/idle expiry and second-factor requirement checked on each request. Scope permission helper requires exact role/network/geography/function and nonrevoked/unexpired grant; no implicit HQ authority. Business dashboards remain later stages.
- Proofs: keyed SHA256 digests only; verification six digits with five attempts per issuance, all other proofs high entropy. Account/purpose binding, atomic consume and predecessor invalidation. Equal-to-expiry is expired. Reset revokes sessions/pending MFA and leaves MFA intact. TOTP counter prevents replay; encrypted seed; hashed one-use recovery codes shown once.
- Django → outbox → Brevo: the HTTP request only commits an encrypted durable intent; it never waits on provider latency (avoids a network timing account-enumeration oracle). The supervised mailer polls committed intents every ten seconds. Fixed HTTPS API endpoint, no credential-bearing redirects, bounded timeout, inline HTML/text (no hosted template prerequisite). Key/sender are server-only. Acceptance/message ID is not delivery. Missing config = blocked, not fake success.
- Email lifecycle: pending/blocked → sending → accepted/failed/unknown; expired payloads erased. Interrupted `sending` becomes `unknown` through recovery command. Unknown/failed are never automatically resent. Explicit user resend issues a new proof and invalidates predecessors. A lost provider response or failed local terminal commit may result in email receipt while local state remains unknown; receipt never grants authority. No exactly-once email delivery claim.
- Throttles: keyed identifier hashes, database fixed windows. 10 subject attempts / 15 minutes, 60 source-address attempts / 15 minutes; resend cooldown 60 seconds. Source address is REMOTE_ADDR, not arbitrary forwarded input; deployment proxy topology must be verified before activation. Limits behind a shared proxy can be conservative; never trust a client-controlled X-Forwarded-For.

## Provisional IT policy

12-character minimum, Django similarity/common/numeric validators, max 128 at forms. This is NOT an external breached-password database check; final breach-checking policy/provider remains an IT decision. Verification 10m; reset 30m; invitation 7d; pending MFA 10m; idle 30m; absolute session 12h or 7d remembered. Remembered sessions still expire on idle/revocation. TOTP 30s with ±1 step, monotonic accepted counter. 8 high-entropy recovery codes. All values require final IT approval.

Existing legacy users without Account fail closed; no automatic email-based identity linking or privilege migration. Trusted operator must reconcile any legacy identities before granting access. Django admin grants do not imply WDOS scoped grants. Password reset is not an MFA reset; lost factors require the approved operator identity-verification policy, not an invented automated bypass.

## WDOS-only configuration

- `WDOS_BREVO_API_KEY`: supplied securely, never committed or exposed to browser.
- `WDOS_EMAIL_FROM`: WDOS sender verified in Brevo; discover after key is supplied, do not borrow another project's sender.
- `WDOS_PUBLIC_ORIGIN`: canonical HTTPS review origin; default is WDOS staging. Do not derive reset URLs from request Host.
- `DJANGO_SECRET_KEY`: strong deployment-only secret, also domain-separated into encryption/HMAC keys. Rotation needs planned MFA/outbox re-encryption or governed recovery; do not casually rotate.
- `WDOS_SECURE_COOKIES=1`: default; local HTTP browser testing alone may explicitly set 0.

No real email was sent during implementation tests. Final activation needs key, verified sender, account permissions/transactional availability and controlled acceptance + mailbox evidence.

## Runtime supervision

The existing Docker service starts `python -m wdos_project.runtime`: migrations and role seeding complete before Gunicorn and the auth mailer start. Either child exiting stops its sibling and exits nonzero for platform restart. SIGTERM stops both. The mailer is part of the same WDOS service; no additional paid resource or VPS permission change is introduced. DB row locking fences multiple mailers; each intent crosses the provider boundary once. A crash after claim is conservative unknown, never automatic replay.

## Operator commands

Run only in the intended WDOS environment with authorized operator access:

- `python manage.py recover_auth_email` — bounded 100 unsent intents; expire stale payloads, mark interrupted sends unknown, never replay unknown/failed sends. After configuring Brevo, run this for still-valid blocked intents, otherwise request fresh proofs.
- `python manage.py invite_person --person UUID --email ADDRESS` — existing person only, expires 7d, queues invitation; never prints secret. No role appointment or arbitrary person creation.
- `python manage.py set_account_access --email ADDRESS --action suspend|restore|grant-staff|revoke-staff` — registered/verified accounts, audit and revoke sessions. Privileged gateway enforces MFA. This is infrastructure-operator access, not an unprotected web endpoint.

Audit stores event types/account references, never plaintext proofs/passwords/provider payloads. Retention, centralized audit access and production backup/restore remain cross-stage governance, not claimed complete here.

## Verification and release

Canonical command: `make verify` (override `PYTHON` only to select the WDOS venv). GitHub runs the same command with PostgreSQL16. SQLite validates functional paths but explicitly skips real PostgreSQL race tests; a local pass is not concurrency certification. CI must pass before merge.

Tests cover real forms, verification expiry/replay/attempt limit, reset/session revocation, pending/suspended states, MFA setup/replay/recovery/admin fencing, intended-person invitation claims, scope denies/revocation, CSRF, untrusted redirects, provider response classes, ambiguous sends and expiry. Migration state must match models; additive upgrade must be checked on a Stage1 database before review deployment.

Deployment/merge and final acceptance are separate gates. Production remains untouched. No claim of live Brevo delivery, client policy acceptance or Stage2 completion follows from passing tests.
