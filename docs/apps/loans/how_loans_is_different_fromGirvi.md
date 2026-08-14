---
status: active
owner: loans
updated: 2026-08-04
tags: [loans, girvi, architecture, comparison]
related: [architecture-and-girvi-parity.md, how_loans_work.md, ../girvi/architecture.md]
---

# How Loans Differs From Girvi

The core difference is that Girvi evolved as a broad operational application, while Loans was designed from the beginning as a smaller event-driven financial domain.

Girvi is feature-rich but carries several generations of architecture. Loans is stricter and easier to reason about, but currently implements fewer workflows.

## Architectural comparison

| Concern | Girvi | Loans |
|---|---|---|
| Primary models | `GivenLoan`, `TakenLoan`, legacy `Loan` compatibility | `PawnLoan`; future `FundingLoan` intentionally absent |
| Borrower identity | `Customer` plus a shadow `Party` link | Directly uses `Party` |
| Loan economics | Primarily stored across individual `LoanItem` rows | Principal and rate stored on `PawnLoan`; collateral stores physical/valuation facts |
| Lifecycle | Many stored operational states | Five stored states; overdue and partial payment are derived |
| Balance | Combines item amounts, accruals, DEA payments and compatibility sources | Deterministically folds immutable loan events |
| Accounting | Mixed synchronous DEA posting and newer outbox paths | Source event and outbox are foundational for every financial action |
| Mutation ownership | Models, services and some legacy views/helpers | Command services own writes |
| Policy | Often read from current workspace preferences | Frozen approval and disbursal snapshots |
| Release | Mature full-release, bulk and repledge-compatible workflow | Immutable full/partial release with valuation and LTV evidence |
| Reversal | Workflow-specific accounting reversal methods | Uniform newest-first compensating events |
| Tenant safety | Tenant schema is the main boundary | Tenant schema plus explicit workspace foreign keys and validation |
| Features | Broad operational feature set | Stronger PawnLoan core, smaller MVP scope |

## 1. Different domain shape

Girvi has two operational loan types:

- `GivenLoan`: money lent to a pawn borrower.
- `TakenLoan`: money borrowed from a lender against repledged collateral.

It also still carries deprecated models and compatibility aliases. The active models are in `apps/tenant_apps/girvi/models/loan_refactored.py`.

Loans deliberately separates these concepts:

- `PawnLoan` is implemented.
- `FundingLoan` is reserved for a future complete workflow.
- No incomplete FundingLoan database model or UI exists.

This prevents lender funding, borrower lending and collateral repledging from becoming one generic model full of conditional behavior.

## 2. Where the loan amount lives

In Girvi, each `LoanItem` contains:

- `loanamount`
- `interestrate`
- Calculated `interest`
- Weight and purity

The total loan principal is the sum of item-level loan amounts. See `apps/tenant_apps/girvi/models/loan_item.py`.

Conceptually:

```text
Girvi GivenLoan principal
= SUM(LoanItem.loanamount)
```

In Loans, `PawnLoan` itself owns:

- `principal_amount`
- `monthly_interest_rate`

Collateral contains only physical and valuation information:

- Gross and net weight
- Purity
- Metal
- Appraisal
- Custody

Conceptually:

```text
Loans PawnLoan
├── contractual principal and rate
└── collateral used to secure and value that principal
```

This is cleaner because adding or correcting an item description does not redefine where the contractual principal comes from.

## 3. Customer versus Party

Girvi originally used `contact.Customer`. It now has optional `borrower_party` and `lender_party` fields as migration bridges:

```text
GivenLoan.borrower       → Customer
GivenLoan.borrower_party → Party
```

Loans directly uses:

```text
PawnLoan.borrower → Party
```

That allows one person or business to act as customer, supplier, lender or another role without duplicating identity records.

There is still a compatibility bridge when DEA needs the older Customer-based account mapping, but Loans hides that behind its borrower-accounting setup service.

## 4. Lifecycle philosophy

Girvi stores detailed operational states such as:

- `ActiveCurrent`
- `ActiveOverdue`
- `ActiveNPA`
- `ClosurePending`
- `RenewalPending`
- `AuctionInitiated`
- `AuctionInProgress`
- `AuctionComplete`
- `Renewed`
- `WrittenOff`

These are defined in `apps/tenant_apps/girvi/models/loan_refactored.py`.

Loans stores only durable lifecycle milestones:

```text
DRAFT
APPROVED
ACTIVE
CANCELLED
CLOSED
```

Everything else is calculated:

- Overdue
- Partially paid
- Partially released
- Accounting pending
- Accounting failed
- Closure ready

This avoids a common inconsistency such as:

```text
loan.state = ACTIVE_OVERDUE
but calculated due = 0
```

In Loans, overdue is always derived from the effective date and current event-folded balance.

## 5. Where business logic lives

Girvi has improved substantially and now includes command-style services. But because it evolved over time, behavior still exists across:

- Model methods
- Services
- Lifecycle flows
- Transition registry
- Views
- Forms
- Compatibility helpers
- Signals

For example, `GivenLoan` still exposes model wrappers such as `create_payment()`, `create_disbursal_payment()`, `split_items()` and `merge_loans()`.

Loans models are intentionally less active. Views call a single workflow service:

```text
View
→ command/service
→ lock and validate
→ persist aggregate + event + audit
→ selector derives result
```

The goal is that there should be only one supported path for approving, disbursing, repaying or releasing a loan.

## 6. Balance calculation

Girvi’s balance must reconcile several sources accumulated over its history:

- Item-level loan amounts
- Current interest calculations
- Persistent accrual rows
- DEA `PaymentVoucher` records
- Legacy payment compatibility
- Release settlement snapshots
- Current preferences

Girvi selectors have stabilized much of this, but the read path still has to understand multiple representations.

Loans uses one economic event stream:

```text
DISBURSAL
+ INTEREST_ACCRUAL
+ INTEREST_CAPITALIZATION
- REPAYMENT
- RELEASE_RECEIPT
± REVERSAL
```

The balance selector folds these events to derive principal, interest, fees and total due. See `apps/tenant_apps/loans/selectors/balances.py`.

This gives Loans one explanation for every balance:

> The amount is ₹X because these specific events produced it.

## 7. Accounting delivery

Girvi’s newer code uses DEA facades and has a posting outbox, but accounting integration remains mixed. Some workflows post synchronously and some paths retain compatibility behavior.

For example, Girvi repayment generally attempts to create and post the DEA payment inside the repayment workflow. If posting fails, it reports that the payment was not recorded.

Loans treats accounting intent as a first-class domain fact:

```text
PawnLoanAccountingEvent
└── PawnLoanAccountingOutbox
```

The business event and outbox commit atomically. After commit, the outbox sends it to DEA.

If DEA fails:

- The loan event remains recorded.
- The outbox becomes `FAILED`.
- The error remains visible.
- Retry is idempotent.
- Later dependent financial actions are blocked.

This is an important philosophical difference:

```text
Girvi tendency:
Try to perform business action and accounting together.

Loans:
Commit business intent safely, then guarantee visible/retryable accounting delivery.
```

## 8. Policy behavior

Girvi typically reads operational preferences through its preference adapter. Therefore current workspace configuration can influence calculations and workflows.

Loans introduces two snapshots:

- Approval snapshot: what staff approved.
- Disbursal policy snapshot: what rules govern the active loan.

This prevents a later administrative preference change from silently altering an already-disbursed loan.

For example, changing maximum LTV from 80% to 70% should affect new loans, not rewrite the release terms of existing active loans.

A current Loans limitation is that the policy contracts support workspace defaults and licence overrides, but persisted admin-configurable values are not yet wired into disbursement. Current disbursals resolve the domain defaults before creating the snapshot.

## 9. Release and custody

Girvi has a mature release and custody system with:

- Full release
- Bulk release
- Repledging
- Return from lender
- Release catch-up interest
- Settlement compatibility
- TakenLoan collateral
- Storage and verification workflows

Its `Release` is primarily one-to-one with a `GivenLoan`. See `apps/tenant_apps/girvi/models/release.py`.

Loans supports multiple immutable releases per PawnLoan:

```text
PawnLoan
├── Partial release 1
├── Partial release 2
└── Full release
```

Each release records:

- Selected collateral items
- Item-by-item valuation evidence
- Calculated metal values
- Appraisals
- Retained collateral
- Maximum LTV
- Exact settlement allocation
- Custody transitions
- Accounting event
- Optional catch-up accrual

This makes partial release much more explicit. But Loans does not yet have Girvi’s repledging or FundingLoan workflow.

## 10. Reversals

Girvi has specific reversal helpers for disbursement, release, auction and sale. Its behavior varies by workflow and reflects compatibility requirements.

Loans has one general rule:

1. Only administrators can reverse.
2. A reason is mandatory.
3. The event must have posted successfully.
4. The newest unreversed event must be reversed first.
5. A compensating source event is created.
6. DEA creates the accounting reversal.
7. The original event is never edited.

Release reversal additionally restores physical custody through new custody events.

## 11. Audit and immutability

Girvi has audit history, accrual rows, custody history and posting evidence, but these were added gradually around existing models.

Loans designed those records together:

```text
Approved facts     → PawnLoanApprovalSnapshot
Active policy      → LoanPolicySnapshot
Business history   → LoanChangeLog
Financial intent   → PawnLoanAccountingEvent
Accounting delivery → PawnLoanAccountingOutbox
Interest periods   → PawnLoanInterestAccrual
Release evidence   → PawnLoanRelease
Custody history    → PawnCollateralCustodyEvent
Corrections        → Reversal records
Notice intent      → PawnLoanNotice (delivery state stays in Notify v2)
```

That gives the rewrite a more uniform audit model.

## 12. What Girvi still does that Loans does not

Girvi remains much broader. Loans currently lacks:

- FundingLoan/TakenLoan servicing
- Repledging
- Renewals
- Auction and recovery
- Auction notices (repayment, interest-due, overdue, and release-confirmation
  notices are implemented in E7.1)
- Customer portal integration
- Bulk release and bulk operations
- Loan split and merge
- Storage boxes
- Physical verification
- Collateral photographs
- Licence documents and renewal workflow
- Configurable printing frames
- Historical archives
- Several detailed exports

The complete parity register is in [architecture-and-girvi-parity.md](architecture-and-girvi-parity.md).

So the rewrite is not “Girvi with renamed models.” It trades Girvi’s broad feature coverage and compatibility history for a stricter foundation:

```text
Girvi:
mature + broad + compatibility-heavy

Loans:
smaller + explicit + event-driven + easier to audit
```

That is why existing Girvi loans remain in Girvi, while new development loans can originate in Loans without copying or dual-writing the same record.
