---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, authorization, rbac, membership]
related:
  - ../architecture/control-plane-contracts.md
  - platform-admin-override-policy.md
---

# Workspace Authorization Contract

## Status

Accepted.

## Context

Current authorization combines `Membership.role`, hardcoded role maps,
`Role.permissions`, Django permissions, installed Guardian object permissions,
orgs decorators, direct role/owner comparisons, and separate Party, Loans,
Rates, and Notify v2 access helpers. These mechanisms often agree but do not
share one result or action vocabulary. Subscription access is also evaluated
inside Workspace middleware, blurring unrelated checks.

## Decision

Phase 2 introduces `WorkspaceAccess`, constructed by
`resolve_workspace_access(actor, workspace)`. It contains actor, Workspace,
Membership, explicit platform-override state, and one effective set of stable
namespaced action codes. Its public operations are conceptually:

```python
access.can("party.view")
access.require("team.member.remove")
```

`Membership` is mandatory except for the accepted superuser-only platform
override. `Role.permissions` stores role-to-action assignment through a
controlled mapping; hardcoded maps seed defaults but are not a second runtime
authority.

`WorkspaceAccess` answers Membership and RBAC only. Workspace lifecycle,
billing, entitlements, RLS, and domain-object invariants stay separate. Views,
services, templates, jobs, and commands must consume the same policy result.

## Alternatives considered

1. Standardize only the existing decorators. Rejected because services,
   templates, and jobs would still reconstruct policy.
2. Use role names as the public API. Rejected because roles are bundles, not
   stable business actions, and owner checks already conflict.
3. Use Guardian for every Workspace action. Rejected because the repository has
   no demonstrated object-ACL need and Guardian adds a second assignment store.
4. Put entitlements and lifecycle inside `WorkspaceAccess`. Rejected because a
   commercial grant and an actor permission answer different questions.

## Consequences

Every action has one answer across layers, business apps stop querying
Membership, and platform override remains centralized. Phase 2 must migrate a
large but mechanical set of decorators, role checks, templates, and app access
helpers. Domain services still enforce object-specific rules after RBAC.

## Migration implications

Phase 2 defines the action registry, makes Membership roles non-null, builds
`WorkspaceAccess`, converts control-plane authorization, and adds privilege and
concurrency tests. Phase 7 may remove Guardian if no concrete object ACL is
accepted. Phase 9 converts surviving data-plane helpers to the same interface.

