---
status: active
owner: girvi
updated: 2026-06-22
tags: [girvi, legacy, commands, lifecycle]
related: [../apps/girvi/refactor-plan.md, ../roadmaps/girvi_refactor_plan.md, ../STATUS.md]
---

# Girvi Legacy Command Lifecycle

This note documents policy and lifecycle state for legacy/manual Girvi management commands.

## Scope

Command files in `apps/tenant_apps/girvi/management/commands/`.

## Policy State

- `do`:
  - Runtime state: disabled.
  - Behavior: always raises `CommandError` with explicit migration path guidance.
  - Reason: avoid accidental execution of unsafe legacy/manual flows.

- `missingcol`:
  - Runtime state: opt-in legacy compatibility utility.
  - Behavior: blocked by default; enabled only when `GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS=1`.
  - Intended use: controlled import/rehearsal operations for deprecated `models.legacy.Loan` rows.

## Guardrails

- Automated tests enforce:
  - `do` remains disabled.
  - `missingcol` requires explicit opt-in environment flag.
  - only `missingcol.py` can import deprecated `models.legacy`/`models.loan` command-side.
  - runtime modules must not import legacy manual commands (`do`, `missingcol`).

## Lifecycle Intent

- Normal runtime and operational workflows should use service/workflow layers and canonical command paths.
- Legacy manual commands are compatibility seams only.
- Any future archival/removal should be done as an explicit roadmap slice with migration/rehearsal impact review.
