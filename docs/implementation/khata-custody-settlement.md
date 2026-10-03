---
status: implemented-local
owner: loans
updated: 2026-10-01
tags: [khata, collateral, exchange, reductions, settlement, verification]
related: [khata-agreement-changes.md, ../architecture/khata-technical-design.md, ../adr/2026-10-01-khata-agreement-design.md, ../plans/khata-delivery-design.md]
---

# Khata custody and settlement checkpoint

The owner authorized collateral exchanges and reduction returns, followed by
settlement. These three backend workflows extend the
[agreement-change checkpoint](khata-agreement-changes.md). Operational screens,
issued documents and production activation remain pending.

## Exchanges and actual handover

`services/khata_collateral.py` exposes `preview_exchange` and `record_exchange`.
Receive replacement items using the existing deposit command before confirmation.
An exchange selects distinct outgoing and incoming items, supports one-to-many
and many-to-one groups, and requires the same metals on each side. Current
same-day approved Rates evidence values both sides, with no cross-metal offset.
The current photo policy is checked; missing prices or required photos fail.

The workspace owner's current exchange WARN/BLOCK policy applies to both
per-metal replacement shortfalls and retained account LTV. WARN records known
shortfalls and permits the exchange; BLOCK rejects them. Overdue WARN/BLOCK
applies independently, using actual unpaid receipts and next-day overdue rules.
A warning exchange never waives the hard backing requirement for a later draw.

Confirmation requires `loan.release` and `data.edit`. It records immutable
`EXCHANGE`, valuations and typed IN/OUT `KhataCollateralSelection` rows. Outgoing
items immediately stop backing draws and cannot be selected again. Accepted
replacement membership cannot be reused for another exchange, although that item
may later be exchanged out. Physical custody still includes outgoing items until
actual handover.

`preview_handover` and `record_handover` complete one reserved item at a time.
`HANDOVER` requires `loan.release`, the original reserving source, an actual
recipient and a handover reference. A linked item can leave custody only once.
Previously committed exchanges remain eligible for handover after owner policy
changes; later policy choices do not silently revoke the accepted exchange.

## Reduction returns

Revision preview/approval accepts optional `outgoing_ids`. Returns must accompany
a formal limit reduction. Approval freezes the selected items and current
valuation, but reserves nothing until activation. Activation atomically records
approved terms, actual required/chosen repayment and outgoing reservations.
Existing cash/approval permissions apply, with `loan.release` additionally required
when reserving returns.

All due interest must be cleared, and retained collateral must cover actual
principal after repayment at the agreed LTV. Exchange WARN cannot override either
check. Annual accrued interest that is not yet due keeps its original schedule.
Stale account, prices, photos or terms require a fresh review and approval.

If reduction handover happens while the account remains active, recheck current
due interest and same-day retained collateral coverage before releasing the item.
Reserved items never contribute to this cover. Once financial settlement has
collected all debt, the original reservation remains a valid handover source
without requiring a new valuation for zero debt.

## Financial settlement and pending custody

`services/khata_settlement.py` exposes `preview_settlement` and
`record_settlement`. The quote collects all actual principal and unpaid simple
interest through today's closure date. Annual accounts owe elapsed interest even
before their annual due date. Already received interest is deducted. Exact
activated revision segments govern a closing partial month, using actual days
within the original monthly anniversary interval; the original first-month
minimum applies once, including same-day closure.

`SETTLE` records typed principal and interest amounts, payment reference, newly
finalized periods/segments and allocations atomically under `loan.repay`.
`KhataInterestPeriod.charged_through` identifies a closing partial interval;
null retains the full existing period meaning. Same-day minimums can have zero
elapsed segments. Existing finalized charges are preserved rather than rewritten.

Settlement zeroes principal and unused entitlement, freezes `settled_on`, and
reserves all remaining eligible items. Earlier exchange/reduction reservations
retain their original source. The account becomes `SETTLED_RETURN_PENDING` while
any item is physically held, then `CLOSED` after the final actual handover.
Interest stops on `settled_on`, independently of later return dates. Closed and
settled accounts reject new financial actions, deposits, photos and proposals.
Cash receipt authority does not confer physical handover authority.

## Database and verification

Migration `0037_khata_custody_settlement` adds the directly Workspace-owned
selection table with forced RLS and registry coverage, operation/source fields,
closing-period evidence and account lifecycle projections. Existing immutable
operation, valuation, charge and allocation guards remain in force. Deferred
checks enforce complete selections, same-metal groups, strict exchange policy,
hard retained LTV and collection/allocation of every unpaid closing charge.
Account projections derive from actual settlement and handover sources.

Commands lock Workspace then account, validate today's business date, check
permissions/write availability, recheck review hashes and preserve UUID retry
identity. Failed child writes roll back money, reservations and lifecycle
together. Concurrent confirmations cannot reserve an item or collect settlement
twice. Restricted-role DML tests cover isolation, immutable selections, forged
parents/lifecycle, omitted evidence and policy/LTV/interest bypass attempts.

141 focused/regression tests pass, including 26 custody/settlement cases and the
115 earlier khata, registry, ordinary partial-month policy and storage cases.
Migration consistency, Django system checks, documentation links and
syntax/whitespace checks also pass. Only the dedicated local test database was
migrated; no development or production activation.

Cancellation/compensation of committed exchanges or returns is not implemented:
never delete reservations or edit posted sources to undo them. Reviewed correction
workflows, UI/private media/document delivery, shared summaries and native recovery
remain release gates before real khata use.
