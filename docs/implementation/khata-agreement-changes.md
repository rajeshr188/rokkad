---
status: implemented-local
owner: loans
updated: 2026-10-01
tags: [khata, agreement, revisions, reductions, interest, verification]
related: [khata-interest-collection.md, ../architecture/khata-technical-design.md, ../adr/2026-10-01-khata-agreement-design.md, ../plans/khata-delivery-design.md]
---

# Khata agreement change checkpoint

The owner's next-step instruction adds local backend support for approved limit
and monthly-rate changes. It extends the [collection checkpoint](khata-interest-collection.md).
There are still no operational khata screens or production activation.

## Proposal, approval and activation

Active accounts can append immutable agreement proposals using `propose_revision`.
Only the limit and monthly percentage can change in this workflow. Frequency,
LTV, lender identity, account number, original opening date and anniversaries stay
fixed. An unchanged proposal is rejected. Earlier proposals remain available as
evidence, but cannot become current terms merely because their number is higher.

`services/khata_revisions.py` exposes reviewed approval and activation commands:

- `preview_revision` shows current/proposed terms, principal, unused entitlement,
  required/chosen principal repayment and the resulting financial position.
- `approve_revision` requires `loan.approve` and a borrower agreement/consent
  reference. It records `TERMS_OK` without changing debt or interest terms.
- `preview_activation` rechecks the approved proposal against the current account.
- `activate_revision` records `REVISE` with the approved terms and any actual
  principal repayment atomically. Cash collection requires `loan.repay`; an
  approver without it cannot receive money. Non-cash activation requires
  `loan.approve`. A cashier can execute a previously approved reduction without
  acquiring proposal-approval authority.

Proposal preparation continues to require `data.edit`. Every command independently
checks Workspace access and commercial-write policy. Commands lock Workspace then
account. UUID retries return completed evidence; changed instructions under the
same UUID fail. Routine effective dates must be today. A proposal from a previous
day needs a new dated successor. Intervening operations or a newer proposal make
approval stale; no automatic silent reapproval occurs.

Pending proposals/approvals do not govern or block a withdrawal under the current
activated terms. Such a withdrawal changes the account and invalidates the pending
approval. Later withdrawals bind the current activation's approval source.

## Principal, entitlement and interest

Canonical principal and unused entitlement replay actual withdrawal and revision
operations in sequence. A limit increase changes entitlement and the interest
base, not principal or cash advanced. A decrease subtracts the limit difference
from unused entitlement down to zero. Repayment reduces principal independently;
it never refills unused entitlement.

A reduction below actual principal requires at least the difference repaid in
the activation transaction, with an actual payment reference. Extra principal
repayment is allowed within that formal reduction up to principal outstanding.
No principal repayment is accepted on a rate-only change or limit increase.
A reduction above actual principal need not invent a payment. No standalone
principal payment or same-limit renewal/payment workflow is introduced here.

Interest uses activated revisions only. Each effective date splits the relevant
monthly interval into exact segments; round the sum once to paise. Annual bills
continue to sum monthly charges on the original anniversary. The opening minimum
uses the original first-withdrawal limit/rate exactly once, even if terms change
on the opening day. Same-day activations remain recorded, while the latest supplies
that day's terms. This follows the technical design's date-granularity convention;
retain its review item before the pilot rather than claiming intraday accounting.

Already finalized months and existing receipts are immutable. A change at a
monthly boundary can affect the new month, never the closed interval before it.
Activation that would reinterpret finalized interest is rejected. No correction
or historical backdating is provided by this workflow.

## Lending eligibility and custody boundary

A limit increase requires an active borrower/series and, for associated series,
a currently usable licence. Rate-only changes and reductions are servicing;
they can proceed after licence expiry or series/borrower inactivity, subject to
Workspace permissions and write availability. Number-counter exhaustion is not a
servicing restriction. This is the local implementation classification; broader
licence/default treatment remains a pilot review item in K32/K33.

No collateral leaves custody in this checkpoint. A revision without a return does
not need new collateral prices, and due interest remains on its schedule. The
owner's overdue BLOCK policy continues to govern withdrawals/exchanges rather
than preventing a repayment/reduction. Current-price hard LTV still governs each
subsequent withdrawal. A future reduction return must additionally clear due
interest and prove retained collateral LTV, regardless of exchange warning mode.
It must reserve outgoing items and record actual handover; this checkpoint does
not permit an active account's ordinary unopened-item return command.

## Database and verification boundary

Migration `0036_khata_agreement_changes` adds operation kinds/shapes and a unique
activation per agreement. It extends the existing immutable source/RLS tables;
no new tenant tables or ordinary-loan data changes are needed. SQL guards validate
canonical principal/entitlement, approved repayment, same-account/source links,
frozen agreement fields and finalized-period boundaries. Withdrawal LTV now uses
net actual principal after formal repayments, while unused entitlement is checked
independently.

Completed-period guards reconstruct dated activated terms and validate each exact
segment against its agreement. The common integer denominator preserves exact
monthly sums and half-up rounding; no floating-point or rounded segment sum is
authoritative. Deferred guards require every expected segment, including periods
containing several activations. Sources are bounded by the accrual operation's
sequence, so later changes cannot extend old evidence.

The revision tests cover pending proposals, split interest, annual dues, original
minimums, same-day ordering, half-paise segments, reduction repayment/entitlement,
fixed contract fields, stale approvals, retries, licence boundaries, permission
separation and concurrent activation. Restricted-role DML tests reject missing
repayment, overdrawing repaid capacity, foreign parents, altered frequency/LTV,
unactivated segment sources and backdating into a finalized month.

115 tests pass: 21 revision cases and the 94 earlier khata, tenancy registry,
ordinary partial-month policy and storage inventory cases. Migration consistency,
Django system checks, documentation links and syntax/whitespace checks also pass.

Only the dedicated local test database is migrated. Exchange/custody reservations,
reduction returns, full settlement, compensation, UI/documents, integrated
summaries and native recovery remain release gates. Do not enable real khatas
with those workflows incomplete. Production deployment is outside this checkpoint.
