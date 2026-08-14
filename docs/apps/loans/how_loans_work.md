---
status: active
owner: loans
updated: 2026-08-04
tags: [loans, architecture, models, workflows]
related: [architecture-and-girvi-parity.md, ../../plans/loans-rewrite-roadmap.md]
---

# How Loans Works

The Loans app is built around one principle: `PawnLoan` is the aggregate identity, while financial truth is reconstructed from immutable events rather than mutable balance columns.

## 1. Model structure

The main hierarchy is defined in `apps/tenant_apps/loans/models/core.py`:

```text
Workspace
└── LoanLicense
    └── LoanSeries
        ├── Pawn-loan number sequence
        ├── Release-number sequence
        └── PawnLoan
            ├── PawnCollateralItem[]
            ├── PawnLoanApprovalSnapshot[]
            ├── LoanPolicySnapshot
            ├── LoanChangeLog[]
            ├── PawnLoanAccountingEvent[]
            │   └── PawnLoanAccountingOutbox
            ├── PawnLoanInterestAccrual[]
            └── PawnLoanRelease[]
                ├── PawnLoanReleaseItem[]
                ├── PawnCollateralCustodyEvent[]
                └── PawnLoanReleaseReversal
```

`PawnLoanNotice[]` also belongs to the PawnLoan aggregate as durable notice
intent. It snapshots the recipient and loan amounts, then references a Notify
v2 event/job. Delivery status, attempts, provider references, and failures are
read from Notify rather than duplicated in Loans.

### Regulatory setup

`LoanLicense` represents the legal lending licence for one workspace. It has issuance and expiry dates, activation state and tenant ownership.

`LoanSeries` belongs to a licence. A licence may contain multiple series.

`LoanNumberSequence` stores independent counters for:

- Pawn-loan numbers
- Release numbers

The sequence is locked during allocation, has a maximum number, and does not recycle committed numbers.

### PawnLoan

`PawnLoan` is the main record in `models/core.py`. It stores:

- Workspace, licence and series
- Borrower as a `Party`
- Permanent loan number
- Original principal and monthly interest rate
- Loan date and tenure
- A small stored lifecycle state

It deliberately does not store fields such as:

- Current principal balance
- Interest outstanding
- Total due
- Amount repaid
- Overdue status
- Closure readiness

Those are calculated from events so they cannot drift away from transaction history.

The stored lifecycle is:

```text
DRAFT ──→ APPROVED ──→ ACTIVE ──→ CLOSED
  │           │
  └───────────┴──────→ CANCELLED

APPROVED ──→ DRAFT  (reopen for correction)
```

The allowed transitions are defined independently from Django in `domain/vocabulary.py`.

Conditions such as `OVERDUE`, `PARTIALLY_PAID`, `ACCOUNTING_FAILED` and `CLOSURE_READY` are derived states, not database states.

### Collateral

`PawnCollateralItem` in `models/core.py` stores:

- Metal
- Gross and net weight
- Purity percentage
- Latest appraisal
- Current custody state

Its current `custody_state` is a convenient projection. The complete movement history is separately preserved through `PawnCollateralCustodyEvent`.

### Snapshots and audit history

Three records preserve different kinds of history:

- `PawnLoanApprovalSnapshot` freezes the approved borrower, economics and collateral payload.
- `LoanPolicySnapshot` captures the calculation policy used after disbursement.
- `LoanChangeLog` records operational actions such as creation, approval, repayment, release and reversal.

Approval snapshots cannot be edited or deleted through normal model methods.

## 2. Creating a loan

The UI does not directly save a `PawnLoan`. The view builds a command and calls `create_pawn_draft()` in `services/pawn_drafts.py`.

Inside one database transaction, the service:

1. Confirms an active tenant workspace.
2. Loads an active borrower `Party`.
3. Confirms the licence and series belong to that workspace.
4. Checks that the series can issue a new number.
5. Validates loan economics and every collateral item.
6. Locks and consumes the next official number.
7. Creates the `PawnLoan`.
8. Creates its collateral.
9. Writes a `DRAFT_CREATED` change log.

If any step fails, the transaction rolls back—including the number allocation.

Only draft loans can be edited. Draft editing replaces the collateral collection and records before/after audit data.

## 3. Approval

`approve_pawn_loan()` in `services/pawn_lifecycle.py`:

1. Locks the loan row.
2. Confirms `DRAFT → APPROVED` is allowed.
3. Revalidates the licence, series, loan and collateral.
4. Produces a canonical JSON payload.
5. Hashes that payload.
6. Stores an immutable, versioned approval snapshot.
7. Changes the loan to `APPROVED`.
8. Adds an audit record.

If corrections are needed, the loan is reopened to draft with a mandatory reason. Reapproval creates another snapshot version instead of overwriting the earlier approval.

## 4. Disbursement and accounting

Disbursement is implemented in `services/pawn_disbursal.py`.

Before disbursement, Loans asks DEA whether accounting is ready:

- Open accounting period
- Cash funding ledger
- Principal control ledger
- Borrower control ledger
- Borrower receivable account mapping
- Interest income ledger
- Conditional fee and interest-receivable ledgers

These checks are in `services/accounting_readiness.py`.

Then one atomic transaction creates:

```text
LoanPolicySnapshot
PawnLoanAccountingEvent(DISBURSAL)
PawnLoanAccountingOutbox(PENDING)
LoanChangeLog(DISBURSED)
PawnLoan.state = ACTIVE
```

After the transaction commits, the outbox attempts delivery to DEA.

The outbox workflow is in `services/accounting_outbox.py`. It provides:

- Deterministic payload fingerprints
- Deterministic idempotency keys
- Once-only source intent
- Attempt tracking
- Durable failure information
- Safe retries

DEA receives the event through its public facade in `integrations/dea_delivery.py`. DEA—not Loans—creates vouchers and journal entries.

If posting fails, the loan event is not erased. The outbox becomes `FAILED`, and later financial actions are blocked until posting succeeds.

One current limitation: the policy model supports workspace defaults and licence overrides, but disbursement currently calls `resolve_policy()` without persisted workspace/licence inputs. Therefore the live snapshot currently uses the domain defaults. Connecting admin-configurable policies is still needed.

## 5. How balances work

Balances are calculated by folding accounting events in `selectors/balances.py`.

Conceptually:

```text
Principal outstanding
  = disbursed principal
  + capitalized interest
  - principal payments

Interest outstanding
  = accrued interest
  - capitalized interest
  - interest payments

Total due
  = principal outstanding
  + interest outstanding
  + fees outstanding
```

A reversal applies the original event with a negative multiplier.

This means the `principal_amount` on `PawnLoan` remains the original contract amount. It is not mutated every time money is received.

Closure readiness is derived as:

```text
total due == 0
AND
every collateral item is WITH_CUSTOMER
```

Financial settlement alone does not close a loan.

## 6. Repayments

Repayments are handled by `services/pawn_repayment.py`.

The service:

1. Locks the active loan.
2. Rejects unresolved accounting events.
3. Calculates the current balance.
4. Allocates payment in this fixed order:
   - Fees
   - Overdue interest
   - Current interest
   - Principal
5. Rejects overpayment.
6. Records a repayment accounting event and outbox.
7. Writes the operational audit record.

A caller-generated `request_key` protects against accidental double submission. Repeating the same key and amount returns the existing repayment; reusing the key with another amount is rejected.

## 7. Interest

Interest is handled in `services/pawn_interest.py`.

The service previews monthly periods using the disbursal policy snapshot. It retains high-precision calculation values but stores currency-rounded finalized accrual rows.

Each finalized period records:

- Period number and dates
- Full or partial-period fraction
- Calculation base
- Unrounded interest
- Recognized rounded interest
- Accounting event, when applicable

For compound loans, unpaid interest can be explicitly capitalized at the configured boundary. It does not silently mutate principal.

With cash accounting, accrual events may be operational-only. With accrual accounting, DEA posts interest receivable and income.

## 8. Release and collateral return

Full and partial releases are handled in `services/pawn_release.py`.

Before release, the system:

1. Requires completed monthly accruals to be finalized.
2. Calculates any current partial-period interest.
3. Values the collateral.
4. Calculates the exact required settlement.
5. Checks accounting readiness.
6. Allocates a permanent release number.

For partial release, it also ensures the remaining principal stays within the configured LTV against retained collateral.

A release transaction creates:

- `PawnLoanRelease`
- `PawnLoanReleaseItem` for each returned item
- Valuation snapshots
- `PawnCollateralCustodyEvent`
- Release accounting event and outbox
- Change-log entry

A full release returns every item and changes the loan to `CLOSED`. A partial release keeps it `ACTIVE`.

## 9. Reversals

Posted events are never edited. Reversal is handled by `services/pawn_reversal.py`.

Rules include:

- Administrator only
- Mandatory reason
- Original event must already be posted
- Later dependent events must be reversed first
- A new compensating event is created
- DEA reverses the accounting
- Original records remain unchanged

Reversing a full release restores collateral custody and reopens the loan. Reversing disbursement returns the loan from `ACTIVE` to `APPROVED`.

## 10. UI architecture

The views in `apps/tenant_apps/loans/views.py` are intentionally thin:

```text
HTTP request
→ validate form
→ call service command
→ service locks and validates
→ models/events/outbox persist
→ selector derives the new state
→ template renders the result
```

Views do not contain posting logic, interest calculations or balance mutation logic.

In short, `core.py` defines the durable facts; services control legal changes; selectors reconstruct the current truth; the outbox safely connects Loans to DEA; and views coordinate user interaction.
