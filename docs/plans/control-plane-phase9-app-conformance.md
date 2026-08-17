---
status: active
owner: project
updated: 2026-08-17
tags: [plans, control-plane, authorization, conformance]
related:
  - ../architecture/control-plane-contracts.md
  - control-plane-phase8-contract-tests.md
  - ../STATUS.md
---

# Control-plane Phase 9 app conformance

## Goal

Make Party, Loans, Notify v2, and Rates consume the locked control-plane APIs
uniformly. Phase 9 removes app-local owner, role-name, and platform-admin
authorization decisions in favor of `WorkspaceAccess` and stable action codes.

## Baseline classification

### BLOCKER

None. Workspace ownership, forced RLS, explicit request identity, billing, and
entitlement contracts already pass the Phase 8 gate.

### FIX IN CURRENT PHASE

Thirteen runtime modules still make authorization decisions through direct
`is_platform_admin`, `get_workspace_role_name`, owner-ID, or app-local role-set
checks:

- Party: `access.py`;
- Rates: `access.py`;
- Notify v2: `access.py`, `views.py`;
- Loans: `access.py`, `views.py`, four domain services, and three web modules.

These are transitional authorization APIs under the accepted control-plane
contract. Phase 9 keeps each app's decorators and public helper signatures where
useful, but changes their decision engine to `resolve_workspace_access()` and
namespaced action codes.

### DEFER TO LATER PHASE

- `apps.tenant_apps` package naming and `Company.schema_name` routing-key
  migration, already governed by ADR;
- removal of legacy inbound Contact, Girvi, Notify, and integer-ID routes after
  telemetry or a compatibility deadline.

### OUT OF SCOPE

- domain workflow redesign in Loans;
- Notify provider operational acceptance;
- pricing, plan, or billing product changes;
- new roles, object ACLs, or authorization frameworks.

## Execution order

1. Freeze the 13-module direct-authorization baseline so debt cannot spread.
2. Convert Rates, the smallest app, and prove member/action/platform behavior.
3. Convert Party while preserving portal identity and Party action semantics.
4. Convert Notify v2, separating provider-administration actions from delivery
   workflow actions.
5. Convert Loans access helpers, then service and web-module callers in bounded
   workflow slices.
6. Require zero unsupported direct role/owner/platform decisions across all
   four apps and add their suites to the aggregate conformance gate.
7. Run the Phase 8 contract gate, four-app restricted-role RLS gate, Django
   checks, migration drift, and foundation integrity before closeout.

## Guardrails

- RLS remains ownership isolation, never action authorization.
- Platform override remains explicit and audited by middleware.
- App helpers must fail closed when request Workspace or Membership is absent.
- Stable action codes replace decision logic; role names may remain display
  data only.
- Preserve domain-service validation and existing HTTP method boundaries.
