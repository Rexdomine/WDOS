# WDOS contributor instructions

Read `DESIGN_APPROVAL.md`, `DESIGN_AMENDMENT_V2.md`, `docs/ui-acceptance.md`, the applicable stage contract, and the planning files before stage work. Local orchestration context, when available, is `/opt/data/projects/WDOS/PROJECT_CONTEXT.md` and its `development-baseline/`; absent local files are not permission to guess stage scope.

## Mandatory UI acceptance gate — every stage

The approved WDOS UI is a binding acceptance contract, not inspiration. Every in-scope screen, desktop/mobile layout, control, copy hierarchy and interaction state must match its approved reference exactly. Unapproved differences block acceptance even if unit tests, CI, code review or security review pass.

Before implementation, identify the approved screen IDs, reference version and any explicitly approved amendments. After implementation, exercise actual routes and success/error/empty/loading/permission/recovery states with Playwright; compare desktop/mobile captures side by side with those references. Include RTL and supported-language expansion where applicable. Record exact candidate SHA, reference identity, screenshots, tested states and every deviation. A deviation requires Rex's explicit versioned approval; never silently redesign, omit scope or change tests to bless a mismatch. Prototype review chrome and sample personal data are not production UI requirements.

Green engineering gates do not override failed visual/interaction acceptance. Rex reviews and explicitly accepts each stage; merge, deployment and next-stage authorization remain separate. Provider acceptance is not email inbox delivery.
