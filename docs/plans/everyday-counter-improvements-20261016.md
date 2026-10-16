---
status: completed
owner: loans
updated: 2026-10-17
tags: [loans, counter, usability, performance]
related: [../implementation/everyday-counter-workflow-review-20261016.md]
---

# Everyday counter improvements

All selected slices are deployed in the [17 October release](../implementation/counter-release-20261016.md).
The table below retains the local-acceptance checkpoint; later release gates and
complete-suite fixes are recorded in that release note.

The owner selects the review's recommended order for implementation. Keep ordinary
Django selectors, existing financial calculations, reviewed posting commands and
Workspace authority. Implementation and local acceptance do not select deployment.

| Slice | Delivery | Status |
|---|---|---|
| EC-01/02 | Truthful paper assurance and clearly based collection amounts | Verified locally |
| EC-03 | Validated Workspace-local return context through loan work | Verified locally |
| EC-04 | Measured request-scoped financial reuse and redundant-read reduction | Verified locally |
| EC-05 | Compact filters/quick views and bounded current-amount rows | Verified locally |
| EC-06 | Focused shared entry, mobile summary and unsaved-change warning | Verified locally |
| EC-07 | Actual effective-day receipts/issuance and bounded priority-work preview | Verified locally |

Collection summaries remain read-only and basis-labelled; commands recalculate
under their existing authority/locks. Recorded balances, scheduled debt, collection
amounts and risk exposure remain separate. Unknown and provisional evidence stay
visible. Return URLs never confer access. No browser persistence of borrower facts,
new loan state, automatic posting, global financial cache or worker rewrite.

Test semantic truth, monetary parity, navigation validation, restricted permissions,
event/reversal reporting, current-source checks and desktop/phone usability. Measure
the same synthetic pages as the review; small local observations are not production
capacity claims. Record final checks and remaining bounds in an implementation note.

See the [implementation and acceptance record](../implementation/everyday-counter-improvements-20261016.md).
Release acceptance is recorded separately. Record-and-enter-next, large-history lazy
loading and worker scheduling changes are outside this delivery.
