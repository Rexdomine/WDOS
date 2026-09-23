# Stage 2 welcome, language and password-control follow-up

## Scope
- Approved welcome hierarchy: one primary join CTA, sign-in link and language selector row, full-width cream notice with shield SVG.
- Core UI locales: English, French, Portuguese, Arabic and Kiswahili. Arabic uses RTL. These are Stage 2 UI translations, not a claim of translated transactional emails or country-local language readiness. Native-speaker/client linguistic approval remains pending.
- Inline password eye controls on login, registration and both reset fields; hidden by default, independent controls, keyboard activation, localized accessible labels/pressed state, focus and value preservation, no submit.
- Locale survives authentication/logout/security rotation as an allowlisted preference only. Authentication flags/proofs are not retained across logout. Auth authorization, token expiry, outbox and schema are unchanged.

## Verification
- `env -u DATABASE_URL -u WDOS_BREVO_API_KEY -u WDOS_EMAIL_FROM make verify PYTHON=<project-venv>/bin/python`: 64 tests run, OK, 5 PostgreSQL-only skips. System checks, migration parity and static collection passed. PostgreSQL races require hosted CI.
- Chromium: five locales at desktop 1440px and mobile 390px; all 10 combinations passed. Verified language selection/navigation persistence, Arabic direction, notice/button width equality, no horizontal overflow and login/register/reset password controls with Enter/Space, preserved values, independent reset controls, focus and zero submit events.
- Visual inspection: welcome hierarchy and final Arabic mobile reset render checked. Language placeholders are forbidden by catalog tests; complete same-key catalogs and localized validation are tested.
- No merge, deployment or live email send performed. Rex owns acceptance and merge.
