---
status: accepted
owner: loans
updated: 2026-09-30
tags: [loans, portability, interest]
---

# Exact partial-period evidence in loan history v2

Weekly and daily fractions cannot reliably round-trip through the six-decimal
loan-history/1 contract. Upfront-covered periods also need an accrual record even
when they produce no financial event. The owner authorized correcting this limit
and adding contextual policy guidance.

## Decision

Add loan-history/2 to the existing bounded staging, preview and explicit-confirmation
workflow. Keep the v1 reader and sealed v1 re-exports compatible. Native exports use
v2; a v1 import extended with event-free accruals upgrades its export to v2.
No existing accepted document, loan terms or posted financial record is edited.

V2 carries the frozen minimum-first-month flag, all four partial-period rules,
exact decimal fraction/unrounded calculation, calendar denominator, elapsed and
chargeable days, per-item rates/bases/money, advance application and release catch-up.
Export reconciles saved projections and exact event evidence against frozen inputs.
Import recalculates each period with the servicing engine and rejects discrepancies.
Only database projections are quantized; portable values are not rounded to fit them.

The timeline explicitly distinguishes financial events from zero-recognized accrual
evidence (`event_recorded=false`). Restore creates the accrual header and item lines
without inventing an event or balance change. Stable accrual identities live in the
existing immutable import references alongside item/event identities.

V2 freezes the repayment-structure tuple and permits non-amortizing flexible
partial-payment and single-payment bullet products. Destination mapping must match
that tuple, original tenor, calculation contract and grace. Earlier v1 keeps its
flexible-product interpretation. All existing limits and excluded workflows remain.

The existing batch profile guard admits v2 while retaining immutable profile and
exact accepted-document matching. Reversal of the migration refuses if v2 batches
exist. Workspace authorization, forced RLS, approval tokens and atomic replay are
unchanged. This is a partial loan export, not a Workspace restore or binary backup.

## Policy help

Setup offers a Bootstrap help drawer with a regular guide link as the no-JavaScript
fallback. Slab/compound-only controls hide without losing submitted values or errors.
A pre-save summary shows scope, effective start and treatment. A separate read-only
example uses shared calendar/fraction/rounding functions with an unchanged single-item
principal; it explicitly does not quote a real loan or modify policies.

See the [v2 contract](../contracts/loan-history-v2.md) and
[user guide](../flows/loan-interest-policies.md).
