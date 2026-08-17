---
status: complete
owner: project
updated: 2026-08-17
tags: [control-plane, urls, ui, workspace]
related: [../architecture/control-plane-contracts.md, ../STATUS.md]
---

# Phase 6 URL and control-plane UI contract

The global account and Workspace-selection plane uses `/app/...`. Once a
Workspace is explicit, canonical navigation uses `/w/<workspace_slug>/...`.
The slug is a public routing identity; the database primary key remains an
internal implementation detail.

Canonical Workspace settings routes cover settings home, setup and setup-state
mutation, preferences, team, sent invitations, new invitations, profile,
billing, roles, modules, security, and archive. Each slug adapter resolves the
Workspace through the shared resolver and invokes the existing authorization-
protected target view directly. This avoids duplicate business behavior and
avoids redirecting users to legacy integer URLs.

Primary desktop and mobile navigation, Workspace cards, breadcrumbs, dashboard
quick actions, invitation success/revoke flows, Workspace selection, and invite
acceptance all emit canonical slug URLs. The setup state and invitation actions
use the same URLs for full-page and HTMX requests; authorization and response
semantics remain in the target views.

Legacy `/orgs/...` and `/workspace/<id>/...` routes remain accepted only as
temporary inbound compatibility paths. They are not canonical, must not be used
in new templates or redirects, and may be removed only after a separate usage
and compatibility review.

Verification is protected by `apps.orgs.test_phase6_url_shells`, shell-render
smoke tests, and the org navigation/authorization suite. The Phase 6 focused
gate passes 114 tests.
