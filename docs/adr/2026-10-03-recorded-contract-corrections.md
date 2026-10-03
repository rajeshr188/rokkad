---
status: accepted
owner: project
updated: 2026-10-03
tags: [loans, paper-entry, corrections]
---

# Correct recorded original contracts through retained snapshot revisions

The completion programme includes errors in original paper dates, principal and
rates. Use the existing multiple disbursal/policy/schedule snapshot mechanism and
canonical compensation events. Preserve the original snapshots and issued copies.
Current loan fields and snapshot pointers are projections of the new retained
contract evidence, not edits to posted events.

A signed correction review binds every affected financial and custody dependency.
Compensate affected receipts/accruals and the origin, freeze a corrected origination
with the same loan identity, and replay supported paper totals chronologically.
Advance interest and deducted document charge reconcile to corrected proceeds.
Known financial closure requires exact revised settlement; no cash refund,
waiver, capitalization or physical reversal is inferred. Custody evidence remains
independent. Transaction coverage becomes stale until checked again.

Implement boundaries incrementally and explicitly track unimplemented dependencies
in the [plan](../plans/unified-loan-recording.md). A blocker must not be bypassed
through a direct update of a posted origin, linked renewal or auction record.

The local extension reviews a recorded successor together with its predecessor's
actual renewal cash. Amend original principal/rate and the paired actual renewal
date, compensating and replaying both collections. A current approved successor
may remain an unchanged locked dependency of an earlier paper correction; its
approval is never rewritten into a paper contract. The current projection of a
renewal resolves the active opening and settlement while retaining original FKs.

An item may now retain multiple renewal principal-opening lines, unique per event
and item. This mirrors retained disbursal revisions and does not duplicate active
principal. Custody date revisions have an explicit one-to-one `restatement_of`
link to the prior immutable row. They preserve the transition and source document;
they are fact revisions, not another movement. A deferred database guard requires
the matching canonical financial correction, recorder, date, reason and both IDs.
Ordinary movements still require their projected starting state. Current custody
reads omit superseded rows; all original rows remain available as evidence.

Single paper closures can correct date, reconciled amount and a positively known
recipient while preserving their confirmed/unspecified custody basis. Newly known
handover uses the separate append-only confirmation. Shared-batch date/custody
changes, arbitrary custody reversals, concessions and unsupported original contract
profiles remain separate capabilities, never direct edits to existing evidence.
