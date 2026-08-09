---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, reports, documents, pilot]
related: [../plans/loan-operational-parity-pilot.md, ../plans/loans-rewrite-roadmap.md, 2026-08-06-loans-versioned-configurable-documents.md]
---

# Loans Pilot Report And Document Boundary

## Decision

The first Loans pilot uses one tenant-scoped PawnLoan report selector as the
source for screen, CSV, XLSX, and PDF output. Exports may format selector
results, but may not independently recalculate balances or interpret lifecycle
events. The canonical Party statement is Loans-owned: it combines current
positions derived by the balance fold with the Party's immutable PawnLoan event
history and does not merge Girvi records.

The required report projections are active loans, daily disbursals and
repayments, interest due, overdue loans, releases and renewals, collateral
storage inventory, regulatory-license expiry, and the Party statement. This is
the pilot boundary; matching Girvi's total report count is not required.

Existing typed document projections remain authoritative for the loan ticket,
repayment receipt, release memo/Form H equivalent, renewal agreement, notices,
and license register. Fixed loan-ticket recovery renders separate `Original`
and `Duplicate` pages with the same source verification identity and customer
and staff signature blocks. Published configurable loan-ticket layouts retain
their explicit copy composition; the pilot layout must use its existing
Original/Duplicate mode. Release output retains customer and staff signature
fields.

## Consequences

- A correction to the balance/event selector changes every report format
  consistently.
- Party statements are tenant- and workspace-scoped and cannot expose a Party
  that has no Loans-owned PawnLoan in the selected workspace.
- Spreadsheet and PDF rendering are presentation concerns only.
- Existing immutable official document issues and their exact bytes are not
  mutated to adopt a different layout or copy mode.
- Broader analytical reports and selected bulk exports remain post-pilot work.

## Rejected Alternatives

- Reimplementing balance formulas inside each export.
- Treating Girvi and Loans rows as one undocumented Party statement.
- Mutating already-issued document artifacts when pilot copy requirements
  change.
