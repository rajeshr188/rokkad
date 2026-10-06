---
status: accepted
owner: project
updated: 2026-10-06
tags: [loans, evidence, admission]
---

# Bounded loan evidence extensions

The owner requested completion of LC-05. Extend existing ordinary admission and
servicing, preserving old evidence meanings and one financial origin per loan.

Implement in controlled slices: supplied opening item splits and actual fee
components; multi-item archive reconciliation; delegated preparation with owner
commit; explicitly timed opening checkpoints; verified closed-position admission.
Each new evidence shape is versioned and validated during replay as well as writes.

Paper receipts with outstanding fees require the actual fee component, including
zero. The rest pays interest then principal. Staff supply multi-item principal
splits; current payments retain the existing priority. Neither rule guesses facts.

Delegated preparation does not approve or post finance. Existing catalog mappings
are reusable; owner review and commit revalidate source, permissions and mappings.
An older review is invalidated whenever preparation changes.

Date-only cutovers remain end-of-day. A new precise checkpoint requires an actual
timestamp, and same-day activity must establish that it happened afterward. No
timestamp is fabricated to make a historical transaction eligible.

A verified terminal checkpoint establishes zero debt at closure without claiming
earlier receipt totals, a payout or a settlement transaction. Original agreement
and archive evidence remain available. Unknown physical handover stays unknown.
Such admission cannot be reversed as a settlement that never existed. Complete
history admission remains available where actual receipts reconcile.

No bulk archive conversion or production deployment is part of this decision.
