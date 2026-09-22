# WDOS

WODDI Digital Operating System — the shared platform foundation for WGMN and WNNN.

## Repository workflow

- `staging` is the active integration branch.
- Feature branches are created from `staging` and merge back through pull requests.
- `main` is the protected release baseline.
- Promotion from `staging` to `main` requires explicit Rex approval.
- Production deployment is separately gated and is not enabled by this bootstrap.

## Stage 1

Stage 1 establishes the implementation spine: Django application shell, backend/API baseline, persistence and migration contracts, environment safety, CI, review deployment, seed strategy, observability, and QA harness. No business module is claimed complete by this foundation pass.

Current Django foundation:

- `GET /` — Django app shell payload
- `GET /health` and `GET /api/health` — database-backed health checks
- `foundation.Role` model with initial migration
- `python manage.py seed_roles` — idempotent system-role seed
- `docs/stage-01-contracts.md` — auth/session and persistence contracts
- `Dockerfile` — Django/Gunicorn staging container
- `.github/workflows/ci.yml` — Django checks, migration check, and tests

The authoritative stage contract remains in the project workspace under `development-baseline/stages/stage-01.md`.

## Safety

Do not commit credentials, local environment files, provider tokens, database dumps, build output, or Render metadata. Review deployment targets and environment identity before every external operation.
