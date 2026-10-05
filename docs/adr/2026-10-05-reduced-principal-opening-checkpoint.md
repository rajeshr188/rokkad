---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, opening, continuation]
related: [2026-10-05-shared-monthly-interest-contract.md, ../plans/unified-loan-domain-correction.md]
---

# Explicit reduced-principal opening checkpoint

## Decision

The owner authorized LD-04 after selecting one loan domain and confirming the
common monthly interest boundary and captured-policy rounding. Add
`loan-opening-review/4` to the existing opening admission and continuation path.
An opening is the sole financial origin of its loan. It records reconciled debt
at cutover, not a new payout or a reconstruction of earlier receipts.

Original item principal, remaining principal and current-period principal base
are distinct reviewed facts. Preserve the original anniversary, maturity and
grace. Explicit cumulative recognized/unpaid interest and current-period
recognized/unpaid interest must reconcile. Current and future advance coverage
identifies actual period numbers and evidence references. Unknown is not zero.
The full eligible current charge, less current advance, is already recognized at
cutover; earlier cumulative recognition is accepted source evidence, not computed
from incomplete history.

Only the confirmed simple/full-month, per-item HALF_UP contract is supported.
The captured policy supplies the quantum. Future charges start after the covered
anniversary, use retained item balances, and apply subsequent reductions from the
next boundary. Advance coverage is deducted once. A principal reduction that would
over-cover a future period is blocked explicitly: refund, waiver and advance
reallocation rules have not been agreed and must not be invented.

Reuse immutable review JSON, the existing writer, allocations, remaining
obligations and paired servicing/reversal. No new tables or parallel loan model.
Migration 0059 adds a Workspace-scoped parent-locking insert guard rejecting a
mixture of migration opening and payout/renewal origin in either insertion order.
It does not rewrite or reinterpret existing events.

Publish `loan-opening-export/3` for review/4, with the existing version 2 row
inventory and explicit checkpoint semantics. Even an unserviced checkpoint uses
this version; old consumers must reject it. Existing review/2 and /3 and export/1
and /2 retain their meaning. Exact-identity recovery fingerprints the added guard.

## Boundaries and rollout

The generic source-dump bridge must not manufacture these checkpoint facts.
Authorized preparation supplies verified evidence to the existing per-loan
preview/confirmed commit. Financial history before cutover remains unavailable.
Checked-through transaction coverage and current valuation remain separate.

Synthetic tests exercise the confirmed rule; representative actual book examples
and staff acceptance remain required before cohort rollout. This decision does not
authorize production conversion or deployment. Rollback retains new-profile
readers and the origin guard, and stops new admission; it must not recalculate
accepted checkpoints using the old unchanged-principal rule.

Rejected: guessing period bases from one balance, replaying pre-cutover receipts,
adding another origin, changing old wire semantics, moving advance silently or
resetting tenure at import.
