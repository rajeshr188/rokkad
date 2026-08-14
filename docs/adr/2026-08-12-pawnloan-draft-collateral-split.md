---
status: accepted
owner: project
updated: 2026-08-12
tags: [loans, pawnloan, collateral, numbering]
related: [../../README.md, ../domain/loans-mixed-metal-origination.md]
---

# PawnLoan draft collateral split

## Decision

A PawnLoan in `DRAFT` may move one or more selected collateral items into one
new PawnLoan draft, provided at least one item remains on the source. The source
keeps its official loan number. The destination consumes exactly one new number
when the confirmed split transaction succeeds.

The operator previews destination Series, active product version, loan date,
tenure, number, and independently resolved economics before confirming. The
confirmation carries a fingerprint; stale source collateral or configuration
must be previewed again.

The service performs destination creation, collateral movement, source
recalculation, and change-log writes atomically. Existing collateral rows and
their photographs move without changing their stable identity. A failed split
rolls back the new draft and its sequence advance and creates no accounting
event.

## Boundaries

- Splitting is draft-only and is not a correction mechanism for approved,
  disbursed, released, or otherwise contractual loans.
- An empty source is not permitted; use ordinary draft editing instead.
- The source number is never returned or reused because the source loan still
  exists. Only the destination needs a new number.
- This draft split is the supported bulk-item workflow. The experimental
  Collateral Intake Batch was removed after operator comparison.
