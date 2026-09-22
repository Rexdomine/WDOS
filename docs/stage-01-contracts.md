# WDOS Stage 1 contracts

## Authentication and session baseline

- Django owns session lifecycle and CSRF protection for browser sessions.
- Session cookies are HTTP-only and `SameSite=Lax`; production uses secure transport.
- Account identity, person identity, role identity, office identity, and provider/job identity remain separate boundaries.
- Authentication and authorization decisions are server-side; client state is never treated as proof of permission.
- Logout and session expiry must invalidate the server-side session before redirecting.
- Future provider integrations must persist intent before external calls and reconcile ambiguous responses before retrying.

This is a contract baseline, not a claim that a user-facing authentication workflow is complete in Stage 1.

## Persistence and migration baseline

- Development fallback is SQLite only when `DATABASE_URL` is absent.
- Review/staging is configured for PostgreSQL through `DATABASE_URL`.
- `python manage.py migrate --noinput` is the deployment migration command.
- `python manage.py makemigrations --check --dry-run` is a CI gate.
- `python manage.py seed_roles` is idempotent and establishes the initial system-role baseline.
