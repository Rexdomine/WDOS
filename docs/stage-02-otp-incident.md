# Stage 2 OTP incident — 2026-09-23

## Finding
Live WDOS staging at merged revision `0c9b3bb5a52d14d9b2b5b9aae9580a0387e6821a` had neither `WDOS_BREVO_API_KEY` nor `WDOS_EMAIL_FROM` configured. A local private key is not deployment configuration. The existing safe outbox blocked provider dispatch without these settings; this was not a client OTP-input failure.

## Authorized correction and evidence
Rex expressly approved configuring the existing WDOS staging service, restarting that same revision, and one OTP check to his chosen recipient. Both variables were set from WDOS-only approved resources; all other environment entries preserved. Exact-target readback matched. The deployed application was then exercised via Playwright `/auth/resend/` once. Brevo recorded `requests`, `delivered` at 2026-09-23 20:35:32 UTC (21:35:32 WAT), and `opened` for `Verify your WDOS account`; message ID `<202609232035.72321933915@smtp-relay.mailin.fr>`. Open events can include mail-client automation; provider delivery is not a claim of inbox folder placement.

## Scope
No production/main deployment, merge, sender/domain modification, DNS change, bulk mail, or fabricated mailbox evidence. The new UI feature revision was not deployed. Recipient, provider key, and OTP omitted from tracked artifacts.

## Release gate
Future deployment acceptance must verify the actual target has provider configuration, approved sender, enabled mail worker and an authorized app-triggered message with provider delivery evidence. Generic success UI, local key presence, provider-only test mail, and CI alone are not delivery proof. Missing config is a deployment blocker, not resolved by visual sign-off.
