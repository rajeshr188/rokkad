---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, collateral, verification, custody, evidence]
related: [2026-08-09-loans-hierarchical-collateral-storage.md, ../plans/loan-operational-parity-pilot.md]
---

# Loans Physical Verification Evidence

## Context

Storage projections say where collateral should be. The pilot also needs an
auditable physical count that never rewrites its original observations when a
discrepancy is investigated or corrected.

## Decision

1. An Owner starts a verification against a Vault or selected descendant. The
   session immediately freezes every in-vault item and its expected physical
   location in that subtree.
2. Each expected item receives exactly one immutable observation: found,
   missing, or misplaced. An item outside the frozen expectation may be
   recorded as unexpected. All expected rows must be observed before completion.
3. Completion freezes the session. PostgreSQL guards tenant agreement, the
   one-way OPEN-to-COMPLETED transition, valid evidence relationships, and
   update/delete rejection for expectations, observations, and resolutions.
4. Missing, misplaced, or unexpected evidence blocks storage transfer, full
   release, release-and-renew, and FundingLoan pledge until a separate Owner
   resolution is recorded.
5. Location correction appends a storage movement and updates the guarded
   location projection. It does not alter the observation.
6. Lost-collateral resolution requires current market value, a separately
   negotiated compensation amount, and a cash-settlement reference. It removes
   the item from its asserted storage location. Legal loan/custody treatment of
   a compensated loss remains a separate workflow boundary; this resolution
   must not manufacture a customer return.
7. A damaged classification is recordable, but remains an operational blocker.
   Damaged-collateral release policy is explicitly deferred.
8. The collateral and location UUID scan routes may preselect the active
   verification item and observed location. They do not record evidence by GET.

## Consequences

- Physical truth, legal custody, and storage location remain distinct concepts.
- Corrections are compensating evidence rather than history edits.
- Only the workspace Owner may operate this workflow during the pilot; a later
  Custodian permission can broaden access without changing the domain model.
- OP5 notice auditing can consume confirmed discrepancy evidence without
  making notification delivery the source of verification truth.
