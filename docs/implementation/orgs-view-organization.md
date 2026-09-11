---
status: active
owner: project
updated: 2026-09-11
tags: [orgs, control-plane, maintenance]
---

# Organization view organization

R12 continues with the control-plane views after the Loans view extraction.
This is a responsibility split, not a change to authorization or user navigation.
The [control-plane contracts](../architecture/control-plane-contracts.md) remain
authoritative.

## Implemented first family

Paths are relative to `apps/orgs/`.

| Module | Responsibility |
| --- | --- |
| `web/workspace_settings.py` | Workspace create/list/detail/update, resumable setup/checklist state, module availability, security activity; module registry and evaluation helper |
| `web/role_settings.py` | Owner/platform role-grant editing and its existing form |
| `web/access_helpers.py` | Existing Workspace access-context and owner-access helpers, reused by both extracted and remaining views |
| `views.py` | Compatibility imports for moved handlers; remaining team, invitations, preferences, lifecycle, selection/dashboard and routing handlers |

Nine handlers and three helpers moved with identical function/decorator ASTs.
All route names and decorated public handler imports remain intact. The new
modules use absolute project imports and never import `orgs.views`. The shared
helpers still delegate to existing access/permission policy; this move does not
introduce a second policy implementation.

The create/update views continue using control-plane services. Role changes still
require the existing owner/platform checks, Workspace context, stored grants and
revision checks. Request identity, lifecycle, billing, entitlements, audit and RLS
remain separate checks. No model, service, template or migration changes are part
of this extraction.

## Remaining families and dependency review

1. Team and invitations: membership lists/role changes/removal, capacity,
   acceptance, verified identity and invitation actions. Keep service calls and
   access checks intact; inspect shared owner/membership helpers before moving.
2. Lifecycle and navigation: archive/restore/transitions, selector, preference
   changes and dashboard. Preserve independent explicit browser-tab identity.
3. Account/preferences and backup surfaces: inspect class-based views and existing
   retirement behavior before extraction.
4. Slug adapters and legacy compatibility: move only after their handler imports
   are stable. Preserve retired responses and old names; do not recreate the
   removed Loans response-rewriting dispatcher.

Tests must patch dependencies where each handler now uses them. Keep direct public
imports and URL tests to verify compatibility. Validation results are recorded in
[Status](../STATUS.md). Broader model/form/renewal-service work remains separate;
optional license scoping and Razorpay acceptance remain shelved.
