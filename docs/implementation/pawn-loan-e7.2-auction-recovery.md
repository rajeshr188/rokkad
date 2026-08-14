---
status: completed
owner: loans
updated: 2026-08-04
tags: [loans, auction, recovery, custody, dea, phase-7]
related: [../plans/loans-rewrite-roadmap.md, ../apps/loans/architecture-and-girvi-parity.md, ../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md]
---

# PawnLoan E7.2 Auction And Recovery

## Boundary

`PawnLoanAuction` is the Loans-owned source document for disposing pledged
collateral after default. DEA owns the recovery voucher and immutable journal;
Notify v2 owns delivery of the auction notice. The original PawnLoan, auction,
notice, accounting event, collateral snapshots, and custody history remain
linked and auditable.

The first safe recovery boundary requires auction proceeds to equal the current
canonical debt exactly. A lower amount would require an explicit bad-debt or
shortfall-write-off document. A higher amount would require a borrower-surplus
payable and payment workflow. E7.2 rejects both cases instead of folding either
amount into principal, interest, or fees.

## Lifecycle

1. An administrator initiates an auction for an active overdue loan whose
   accounting is current and whose collateral is entirely in the vault.
2. Loans allocates an immutable attempt number and auction number, then creates
   a source-linked auction notice through Notify v2.
3. The auction can start only on or after its scheduled date and only after the
   linked Notify job reports `SENT`.
4. An initiated or in-progress auction can be cancelled with an administrator
   reason, so a no-bid or aborted sale cannot strand the loan in recovery.
5. Completion finalizes any partial-period catch-up interest, reads the
   canonical balance, requires exact recovery, snapshots buyer and collateral
   evidence, moves custody to `AUCTION_DISPOSED`, posts `AUCTION_RECOVERY`
   through the outbox to DEA, and closes the loan.
6. An administrator can reverse a completed auction with a reason only while
   the loan and custody remain compatible. Compensating accounting events are
   posted, collateral returns to `IN_VAULT`, and the loan reopens as active.

## Accounting And Evidence

The recovery payload separates original principal, capitalized-interest
principal, current interest, and fees. The Loans delivery adapter routes it to
the `PAWN_LOAN_AUCTION_RECOVERY` DEA voucher rule. Normal outbox idempotency,
posting failure visibility, open-period checks, and newest-first reversal rules
apply.

Each completion stores immutable `PawnLoanAuctionItem` snapshots and custody
events. The loan detail exposes the auction lifecycle plus verification-linked
auction notice and recovery memo PDFs.

## Deferred But Essential

- Shortfall/write-off approval and accounting document.
- Borrower-surplus liability and payment document.
- Bid register, bidder management, reserve price, and external auction-house
  integration if operational evidence requires them.
- Broader auction reports and customer-portal exposure.

These are deliberate follow-on workflows, not implied behavior in the current
exact-recovery path.

## Verification

- Tenant migration: `loans.0010`
- Django system check and migration-drift check
- Focused model, notice, payload, cancellation, real DEA posting, custody, and
  reversal coverage
- Full tenant-aware Loans regression: 164 tests pass
- Migration applied to all local tenant schemas with `migrate_schemas --tenant`
