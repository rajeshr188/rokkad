---
status: accepted
owner: project
updated: 2026-08-17
tags: [adr, workspace, request, rls, security]
related:
  - ../architecture/control-plane-contracts.md
  - 2026-08-14-shared-schema-workspace-rls-tenancy.md
---

# Workspace Request Authority And RLS Context

## Status

Accepted.

## Context

`SecureWorkspaceMiddleware` currently considers Domain, Workspace-bearing path,
and `UserProfile.workspace`, mirrors the result to `request.tenant`, validates
Membership and subscription, and enters `workspace_context()`. Context
processors and several control-plane views can opt back into profile fallback.
This makes a navigation preference capable of changing request and database
authority. Domain/path mismatch handling also differs for superusers.

The working RLS primitive already accepts a positive Workspace ID, opens an
atomic transaction, sets transaction-local `app.workspace_id`, rejects
conflicting nesting, and restores context on exit.

## Decision

- Only a registered Workspace domain or recognized Workspace-bearing path may
  establish request authority.
- If both exist, they must resolve to the same Workspace or fail closed for all
  actors.
- Global requests always have `request.workspace = None` and unset PostgreSQL
  Workspace context.
- `request.workspace` is set only after the explicit identity is validated and
  Membership or the accepted platform-admin override is established.
- The PostgreSQL context must match `request.workspace.id` for the complete
  scoped unit and must be cleared afterward.
- `workspace_context(workspace_id)` remains the only normal context-setting API.
- `UserProfile.workspace` is navigation preference only. `request.tenant` is a
  temporary compatibility mirror.
- Unscoped business paths need an explicit Workspace domain; on a global host
  they fail closed or redirect to an explicit Workspace URL.

## Alternatives considered

1. Keep domain > path > profile precedence. Rejected because conflicting or
   absent explicit identity can silently select a different RLS scope.
2. Make domain always win. Rejected because a conflicting path is evidence of
   an invalid request, not a preference decision.
3. Make path the sole authority. Rejected because registered Workspace domains
   are already a valid explicit product route and support branded entry.
4. Store active Workspace in session/profile. Rejected because tabs interfere
   and ambient state is not a safe database authority.

## Consequences

Explicit URLs are tab-safe and auditable. Global pages cannot accidentally see
Workspace context. Platform overrides remain explicit and RLS-bound. Some
legacy routes and context processors will stop receiving an implicit Workspace.

## Migration implications

Phase 1 changes middleware resolution, removes profile authority fallback,
narrows context processors, characterizes unscoped routes, and expands cleanup
tests. Phase 6 standardizes URLs. Phase 7 removes `request.tenant` and stale
schema terminology. No RLS model or policy change is required.

