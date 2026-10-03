---
status: implemented-local
owner: loans
updated: 2026-10-01
tags: [khata, interest, receipts, rls, verification]
related: [khata-opening.md, ../architecture/khata-technical-design.md, ../adr/2026-10-01-khata-agreement-design.md, ../plans/khata-delivery-design.md]
---

# Khata interest collection checkpoint

The owner's next-step instruction continues the local backend implementation.
This checkpoint adds completed-period finalization and actual interest receipts
to the [opening backend](khata-opening.md). It does not expose khata screens or
enable production. Agreement changes, exchanges, reductions, settlement,
corrections, documents, shared summaries and native recovery remain pending.

The subsequent [agreement-change checkpoint](khata-agreement-changes.md) extends
this implementation for activated revisions and split interest. The unchanged-term
guard and pending-work descriptions below refer to this earlier collection slice.

## Delivered records and commands

Migration `0035_khata_interest_collection` adds three directly Workspace-owned,
forced-RLS tables and registry gates:

- `KhataInterestPeriod`: a frozen monthly index, start/end, due date, actual
  charge, minimum adjustment, final charge and calculation contract.
- `KhataInterestSegment`: the exact numerator/denominator, dates, period days
  and typed agreement reference underlying each charge.
- `KhataInterestAllocation`: a typed receipt-to-period link and positive amount.

All are append-only, guarded against foreign Workspace/account/source links and
raw UPDATE/DELETE. Their source operations preserve actor, recorded timestamp,
business date, request UUID/hash and versioned calculation/allocation evidence.
`ACCRUE` finalizes charges and carries no cash; `INTEREST.amount` records actual
interest received. Neither changes principal or unused entitlement.

`services/khata_servicing.py` provides:

- `finalize_interest`: freeze all completed, previously unfinalized months under
  the existing repayment permission. It rejects an empty batch and retries an
  already completed identical request without duplicating charges.
- `preview_interest_payment`: read-only review of the proposed amount and
  oldest-due allocation. No finalization or receipt occurs during preview.
- `record_interest_payment`: requires `loan.repay`, today's business date, an
  actual receipt/payment reference and an unchanged review hash. Any required
  completed-month finalization and the receipt commit atomically.

These services follow Workspace/account lock order, existing membership/action
and commercial-write checks, UUID conflict handling and atomic rollback. They do
not apply new-lending gates for inactive borrowers/series, stale collateral prices
or expired associated licences to interest collection. Those are separate from
Workspace access restrictions, which still apply.

## Calculation and allocation boundary

The activated opening revision is the only live agreement in this checkpoint;
unapproved draft proposals never become interest terms. Monthly percentages,
anniversary dates, simple interest and KHATA-1 rounding remain unchanged.

Only completed monthly periods can be frozen here. Monthly accounts owe each
charge on its monthly anniversary. Annual accounts preserve monthly charges with
their shared annual anniversary due date; finalizing a month does not make it
prematurely due. A same-day/early-closure minimum remains a calculation quote,
not an ordinary collectible advance receipt. Settlement will collect it through
its separate workflow.

Partial receipts allocate oldest due date, then monthly index. No advance or
excess interest credit is accepted. Annual receipts can partially pay the annual
bill; the constituent monthly allocation remains explicit. No interest compounds
on unpaid dues. Principal and unused entitlement remain unchanged after payment.

Canonical balances use frozen charges where available, calculate unfinalized
periods, and subtract actual allocations. They expose gross calculated interest,
paid interest, outstanding interest, due interest and overdue interest separately.
Overdue begins the day after the due date. Clearing all overdue dues removes the
interest-based withdrawal block; the other withdrawal checks still apply.

Database guards enforce contiguous anniversary periods, opening-term amounts,
exact segment evidence, full receipt allocation, due-date eligibility,
oldest-first allocation and charge/receipt caps. Deferred guards reject incomplete
period/segment/allocation children. Frozen operation snapshots prevent later
evidence additions from extending historical charges or receipts.

The SQL calculation guard deliberately supports unchanged opening terms and
completed full months only. The revision/settlement slice must extend it together
with activated-term selection, split segments, closing partial periods and their
tests. Merely allowing active-account proposals is insufficient and remains
disabled. Correction/supersession is also not implemented by editing these rows.

## Verification and release boundary

Verification uses the dedicated local test database with
`django_project.settings.test`; no development or production database is migrated.
94 tests pass across the 20 collection cases and existing khata, registry,
ordinary partial-month policy and storage inventory suites. Migration drift,
Django system checks, documentation links and syntax/whitespace checks also pass.
The collection suite covers monthly/annual anniversaries, partial oldest-first
payments, zero rates, no advance/excess collection, no compounding, frozen charge
authority, UUID retries/conflicts, stale reviews, midnight/date boundaries,
rollback of both cash and accrual, permission/commercial-write checks, overdue
unblocking and two concurrent cashiers. Restricted-role tests exercise populated
cross-workspace isolation, immutable evidence, forged parents/charges, skipped
dues, over-allocation, missing child records and late allocation attacks.

Full release remains gated on remaining servicing, custody handover, compensation,
UI/documents, combined summaries, recovery verification and a named pilot. Existing
ordinary-loan workflows and production data are unchanged by this increment.
