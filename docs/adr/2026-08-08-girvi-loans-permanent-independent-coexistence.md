---
status: superseded
owner: project
updated: 2026-08-08
tags: [girvi, loans, ownership, coexistence, dea]
related: [2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, 2026-08-08-girvi-canonical-cleanup-and-coexistence-retirement.md, 2026-08-08-operational-accounting-integration-deferral.md, ../apps/loans/architecture-and-girvi-parity.md]
superseded_by: [2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md]
---

# ADR: Girvi And Loans Permanent Independent Coexistence

Date: 2026-08-08
Status: Superseded

This ADR's strict record-ownership and no-dual-write rules remain active during
temporary coexistence. Its permanent-end-state decision is superseded.

## Context

Girvi and Loans now provide distinct, viable loan workflows. The prior rollout
architecture treated Loans as the eventual owner of all new pawn-loan
origination while Girvi serviced only records it already owned. The project
owner instead requires both applications to remain available in parallel as
independent products.

The Girvi canonical cleanup removed deprecated Girvi models and the temporary
cross-app comparison and unified-read implementation. It did not require either
application to own or mutate the other's records.

## Decision

1. Girvi and Loans are permanent independent tenant applications.
2. Both applications may originate new records when enabled for a workspace.
3. The application that creates a record owns its complete lifecycle. A Girvi
   loan remains writable only through Girvi; a Loans `PawnLoan` remains writable
   only through Loans.
4. Records are not copied, transferred, synchronized, or dual-written between
   the applications. Similar identifiers do not imply shared identity.
5. Girvi and Loans retain independent regulatory setup, number sequences,
   policies, services, lifecycle states, permissions, documents, and URLs.
6. DEA remains the sole owner of its vouchers, journals, period controls,
   posting rules, and accounting reversals. Operational delivery may be
   deferred under the accounting-integration ADR. Source and idempotency
   identities must include the owning application whenever delivery is active.
7. Navigation must expose Girvi and Pawn Loans as distinct destinations. A
   workspace may choose a default loan landing page, but that choice must not
   disable the other application or change record ownership.
8. Combined portfolio or management reporting is optional. If introduced, it
   must be read-only, source-labelled, selector/facade based, and route every
   mutation to the owning application. Permanent coexistence does not restore
   the retired comparison or unified-write surfaces.
9. The existing `loan__new_module_enabled` setting is transitional. Until it is
   replaced, it may select the canonical landing route and presentation only;
   it must not block Girvi creation or imply a data cutover.

## Product Boundary

- Girvi owns `GivenLoan` and `TakenLoan`, including its mature operational,
  custody, repledging, and lender-facing workflows.
- Loans owns `PawnLoan` and its event-oriented policy, outbox, reversal,
  accrual, auction, renewal, and release workflows.
- A future Loans `FundingLoan` requires its own architecture decision and does
  not absorb Girvi `TakenLoan` records automatically.

## Consequences

- Operators need explicit product guidance when both applications can create a
  similar customer pawn loan.
- Independent reconciliation against DEA is mandatory for each application.
- Numbering collisions across applications are acceptable only when every
  external and accounting reference also carries source-app identity; otherwise
  workspaces must configure visibly distinct prefixes.
- Cross-app dashboards cannot infer ownership from a numeric primary key.
- Retirement of either application requires a future explicit ADR; it is not an
  assumed end state of the current Loans roadmap.

## Superseded Decisions

This ADR supersedes the eventual replacement, single-origination-owner, and
legacy-servicing-only portions of
`2026-07-15-loans-rewrite-domain-and-cutover-architecture.md`. It does not
supersede that ADR's Loans-domain, numbering, lifecycle, custody, accounting,
outbox, or reversal rules.

It is compatible with
`2026-08-08-girvi-canonical-cleanup-and-coexistence-retirement.md`: that ADR
retired a particular cross-app unified-read/comparison implementation and
legacy Girvi compatibility surfaces, not independent application operation.

## Next Implementation Slice

Replace cutover semantics with independent module availability and default
navigation policy. The preferred workspace settings are:

- `loan__girvi_enabled`
- `loan__pawn_loans_enabled`
- `loan__default_module` with `girvi` or `loans`

That slice must include migration/backfill behavior for the existing setting,
separate navigation entries, route tests, permission tests, and proof that
enabling either application does not disable creation or servicing in the
other.
