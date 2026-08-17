---
status: complete
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

## Current progress

Slice 9.1 records and freezes the 13-module direct-authorization baseline.
Slice 9.2 converts Rates: its helpers now resolve `WorkspaceAccess`, fail closed
without Membership or audited platform override, and authorize through stable
`data.view`, `data.create`, `data.edit`, and `data.delete` codes. Public helper,
decorator, and mixin signatures remain unchanged.

Slice 9.3 converts Party. Workspace membership and platform override now come
only from `WorkspaceAccess`; Party actions use stable `contact.*` / `data.*`
codes, and Party administration uses `workspace.settings.manage` instead of an
app-local Owner/Admin role-name set. Portal identity remains a separate customer
binding and is not broadened by staff authorization.

The focused Party authorization, model, selector, merge, workspace-isolation,
RLS, and control-plane contract suites pass. The legacy Party browser suite is
not part of this slice's green gate because its workspace fixture has no active
subscription and is redirected to billing before reaching Party views; that
pre-existing fixture gap is separate from Party authorization conformance.

Slice 9.4 converts Notify v2. Its ordinary notification workflow actions now
consume stable `data.*` codes through `WorkspaceAccess`, while WhatsApp provider
configuration requires the separate `workspace.settings.manage` action. The
settings UI consumes the same resolved access result instead of reconstructing
owner/Admin/platform policy. The conversion also standardizes the provider
setup request attribute as `request.notify_v2_workspace`. All 38 Notify v2
tests and the focused Phase 9 conformance gate pass. Only the nine reviewed
Loans modules remain in the direct-authorization baseline.

Slice 9.5 converts the central Loans access helper. It resolves and caches one
`WorkspaceAccess`; ordinary Loans entry requires `data.view`, setup requires
`workspace.settings.manage`, and owner-only custody/operational boundaries use
the Owner-only `workspace.transfer` action. Public decorators and the
`request.loans_workspace` compatibility attribute remain stable. Focused access,
explicit nonmember, slug-scoped business-entry, Phase 9, and control-plane
contract gates pass. The remaining baseline is eight reviewed Loans service and
view modules, to be converted in workflow-sized slices.

Slice 9.6 converts the Owner-only custody workflow across storage operations,
physical verification, and custody web actions. Every layer now consumes
`workspace.transfer` through `WorkspaceAccess`; domain-specific error types,
pilot restrictions, immutable evidence, discrepancy resolution, and notice
behavior are preserved. The notice suite fixture now includes the canonical
mirrored Owner Membership previously masked by a direct owner-ID shortcut.
Focused authorization, all eight notice tests, and four service-level custody
tests pass. Five reviewed Loans modules remain.

Slice 9.7 completes Loans and Phase 9. Auction and reversal services resolve
`WorkspaceAccess` directly; financial, reporting, and broad view helpers consume
the request-cached result. Administrator operations require
`workspace.settings.manage`, while Owner-only custody remains
`workspace.transfer`. The direct authorization baseline is zero across Party,
Loans, Notify v2, and Rates. `django_project.test_phase9_app_conformance_gate`
is the aggregate CI entrypoint.

Closeout passes 34 economics/auction/reversal/report tests, the 34-test aggregate
Phase 9 gate, the 12-test four-app restricted-role RLS gate, zero foundation
integrity findings, Django checks, and migration drift. Full Loans discovery
executes 404 tests: 315 pass;
89 legacy browser failures/errors are billing redirects from unscoped
`/loans/...` fixtures before Loans views execute. That fixture modernization is
explicit follow-up debt; Phase 9 does not reintroduce profile fallback or weaken
the billing boundary to make stale paths pass.

## Guardrails

- RLS remains ownership isolation, never action authorization.
- Platform override remains explicit and audited by middleware.
- App helpers must fail closed when request Workspace or Membership is absent.
- Stable action codes replace decision logic; role names may remain display
  data only.
- Preserve domain-service validation and existing HTTP method boundaries.
