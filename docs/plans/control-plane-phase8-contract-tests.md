---
status: active
owner: project
updated: 2026-08-17
tags: [plans, control-plane, contracts, tests, rls]
related:
  - ../architecture/control-plane-contracts.md
  - ../implementation/control-plane-phase7-residue-cleanup.md
  - ../STATUS.md
---

# Control-plane Phase 8 executable contract tests

## Goal

Create one traceable test gate for every accepted `CP-*` control-plane
invariant. Phase 8 consolidates and closes coverage gaps; it does not redesign
Workspace, billing, authorization, entitlement, or RLS APIs.

## Scope

| Contract family | Primary existing evidence | Phase 8 action |
| --- | --- | --- |
| CP-WORKSPACE | Middleware, resolver, and route-intent tests | Map and fill explicit identity, conflict, and tab-independence gaps |
| CP-RLS / CP-DATAPLANE | App RLS suites and tenancy primitives | Add a restricted-role isolation gate and direct-setting guard |
| CP-MEMBERSHIP / CP-OWNERSHIP | Phase 2 ownership/access tests | Fill atomic-transfer or reconciliation gaps |
| CP-AUTH | WorkspaceAccess and authorization intent tests | Prove action-code authorization and explicit audited override |
| CP-LIFECYCLE | Phase 3 lifecycle tests | Prove lifecycle/subscription independence and evidence retention |
| CP-BILLING / CP-ENTITLEMENT | Phase 4 billing and subscription tests | Prove idempotency, fail-closed policy, and context-preserving denial |
| CP-JOB | Commands and Workspace context tests | Prove explicit Workspace ID and self-owned context boundaries |

## Execution order

1. Build a machine-readable invariant-to-test registry using the exact IDs from
   `control-plane-contracts.md`.
2. Fail the registry test when an accepted invariant has no executable test
   reference or a reference no longer resolves.
3. Run existing focused suites and classify genuine coverage gaps.
4. Add the smallest behavioral tests needed for uncovered invariants.
5. Add a documented Phase 8 aggregate test command suitable for CI.
6. Run Django checks, migration drift, restricted-role RLS tests, and the full
   contract gate; record results and close the phase.

## Current progress

Slice 8.1 adds an exact 25-invariant registry and a guard that compares it with
the accepted contract document, imports every referenced test module, and
requires executable tests in each module. Behavioral evidence is intentionally
coarse at this stage; the next slice audits individual test methods and fills
real gaps before the registry can be treated as completion evidence.

Slice 8.2 replaces module-level references with exact executable test labels.
The audit identifies four genuine remaining gaps: audited platform override,
business-row ownership retention across lifecycle changes, all-model RLS
metadata coverage, and explicit Workspace context ownership for jobs/commands.
It also adds source guards proving that only `workspace_context()` sets the
PostgreSQL Workspace setting and surviving business apps do not import billing
models, transitions, or provider services.

Slice 8.3 closes `CP-JOB-001`. The Workspace-default command now has direct
evidence that it opens `workspace_context(workspace_id)` and an atomic unit;
the all-Workspace command proves it passes each explicit ID to that scoped
command. The PawnLoan reassessment command was found relying on ambient context
and now opens its own context around the batch service call.

Slice 8.4 closes `CP-LIFECYCLE-002` with database evidence. A Workspace-owned
Rates row is created, the Workspace is suspended, reactivated, and archived
through the canonical lifecycle service, and the test proves the row identity,
owner ID, and payload remain unchanged at each restricted lifecycle state.

Slice 8.5 closes `CP-AUTH-003`. Every successful platform membership override
is now audited after the explicit Workspace context is established, including
the Workspace ID, path, identity-resolution source, and an explicit override
marker. Platform authority still cannot bypass conflicting domain/path identity
or Workspace lifecycle restrictions.

## Guardrails

- Do not weaken fail-closed behavior to make a test pass.
- Do not use the migration-owner database role as RLS evidence.
- Do not encode roles inside RLS policies or billing state inside Workspace
  identity resolution.
- Do not broaden legacy aliases or introduce a second authorization API.
- Runtime changes require a demonstrated contract failure and focused tests.

## Completion criteria

- every accepted `CP-*` invariant maps to at least one executable test;
- references are validated automatically;
- restricted-role two-Workspace DML coverage passes;
- the aggregate gate is deterministic and documented;
- no migration drift or foundation integrity findings remain.
