# UI/reference verification contract

## Mandatory UI acceptance gate — every stage

The approved WDOS UI is a binding acceptance contract, not inspiration. Every in-scope screen, desktop/mobile layout, control, copy hierarchy and interaction state must match its approved reference exactly. Unapproved differences block acceptance even if unit tests, CI, code review or security review pass.

Before implementation, identify the approved screen IDs, reference version and any explicitly approved amendments. After implementation, exercise actual routes and success/error/empty/loading/permission/recovery states with Playwright; compare desktop/mobile captures side by side with those references. Include RTL and supported-language expansion where applicable. Record exact candidate SHA, reference identity, screenshots, tested states and every deviation. A deviation requires Rex's explicit versioned approval; never silently redesign, omit scope or change tests to bless a mismatch. Prototype review chrome and sample personal data are not production UI requirements.

Green engineering gates do not override failed visual/interaction acceptance. Rex reviews and explicitly accepts each stage; merge, deployment and next-stage authorization remain separate. Provider acceptance is not email inbox delivery.

## Required PR evidence
- Approved screen IDs/version and amendment ledger.
- Exact head SHA and screenshot matrix at matched viewports.
- Reference comparisons and complete issue-to-proof mapping.
- Actual journey assertions, not only DOM existence.
- Independent review and exact-head CI/security/code review results.
- Explicit blockers, external/provider limitations and acceptance status.

## Reproducible Stage 2 baseline
The canonical Stage 2 HTML/CSS/asset references are frozen in `docs/approved-ui/stage-02/` with original SHA-256 manifest. The approved PDF link and hash are recorded there and in `DESIGN_APPROVAL.md`. CI runs `scripts/check_ui_reference_manifest.py`; this detects reference corruption, not visual equivalence. A deliberate test mutation of a temporary copy was rejected. Never interpret this check as a substitute for screenshot/state review.
