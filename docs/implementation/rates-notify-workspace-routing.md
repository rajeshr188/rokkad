---
status: active
owner: project
updated: 2026-09-08
tags: [rates, notify, workspace, routing]
related: [../STATUS.md, ../architecture/control-plane-contracts.md]
---

# Rates and Notify Workspace navigation audit

Operator navigation now uses named `workspace_rates:*` and `workspace_notify:*`
routes beneath `/w/<slug>/rates/` and `/w/<slug>/notifications/`. The existing
Party adapter moved unchanged to `apps/orgs/route_adapters.py` so all three apps
reuse the same check of middleware-selected Workspace identity. Decorated
business views continue to enforce their existing permissions and RLS context.

## Completed

- Rates list/detail/source links, create/edit/delete actions, crispy form
  Cancel/Add Source links, and dashboard shortcuts retain the Workspace slug.
- Rates and Notify model-generated absolute URLs use their owning Workspace.
- Notify list/detail/settings/integration navigation, digital-send and manual
  print/post status actions, ZIP downloads, and success/error redirects use
  canonical URLs. Retired notification/notice-group aliases return to the
  canonical batch list without reinterpreting legacy IDs as batch IDs.
- Individual artifact links now use an authenticated, permission-checked
  download view. It resolves the artifact under RLS and its requested batch,
  returns a file attachment, and rejects missing files or mismatched IDs.
- Restricted-role HTTP journeys exercise Rates creation/edit/deletion and Notify
  navigation/status changes/downloads, wrong Workspace/batch denial, CSRF, and
  permission denial. Test artifacts and status changes affect test data only.

Validation covers 161 passing non-shell tests (Rates, Notify, Party, MVP
journeys, and route/access contracts) plus 13 passing shell tests after updating
a stale dashboard request fixture. Two Notify mocks also gained the required
Workspace slug. Django system checks, migration drift, and whitespace checks
pass.

No provider message was sent and no physical print job was submitted.

## Boundary follow-up

The application follow-up now uses registered Workspace domains for authorized
staff admin links. Canonical WhatsApp callbacks have the narrow provider-auth
exception described in the
[ADR](../adr/2026-09-08-notify-provider-request-boundary.md); signature, phone,
identity, lifecycle, and RLS checks remain. Settings display canonical callback
URLs. The operator index redirect also uses the validated request Workspace.

Django public development media now denies raw Notify artifact paths. Guarded
downloads continue to work. Production web servers and object stores must enforce
private serving separately; this change does not revoke already-known external
storage URLs or verify deployment DNS/TLS. These are real-data pilot checks.

Physical mobile and printer acceptance remains deferred by the operator.
