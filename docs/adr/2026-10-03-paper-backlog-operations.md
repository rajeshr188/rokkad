---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, custody, operations]
---

# Complete paper entry with ordinary operational evidence

The owner authorized the remaining recommendations in the
[delivery plan](../plans/unified-loan-recording.md). Reuse ordinary financial,
custody and per-loan transaction-review records. Do not create a parallel ledger.

A paper closing number is optional. Allocate the ordinary system release number
when absent, retain that basis in immutable closing evidence, and bind the actual
number to the signed review. Never describe the assigned number as an original
paper number.

For a financially closed loan whose handover is unconfirmed, a later confirmation
appends a custody event attached to its original release and a source-referenced
change log. Preserve the original release, its unknown timestamp, and settled
money. Record the actual handover date separately from entry time. Serialize under
the loan/item locks; signed review and request identity prevent stale or duplicate
confirmation. An unknown subsequent loan is never inferred.

Book/day progress is operational evidence, separate from transaction completeness.
Batch reviews still create an immutable review for each explicitly selected loan,
bind every financial fingerprint, and either all commit or all roll back. Neither
operation can certify that unentered paper loans exist in the financial system.

Reviewed archive admission can establish financial closure while leaving physical
cash/customer handover unknown, using the same PAPER_CLOSED meaning as manual entry.
Source identity and archive conflict checks still apply.
