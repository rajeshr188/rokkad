---
status: active
owner: project
updated: 2026-08-05
tags: [domain, accounting, dea]
related: [../flows/dea-posting-flow.md, ../implementation/dea-vouchers.md, ../implementation/dependency-policy.md, party.md, ../adr/2026-06-18-party-domain-model.md]
---

# Accounting / DEA

DEA is the accounting core. It owns charts/accounts, accounting documents, vouchers, voucher lines, journal entries, posting rules, opening balances, and period controls.

## Boundary

- Operational apps create business documents and request accounting effects through the DEA facade.
- DEA converts business intent into vouchers and journal entries.
- Period-lock validation belongs in posting engine paths, not scattered view-only checks.
- Posting rules should be registered and test-covered for every seeded `VoucherType`.

## Document Layers

- Business documents: `PaymentVoucher`, `JournalEntryVoucher`, `ExpenseVoucher`, loan events, sale/purchase documents.
- Accounting layer: `Voucher`, `VoucherLine`, `JournalEntry`.

## Party And Subledger Accounts

Accounting account selection should be based on business event, party role, and accounting purpose. It should not be based on the party identity alone.

A single Party can have multiple subledger accounts:

- Customer receivable -> Accounts Receivable control
- Supplier payable -> Accounts Payable control
- Borrower loan receivable -> Loans Receivable control
- Lender loan payable -> Loans Payable control
- Customer advance -> Advances from Customers control
- Supplier advance -> Advances to Suppliers control

Gross receivables, payables, advances, and loan balances should remain separately visible. Net exposure can be reported, but posting should preserve the distinct account purposes.

Implementation status:

- `dea.PartyAccountMapping` maps `party + role_key + purpose + optional event_type` to a DEA `Account` and optional control `Ledger`.
- The public DEA facade exposes `resolve_party_account()`, `resolve_customer_account()`, and the legacy-compatible `ensure_customer_account()`.
- `dea.Account.contact` is now a foreign key so one bridged `Customer`/`Party` can have multiple subledger accounts.
- `contact.Customer.account` remains a compatibility read alias for older code. New posting code should use the DEA facade resolver and pass an explicit role/purpose.
- Girvi borrower/lender and DEA sales/purchase invoice posting rules now use explicit role/purpose account resolution.
- The side-by-side Loans app delivers `PawnLoanAccountingEvent` disbursals through the public DEA facade. DEA's `PAWN_LOAN_DISBURSAL` rule owns the source-linked voucher, open-period enforcement, principal-control/cash journal effect, and borrower loan-receivable attribution; repeated delivery returns the existing posted effect.
- The side-by-side Loans repayment service persists the current-date allocation and source event before delivery. For itemized loans, the original-principal portion is also frozen into immutable collateral allocation lines in highest-monthly-rate-first order, with collateral ID as the deterministic tie-breaker; capitalized-interest principal remains separately classified. Later accruals reconstruct item bases from active allocation evidence, and repayment reversal excludes the reversed event without mutating it. DEA's `PAWN_LOAN_REPAYMENT` rule owns cash receipt posting to principal control, interest income or interest receivable according to the immutable policy snapshot, fee income, and borrower subledger attribution. Unresolved delivery blocks dependent loan events, and repeated request keys or delivery do not duplicate either accounting or allocation evidence.
- PawnLoan monthly accrual headers retain high-precision calculations and store currency-rounded newly due amounts. New itemized loans also persist immutable collateral-level lines containing principal base, frozen metal rate, period fraction, calculated interest, advance interest consumed, and newly due interest. Under accrual accounting, uncovered interest debits interest receivable and credits interest income with borrower attribution, while prepaid coverage debits Unearned Revenue and credits interest income without creating a second receivable. Under cash accounting, accrual and capitalization remain operational-only, and a prepaid period creates no second charge. Explicit capitalization reclassifies interest receivable into principal control; repayment preserves the capitalized-interest component so collection credits interest income instead of principal control.
- PawnLoan disbursal, repayment, accrual, and capitalization corrections are explicit reversal source events linked one-to-one to immutable originals. Loans enforces administrator authority, mandatory reason, posted-original readiness, and newest-first dependency order; DEA reverses the original voucher through its journal-reversal service. Cash-policy operational-only events receive compensating domain events without synthetic accounting vouchers.
- New same-loan partial collateral releases are prohibited. Partial repayment returns no collateral; full release settles and closes the source; release and renew records an immutable source settlement plus newly numbered successor opening. DEA may post the net cash movement while retaining both gross business facts and their source links.
- Itemized full release and renewal settlement freeze each collateral tranche's remaining original principal into immutable closing lines. An explicit release-and-renew successor freezes its newly allocated item principal, metal rate, and predecessor lineage in immutable opening lines. Successor repayment and interest calculations reconstruct from the active opening event; reversal excludes the reversed event instead of editing evidence. Legacy aggregate loans receive no invented item allocation, and capitalized interest cannot be carried into an explicit successor until an item-attribution rule exists.

## BusinessDoc Classification

A business event is any business fact that may have accounting meaning, such as cash paid, cash received, an expense incurred, interest accrued, a loan released, stock moved, or a period closed.

Not every business event should become a DEA `BusinessDoc` model. A model should be a business document when it represents one accounting-relevant fact with a clear effective date, economic payload, voucher type, audit identity, and idempotency fingerprint. If the object is a long-lived domain aggregate with many lifecycle events, each accounting event should be posted separately through a document or event payload.

For example, Girvi `GivenLoan` is a loan aggregate, not one accounting document. Its disbursal, repayment, release, auction, sale, and interest accrual events are the accounting-relevant facts. Those events may produce `PaymentVoucher`, `JournalEntryVoucher`, or event payloads that DEA translates into `Voucher`, `VoucherLine`, and immutable `JournalEntry` records.

## Current Concerns

- Ensure every external caller uses the facade instead of models/posting internals.
- Revisit voucher uniqueness constraints if event-driven Girvi needs multiple vouchers against one loan/document.
- Keep fingerprint behavior consistent: nullable until posting or assigned when drafts are created.

Archived DEA sources are preserved in [archive/dea](../archive/dea/).
