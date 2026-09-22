# WDOS

WODDI Digital Operating System — the shared platform foundation for WGMN and WNNN.

## Repository workflow

- `staging` is the active integration branch.
- Feature branches are created from `staging` and merge back through pull requests.
- `main` is the protected release baseline.
- Promotion from `staging` to `main` requires explicit Rex approval.
- Production deployment is separately gated and is not enabled by this bootstrap.

## Stage 1

Stage 1 establishes the implementation spine: application shell, backend/API baseline, persistence and migration contracts, environment safety, CI, review deployment, seed strategy, observability, and QA harness. No business module is claimed complete by this foundation pass.

The authoritative stage contract remains in the project workspace under `development-baseline/stages/stage-01.md` until the implementation repository structure is finalized against the approved stack decision.

## Safety

Do not commit credentials, local environment files, provider tokens, database dumps, build output, or Render metadata. Review deployment targets and environment identity before every external operation.
