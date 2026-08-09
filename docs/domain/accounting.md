---
status: active
owner: project
updated: 2026-08-07
tags: [domain, accounting, dea]
related: [../flows/dea-posting-flow.md, ../implementation/dea-vouchers.md, ../implementation/dependency-policy.md, party.md, ../adr/2026-06-18-party-domain-model.md]
---

# Accounting / DEA

DEA is the accounting core. It owns charts/accounts, accounting documents, vouchers, voucher lines, journal entries, posting rules, opening balances, and period controls.

Operational delivery is controlled by audited workspace preference
`accounting__integration_mode`. `DEFERRED` is the default while central
accounting matures: Loans records immutable source events and outboxes but does
not run DEA readiness or automatic delivery. Those outboxes remain `PENDING`;
they are not ledger truth and must not be reported as posted or failed. `DEA`
mode preserves the existing posting and reversal behavior. Existing DEA
history is never rewritten. Deferred activation requires an explicit,
reconciled workflow; the proposed design is documented in
[Loans deferred-to-DEA activation](../adr/2026-08-09-loans-deferred-to-dea-activation.md).
Changing the preference alone is not a safe activation. Girvi `GivenLoan` disbursal and
`TakenLoan` activation record canonical versioned outbox events instead of
creating DEA payment vouchers while deferred. `TakenLoan` repayment is also
decoupled: immutable Girvi `LoanRepayment` rows are operational truth, while
DEA mode atomically links a payment voucher and deferred mode records one
pending `TAKEN_LOAN_REPAYMENT` event without fabricating accounting evidence.
Settlement combines these rows with only unlinked historical DEA vouchers.
Correction uses a separate exact compensating repayment row, never mutation.
Other Girvi money events remain on DEA until separate slices replace their
operational payment-voucher evidence safely.

## Standalone Successor Architecture

Current DEA remains the runtime accounting authority. Accepted ADR
`2026-08-07-standalone-accounting-transaction-kernel.md` governs a side-by-side
successor at `apps.tenant_apps.accounting`. It is registered as a tenant app and
has side-by-side persistence, but no runtime posting integration yet.

The accepted successor ontology stores one positive atomic monetary movement
as either internal-ledger to internal-ledger or internal-ledger to external
account. External accounts are genuine transaction sides with frozen reporting
classification, not duplicated sidecars beside a complete control-ledger
posting. Compound events are ordered batches. Conventional debit/credit lines,
statements, and financial reports are projections over that single truth.
K0-K3 proved scenarios, balanced reports without double-counting, historical
classification, authorization, idempotency, periods, currency conversion, and
append-only correction. Do not infer cutover or migrate DEA data from the ADR's
acceptance; persistence design and a later explicit runtime transition remain
separate stages.

K4 added the accepted relational mapping in
`docs/implementation/standalone-accounting-persistence-design.md`. K5.1 then
registered the tenant app and introduced organization/book, period, and ledger
master persistence. The mapping requires one atomic transaction row through draft
and posted lifecycle; a future posting batch will make it immutable rather than
copying it into a second ledger table.

K5.2 adds external accounts and immutable effective-dated classification core.
Each account is book-owned and identifies a Party through an adapter key plus
accounting purpose; no Rokkad Party dependency exists. Classifications map the
external side to one same-book posting ledger and freeze reporting class/normal
side by version.

K5.3 adds voucher headers and complete draft atomic transactions. Every common
transaction row has exactly one ledger-to-ledger or ledger-to-external-account
subtype; the database defers that exact-cardinality check until the atomic write
boundary. Account transactions retain the classification version effective on
their voucher date. Authorization freezes voucher and transaction intent but
does not itself post it.

K5.4 adds the posting boundary. An authorized voucher is fingerprinted from its
frozen source, rule, currency, ledger, account, and classification facts and is
atomically paired with one immutable `TransactionBatch` in the unique covering
period. Ordinary vouchers require an open period; adjustment-only periods admit
only adjustment vouchers. Posted state cannot exist without exactly one batch,
and repeated posting returns that original evidence. This is side-by-side
persistence only: DEA remains the production runtime authority.

K5.5 implements append-only correction. A reversal is a newly posted adjustment
voucher linked to its original batch. Its atomic transactions appear in reverse
order with every side swapped while money, currency provenance, account identity,
and frozen classification remain identical. The database verifies that exact
relationship and permits only one reversal of a non-reversal batch. Correction
is the untouched original plus this compensating batch plus a newly authorized
replacement, grouped for explanation; it never rewrites historical truth.

K5.6 persists settlement explanation without adding money. A posted external-
account transaction may originate one open item that freezes its exact account
and transaction/base amounts. A posted opposite-side transaction on the same
book/account can allocate some or all of that item. Capacity is checked against
both settlement and item under locks, allocation rows are immutable, and
outstanding is derived. Reversal of settlement allocation still requires future
compensating allocation evidence; existing rows must never be edited or deleted.

K5.7 closes that lifecycle gap. Reversing a settlement creates an exact
compensating allocation linked to the original allocation and the financial
reversal transaction. Outstanding subtracts compensations from original
allocations. This is explanation only and introduces no new monetary effect.

K5.8 connects persisted posted truth to the proven report projections without
storing balances. It exposes two conventional lines per atomic transaction,
separate internal and external statements, a combined balanced trial balance,
P&L, balance sheet, and frozen-classification reconciliation. Draft and
authorized intent is excluded. This completes the intended persisted MVP kernel
proof; it does not authorize runtime cutover from DEA.

K6 accountant evidence distinguishes an open item's outstanding amount from an
external account's net balance. A settlement can be only partly allocated: a
customer receipt of INR 600 with INR 400 allocated leaves INR 600 outstanding
on a INR 1,000 invoice, INR 200 unapplied customer credit, and INR 400 net
receivable. `posted_unapplied_settlements` exposes that unused settlement
capacity without creating or changing any financial entry.

K7 period operations are explicit accounting events rather than ordinary model
edits. Open periods may move to adjustment-only or closed; adjustment-only may
close; closed may reopen only to adjustment-only with a reason or become locked;
locked is terminal. Each transition carries immutable actor/time evidence. The
MVP bootstrap deliberately creates only the primary INR book, one period, and
Cash, Accounts Receivable, and Sales ledgers.

The K7 MVP integration vocabulary is deliberately limited to versioned cash
sale, credit sale, and customer receipt events. Source identity is not the
voucher number. Exact delivery replay returns the original posted result;
reusing that identity with different monetary or classification input is an
error, and failed attempts leave operational evidence but no partial voucher.

## Visual Workflow Modes

The K8 visual MVP has two explicit modes. `OWNER` is the KISS default: one real
workspace Owner confirmation moves a voucher through draft, authorization, and
immutable posting while recording the same truthful actor at each stage.
`TEAM` retains separate maker, authorizer, and poster actions. The owner mode is
an audited segregation-of-duties waiver, not impersonation. Credit-sale or
receipt entry may create a standalone customer receivable/classification
inline. New visual accounts link directly to the existing tenant `Party`; the
external account still owns the accounting purpose and balance.

Posted transactions are never unposted. The visual workflow creates a linked
opposite reversal voucher. Owner mode permits the actual Owner to reverse their
own posting with explicit date, reason, and confirmation; Team mode retains the
different-user rule. A reversed credit-sale open item reports zero outstanding,
cannot accept new allocations, and an already allocated invoice requires its
receipts to be reversed first.

## Boundary

- Operational apps create business documents and durable accounting intent.
  A workspace in `DEA` mode requests effects through the DEA facade; a
  workspace in `DEFERRED` mode retains pending source evidence only.
- Canonical Loans balance and lifecycle readiness treat an intact `PENDING`
  outbox as expected, non-blocking evidence in `DEFERRED` mode. Missing,
  `FAILED`, or `PROCESSING` delivery evidence still fails closed. In `DEA`
  mode, every non-posted outbox remains a blocker.
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
- Reconciliation requires itemized full-release and renewal events to match their immutable opening/closing lines, while preserving historical aggregate and partial-release compatibility. Composite renewal reversal restores each source collateral item's prior custody from its own renewal event. Operational reports and verification PDFs expose the source/successor relationship, collateral movement, and item-principal evidence needed to explain the correction trail.
- Auction item-principal allocation is a named post-MVP obligation in roadmap E7.3A.8. Loans auction operations must remain outside the limited pilot until recovery proceeds can be allocated deterministically to immutable item lines, reconciled to pre-auction tranche balances and the aggregate recovery, reversed through compensating evidence, and exposed in reports and recovery documents. Existing aggregate auction history must not be assigned invented item allocations.

## BusinessDoc Classification

A business event is any business fact that may have accounting meaning, such as cash paid, cash received, an expense incurred, interest accrued, a loan released, stock moved, or a period closed.

Not every business event should become a DEA `BusinessDoc` model. A model should be a business document when it represents one accounting-relevant fact with a clear effective date, economic payload, voucher type, audit identity, and idempotency fingerprint. If the object is a long-lived domain aggregate with many lifecycle events, each accounting event should be posted separately through a document or event payload.

For example, Girvi `GivenLoan` is a loan aggregate, not one accounting document. Its disbursal, repayment, release, auction, sale, and interest accrual events are the accounting-relevant facts. Those events may produce `PaymentVoucher`, `JournalEntryVoucher`, or event payloads that DEA translates into `Voucher`, `VoucherLine`, and immutable `JournalEntry` records.

## Current Concerns

- Ensure every external caller uses the facade instead of models/posting internals.
- Revisit voucher uniqueness constraints if event-driven Girvi needs multiple vouchers against one loan/document.
- Keep fingerprint behavior consistent: nullable until posting or assigned when drafts are created.

Archived DEA sources are preserved in [archive/dea](../archive/dea/).
