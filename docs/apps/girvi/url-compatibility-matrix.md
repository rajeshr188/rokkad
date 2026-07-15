---
status: active
owner: girvi
updated: 2026-07-15
tags: [girvi, urls, compatibility, p6]
related: [README.md, workflows.md, refactor-plan.md, ../../STATUS.md]
---

# Girvi URL Compatibility Matrix

This document inventories duplicate/alias routes in `apps/tenant_apps/girvi/urls.py` before P6 cleanup. It defines canonical names to keep, alias names to phase out, and a safe rollback posture.

## Scope

- Runtime namespace: `girvi`
- Source of truth: `apps/tenant_apps/girvi/urls.py`
- Inventory date: 2026-06-21
- Current route count scanned: 133

## Duplicate Path Inventory

| Path | Names Today | Proposed Canonical | Proposed Alias To Keep Temporarily | Notes |
| --- | --- | --- | --- | --- |
| `girvi/loan-listreport/` | `Loan_list_repot`, `girvi_loan_list_report` | `girvi_loan_list_report` | `Loan_list_repot` | Canonicalize typo/misspelling alias only for historical reverse usage. |
| `loan/<int:pk>/transition/` | `loan_transition`, `girvi_loan_transition` | `girvi_loan_transition` | `loan_transition` | Runtime transition registry already uses `girvi_loan_transition`. |
| `statements/` | `statement_list`, `girvi_statement_list` | `girvi_statement_list` | `statement_list` | Templates currently use `girvi_statement_list`. |
| `statement/create/` | `statement_create`, `girvi_statement_create` | `girvi_statement_create` | `statement_create` | Keep temporary alias for bookmarks and older code paths. |
| `statement/<int:pk>/toggle_complete` | `statement_update`, `girvi_statement_update` | `girvi_statement_update` | `statement_update` | Canonical naming should keep app-prefixed style. |
| `storage_boxes/` | `storage_boxes`, `girvi_storage_boxes` | `girvi_storage_boxes` | `storage_boxes` | Both names are used in templates/navigation today. |
| `storage_boxes/add/` | `add_storage_box`, `girvi_add_storage_box` | `girvi_add_storage_box` | `add_storage_box` | HTMX forms mostly use prefixed name. |
| `storage_boxes/update/<int:pk>/` | `update_storage_box`, `girvi_update_storage_box` | `girvi_update_storage_box` | `update_storage_box` | Keep alias while templates and tests are normalized. |
| `storage_boxes/delete/<int:pk>/` | `delete_storage_box`, `girvi_delete_storage_box` | `girvi_delete_storage_box` | `delete_storage_box` | Same endpoint, dual name today. |

## Duplicate Name Inventory

These are duplicate route names bound to multiple paths and should remain by design only if both routes are intentionally supported.

| Name | Bound Paths Today | Action |
| --- | --- | --- |
| `girvi_release_create` | `girvi/release/create/`, `girvi/release/<int:pk>/create/` | Keep both for now; they represent two entry shapes (blank and loan-specific). Document behavior in release workflow docs/tests. |
| `loanitem_create_update` | `loanitem/<int:parent_id>/create/`, `loanitem/<int:parent_id>/update/<int:id>/` | Keep both for now; same handler intentionally supports create/update modes. |

## Current Usage Signals

Current runtime references use canonical names for the alias families in this matrix.
Alias names are now compatibility-only and exercised by route-intent tests.

This supports a controlled removal phase: keep aliases for one release window,
monitor for external reverse usage, then prune in one audited patch.

## Cleanup Sequence (P6)

Current progress (2026-07-15):

- Canonical names are now published in `apps/tenant_apps/girvi/urls.py` as `GIRVI_CANONICAL_ROUTE_NAMES`.
- Alias names are frozen as compatibility entries in `GIRVI_FROZEN_ALIAS_ROUTE_NAMES`.
- Canonical entries are listed before aliases for duplicate paths so resolver intent is explicit.
- Route-intent tests now guard canonical resolution and alias compatibility.

1. Keep canonical and alias names together; do not delete routes yet.
2. Normalize all internal reverse/template references to canonical names.
3. Add URL reverse regression tests for canonical names and alias compatibility names.
4. Add deprecation comments in `urls.py` for aliases with target removal milestone.
5. Remove aliases only after no internal references remain and a release window has passed.

## Exit Signal

P6 URL cleanup is ready to finalize when:

- Internal templates/views/tests only reverse canonical names.
- Alias names are exercised by explicit compatibility tests only.
- Alias removal can be done in a single patch with green URL regression tests.
