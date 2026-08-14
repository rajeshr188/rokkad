---
status: accepted
owner: project
updated: 2026-08-08
tags: [girvi, loans, cleanup, migrations, compatibility]
related: [2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../plans/girvi-audit-followup-plan.md, ../implementation/girvi-destructive-schema-reset-runbook.md]
---

# ADR: Girvi Canonical Cleanup And Coexistence Retirement

Date: 2026-08-08
Status: Accepted

## Context

The project owner explicitly removed the requirements to preserve production
Girvi data and support legacy integrations. The retained `Loan`/`LoanPayment`
models, lifecycle aliases, transitional module names, and Girvi/Loans unified
read layer therefore added complexity without serving an accepted contract.

This changes the rollout assumptions in the earlier Loans rewrite ADR. Its
accounting, numbering, lifecycle, and ownership rules remain applicable, but
its requirement for supported Girvi/Loans coexistence and unified reads does
not.

## Decision

1. `GivenLoan` and `TakenLoan` are the only Girvi runtime loan models.
2. Deprecated `Loan` and `LoanPayment` model classes and runtime resources are
   deleted. Migration `girvi.0029` removes their schema state.
3. Active audit evidence remains in `LoanChangeLog`, independent of deprecated
   loan models.
4. Girvi lifecycle code accepts canonical status values and canonical
   transition names only; compatibility translation is not a runtime contract.
5. Girvi managers live in `girvi.managers`; transitional manager/model modules
   are deleted and guarded by import-boundary tests.
6. The Girvi/Loans unified portfolio, comparison command, cross-app projection,
   and coexistence readiness check are retired. Loans readiness uses Loans-owned
   operational and reconciliation evidence.
7. Notify links business objects through `NotificationItem`; its deprecated
   direct Girvi-loan many-to-many relation is removed from runtime and migration
   state.
8. Historical migrations remain replayable for fresh tenant schemas. A
   destructive schema reset is a separate operator action and requires explicit
   target-schema approval under the existing runbook.

## Consequences

- Fresh tenant migration replay no longer depends on deleted runtime models.
- Legacy status strings, transition aliases, direct notification loan links,
  and coexistence APIs are intentionally unsupported.
- Existing environments that require historical data preservation must not use
  this cleanup path without a separately designed migration/export process.
- The destructive reset runbook remains unexecuted until schemas are explicitly
  approved.

## Superseded Decision

This ADR supersedes only the unified-read and supported-coexistence portions of
`2026-07-15-loans-rewrite-domain-and-cutover-architecture.md`. It does not
supersede DEA ownership, immutable accounting/reversal rules, regulatory loan
numbering, or Loans-domain lifecycle decisions.