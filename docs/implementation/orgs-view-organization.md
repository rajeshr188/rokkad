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

## Implemented families

Paths are relative to `apps/orgs/`.

| Module | Responsibility |
| --- | --- |
| `web/workspace_settings.py` | Workspace create/list/detail/update, resumable setup/checklist state, module availability, security activity; module registry and evaluation helper |
| `web/role_settings.py` | Owner/platform role-grant editing and its existing form |
| `web/access_helpers.py` | Existing Workspace access-context and owner-access helpers, reused by both extracted and remaining views |
| `web/team_members.py` | Member list, role change/removal, self-leave and owner-membership helpers |
| `web/invitations.py` | Sent/received invitation lists, send, confirmation, accept, decline and revoke; explicit query lookup helper |
| `web/workspace_lifecycle.py` | Archive confirmation, archived list, restore and explicit lifecycle transitions |
| `web/workspace_navigation.py` | Workspace selector, POST selection with safe redirects, and dashboard |
| `views.py` | Compatibility imports for moved handlers; remaining preferences/account/backup surfaces, subscription compatibility and routing handlers |

The first family moved nine handlers and three helpers. Team/invitations added
eleven handlers and three helpers; lifecycle/navigation added seven handlers.
All moved function/decorator ASTs remain identical.
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

1. Account/preferences and backup surfaces: inspect class-based views and existing
   retirement behavior before extraction.
2. Slug adapters and legacy compatibility: move only after their handler imports
   are stable. Preserve retired responses and old names; do not recreate the
   removed Loans response-rewriting dispatcher.

Tests must patch dependencies where each handler now uses them. Keep direct public
imports and URL tests to verify compatibility. Validation results are recorded in
[Status](../STATUS.md). Broader model/form/renewal-service work remains separate;
optional license scoping and Razorpay acceptance remain shelved.
