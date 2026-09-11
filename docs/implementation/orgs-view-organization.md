---
status: active
owner: project
updated: 2026-09-11
tags: [orgs, control-plane, maintenance]
---

# Organization view organization

The control-plane views portion of R12 is complete, following the Loans extraction.
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
| `web/account_preferences.py` | Account profile/settings and the existing class-based preference editor |
| `web/slug_routes.py` | Explicit slug adapters and 37 retirement aliases |
| `web/compatibility.py` | Existing permission/role helpers and subscription decorator retained for compatibility |
| `views.py` | Compatibility imports only; no handler implementations |

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

## Completion and cleanup evidence

The final extraction moved 66 functions/classes with identical ASTs and preserved
137 handler/helper/class/retirement exports. The duplicate original accounting
settings function was already overwritten by its 410 retirement alias; only its
unreachable definition was removed. The alias remains intact.

`BackupSchemaView` and `BackupDatabaseView` had no routes, imports, tests, template
links or other callers in repository-wide searches. They were removed with unused
StringIO/call_command/View imports. No backup command was run and no backup route
was added or changed. Operations still follow the documented deployment procedures.
Unused module logger/User initialization was removed. Source-based routing tests
now inspect slug_routes.py and the module registry's actual owning module.

Feature modules must not import orgs.views. Preserve the facade's decorated public
exports and route names. No service, model, template, permission or schema behavior
changed. Broader model/form/renewal-service organization remains separate review
work; it is not a reason to split files solely for size.

Tests must patch dependencies where each handler now uses them. Keep direct public
imports and URL tests to verify compatibility. Validation results are recorded in
[Status](../STATUS.md). Broader model/form/renewal-service work remains separate;
optional license scoping and Razorpay acceptance remain shelved.
