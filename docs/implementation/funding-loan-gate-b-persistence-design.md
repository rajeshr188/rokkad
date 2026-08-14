---
status: historical
owner: project
updated: 2026-08-08
tags: [loans, funding-loan, persistence, application, concurrency]
related:
  - ../plans/loans-girvi-consolidation-fit-gap.md
  - ../adr/2026-08-08-loans-consolidation-and-girvi-retirement-evaluation.md
  - ../constitution.md
---

# FundingLoan Gate B Persistence And Application Design

> Historical implementation design. FundingLoan is now a supported runtime
> workflow under `../adr/2026-08-13-loan-application-boundaries-and-monitoring.md`.
> Statements below that describe it as a disabled prototype record the staged
> delivery boundary at the time and are not current product policy.

## Purpose

Define the tenant persistence, constraints, transaction boundaries, ports, and
migration checks for the Gate B FundingLoan prototype. This design derives from
the completed pure contract in `loans.domain.future_funding`.

This document authorizes a later model/application prototype only after review.
It does not enable FundingLoan runtime support, add routes, connect accounting,
or change Girvi ownership.

## Aggregate Boundary

`FundingLoan` is independent from `PawnLoan`:

- lender is `party.Party`;
- economic terms and event history belong to FundingLoan;
- collateral remains owned by its originating PawnLoan;
- `FundingPledgeItem` references existing `PawnCollateralItem` rows;
- FundingLoan never reads PawnLoan financial events to calculate its balance;
- borrower release, renewal, and recovery read projected collateral custody and
  active pledge availability only.

## Persistence Model

### FundingLoan

| Field | Contract |
| --- | --- |
| `workspace` | Protected FK to `orgs.Company`; explicit tenant ownership. |
| `lender` | Protected FK to `party.Party`; must belong to the active workspace. |
| `funding_number` | Workspace-unique, allocated through a locked workspace sequence. |
| `state` | `DRAFT`, `ACTIVE`, `SETTLEMENT_PENDING`, `CLOSED`, `CANCELLED`. |
| `created_at`, `updated_at` | Audit timestamps. |
| `created_by`, `updated_by` | Nullable protected actor evidence. |

The aggregate row stores identity and the durable lifecycle milestone only. It
does not store mutable principal, interest, fee, balance, pledged weight, or
current collateral value totals.

Constraints and indexes:

- unique `(workspace, funding_number)`;
- index `(workspace, state, created_at)`;
- index `(lender, state)`;
- database trigger rejects workspace changes and illegal state transitions;
- terminal rows cannot return to an open state.

### FundingLoanTermsSnapshot

One-to-one protected relation to FundingLoan, created only at activation:

- principal amount;
- monthly interest rate;
- activation and maturity dates;
- maximum funding LTV ratio;
- currency quantum;
- schema version and deterministic fingerprint;
- creator and timestamp.

Checks enforce positive principal/quantum, nonnegative rate, maturity on or
after activation, and LTV in `(0, 1]`. An append-only trigger blocks update and
delete. Activation requires exactly one terms snapshot.

### FundingLoanEvent

Immutable operational financial evidence, not an accounting event:

| Field | Contract |
| --- | --- |
| `funding_loan` | Protected owner FK. |
| `sequence` | Positive, unique per FundingLoan. |
| `event_kind` | Activation, interest accrual, fee assessment, repayment, reversal. |
| `effective_date` | Business date. |
| `principal_amount` | Nonnegative currency amount. |
| `interest_amount` | Nonnegative currency amount. |
| `fee_amount` | Nonnegative currency amount. |
| `operation` | Stable command family used to scope idempotency. |
| `request_key` | Caller-supplied idempotency key. |
| `request_fingerprint` | Hash of canonical operation input. |
| `reversal_of` | Protected one-to-one self-reference for reversals only. |
| `reason` | Required for reversal; blank otherwise. |
| `actor`, `created_at` | Immutable audit evidence. |

Constraints and triggers:

- unique `(funding_loan, sequence)`;
- unique `(funding_loan, operation, request_key)`;
- reversal link exactly when kind is `REVERSAL`;
- exactly one reversal per original through the one-to-one relation;
- kind-specific amount shape from the pure contract;
- reversal amounts exactly match the original;
- newest-first reversal based on active event sequence;
- event workspace is inherited through FundingLoan, never duplicated;
- update/delete prohibited for every row.

Indexes support `(funding_loan, effective_date, sequence)` and
`(funding_loan, event_kind, sequence)`.

### FundingPledge

Immutable pledge header created during activation:

- protected FundingLoan FK;
- workspace, effective date, request key and request fingerprint;
- total collateral value and maximum funded amount snapshots;
- valuation method/version and structured evidence snapshot;
- actor and timestamp;
- optional one-to-one compensating `FundingPledgeReversal` later in Gate B.

The workspace and FundingLoan must agree. One activation pledge is allowed per
FundingLoan in the prototype. Header and item snapshots are append-only.

### FundingPledgeItem

One row per selected PawnCollateralItem:

- protected FundingPledge FK;
- protected PawnCollateralItem FK;
- source PawnLoan ID snapshot for audit/query convenience;
- appraised/calculated/selected collateral value snapshots;
- valuation inputs and fingerprint;
- `released_at` nullable projection of active pledge membership.

Constraints and database guards:

- unique `(funding_pledge, collateral_item)`;
- partial unique constraint on `collateral_item` where `released_at IS NULL`;
- positive selected value;
- source PawnLoan must equal `collateral_item.loan_id`;
- PawnLoan, collateral, FundingLoan, and pledge workspace must agree;
- the PawnLoan must be active and collateral must be in the vault at pledge;
- only the return/correction command may set `released_at`, once;
- no delete; core snapshot fields are immutable.

The partial unique constraint is the final concurrent double-pledge authority.
Application checks provide useful errors but are not sufficient.

### FundingCustodyEvent

Extend `PawnCollateralCustodyEvent` rather than create a competing custody
stream. Add nullable protected base-workflow sources for FundingPledge and
FundingReturn plus nullable correction-provenance sources for their reversals.
Update the existing constraint and `clean()` rules together.

Each row records item, from/to states, effective date, actor, timestamp, source,
and optional one-to-one `reversal_of`. Database guards enforce:

- exactly one base-workflow source across release, auction, renewal, funding
  pledge, and funding return;
- zero correction-provenance sources for an original movement, or exactly one
  correction-provenance source that matches the base workflow for a reversal;
- existing release/auction/renewal reversal rows remain valid because they keep
  the base workflow source and add their matching correction source;
- source workspace and collateral workspace agreement;
- `from_state <> to_state`;
- a movement starts at the collateral row's current projected state;
- the collateral row projection changes to `to_state` in the same transaction;
- a reversal exactly inverts one unreversed movement;
- later active movements for that item must be reversed first;
- custody events are append-only.

### FundingReturn

Immutable header for one partial or full lender return:

- FundingLoan, workspace, effective date, request key/fingerprint;
- retained collateral value and principal/LTV snapshots;
- actor and timestamp.

`FundingReturnItem` uniquely links returned pledge items. A full return requires
zero principal. A partial return requires retained collateral to cover current
principal under the terms snapshot LTV. Returning an item sets its pledge-item
`released_at` projection and appends lender-to-vault custody evidence atomically.

### FundingLoanSequence

One row per workspace with `next_value`, configurable prefix, width, and
optional maximum. Allocation uses `SELECT ... FOR UPDATE`; numbers never recycle
or wrap. This is separate from regulatory PawnLoan license/series numbering.

## Application Contracts

### Commands

- `CreateFundingLoanDraft`
- `CancelFundingLoanDraft`
- `ActivateFundingLoan`
- `AccrueFundingInterest`
- `AssessFundingFee`
- `RecordFundingRepayment`
- `BeginFundingSettlement`
- `ReturnFundingCollateral`
- `CloseFundingLoan`
- `ReopenFundingSettlement`
- `ReverseFundingEvent`
- `ReverseFundingCustodyMovement`

Every command includes `workspace_id`, actor, and request key where it creates
immutable evidence. Commands carry IDs and value objects, not ORM instances.

### Repository Ports

The application layer depends on protocols:

```text
FundingLoanRepository
  lock_loan(workspace_id, funding_loan_id)
  allocate_number(workspace_id)
  load_event_history(funding_loan_id)
  append_event(...)
  save_state(...)

FundingCollateralRepository
  lock_candidates(workspace_id, collateral_item_ids)
  load_active_pledges(collateral_item_ids)
  append_custody_events(...)
  set_projected_custody(...)

FundingPledgeRepository
  create_pledge(...)
  lock_active_items(funding_loan_id)
  record_return(...)
```

ORM implementations live under infrastructure/persistence. Pure handlers call
Gate A policies and do not import DEA, standalone accounting, views, or forms.

### Outbound Ports

```text
FundingAccountingPort.record(events) -> delivery references
FundingDocumentPort.issue(source) -> document reference
FundingNotificationPort.enqueue(source) -> notification reference
Clock.today() -> date
```

Gate B uses `NullFundingAccountingAdapter`, which records no accounting rows and
always returns an operational-only receipt. It cannot inspect accounting setup.
Document and notification adapters are also null in Gate B.

Accounting delivery rows are not part of the Gate B migration. They belong to
Gate E after the operational vertical slice passes.

## Handler Transaction Boundaries

All write handlers use one `transaction.atomic()` and this lock order:

1. workspace FundingLoanSequence when allocating a number;
2. FundingLoan row;
3. PawnLoan rows sorted by primary key;
4. PawnCollateralItem rows sorted by primary key;
5. active FundingPledgeItem rows sorted by collateral ID;
6. FundingLoanEvent rows when validating sequence/reversal order.

Never lock these sets in request order. Stable ordering prevents deadlocks.

Activation performs, in one transaction:

1. lock FundingLoan and selected PawnLoan/collateral rows;
2. verify tenant, active PawnLoans, vault custody, and no active pledge;
3. build validated terms and pledge plans through Gate A policies;
4. create terms snapshot, activation event, pledge header/items;
5. append vault-to-lender custody events and update custody projections;
6. move FundingLoan to active;
7. invoke the null accounting port after persistence but before commit only if
   it is guaranteed side-effect free. Real adapters later use after-commit
   delivery from a separate outbox.

Database partial uniqueness resolves simultaneous activation races. Convert its
`IntegrityError` into the stable “collateral already pledged” application error.

## Idempotency

Each command request key is scoped to its aggregate and explicit operation
value. The database key is `(funding_loan, operation, request_key)`. The stored
fingerprint includes all economic values, dates, selected collateral IDs,
valuations, and correction reason. Replay with the same fingerprint returns the
existing result. Reuse with changed input fails.

Do not derive the key solely from mutable payload JSON or accounting identity.
No accounting voucher ID participates in operational idempotency.

## PostgreSQL Enforcement

Use Django constraints for row-local rules and reversible `RunSQL` functions/
triggers for cross-row or cross-table invariants. Trigger functions must be
schema-local, narrowly named, and dropped in reverse migration SQL.

Required trigger families:

1. immutable FundingLoan terms, events, pledge snapshots, custody events, and
   return evidence;
2. FundingLoan state transition guard;
3. event reversal exactness and newest-first ordering;
4. pledge item source/workspace/active-PawnLoan/custody agreement;
5. custody source agreement, current-state continuity, exact reversal, and
   projected-state synchronization.

Do not place query-critical amounts or status inside JSON. JSON snapshots are
for explanatory valuation evidence and versioned source context only.

## Migration Plan

The first Gate B migration depends on `loans.0018_official_issue_uniqueness` and
the current Party/Orgs migrations. It is additive and tenant-scoped.

Recommended sequence:

1. Add FundingLoan, sequence, terms, event, pledge, pledge-item, return, and
   return-item tables plus nullable funding sources on custody events.
2. Add row-local checks, unique constraints, partial unique active-pledge
   constraint, and indexes.
3. Replace the custody base-source/correction-provenance constraint and update
  `PawnCollateralCustodyEvent.clean()` in the same code/migration slice. Add
  regression tests for existing release, auction, and renewal reversal rows.
4. Install cross-table and append-only PostgreSQL guards with reversible SQL.
5. Add no data migration and seed no FundingLoan rows.
6. Keep `FUNDING_LOAN_RUNTIME_SUPPORTED = False`.

Apply only with `migrate_schemas --tenant`; never plain `migrate` as project
deployment guidance.

## Migration Review Checklist

- SQL contains only additive Loans changes and the deliberate custody-source
  constraint replacement.
- No Girvi table, migration, route, or record is touched.
- No DEA or standalone accounting FK exists.
- Every FK deletion behavior is `PROTECT` except nullable actor `SET_NULL`.
- Partial active-pledge uniqueness is present in generated SQL.
- Trigger reverse SQL removes every function/trigger cleanly.
- Fresh tenant replay succeeds from zero.
- Existing tenant migration succeeds with no FundingLoan seed rows.
- Migration rollback restores the pre-Gate-B custody source constraint.
- Django model validation and database enforcement accept/reject the same
  custody source combinations.
- `makemigrations loans --check --dry-run` is clean after generation.

## Gate B Test Matrix

Before Gate B can complete:

- model checks and trigger bypass tests;
- request-key exact replay and changed-payload rejection;
- two-connection concurrent double-pledge test with one winner;
- deterministic lock-order coverage across reversed input ID order;
- tenant/workspace mismatch rejection at service and database boundaries;
- atomic rollback of loan, terms, event, pledge, items, custody, and projection;
- independent funding balance/repayment/closure repository tests;
- borrower release, renewal, and recovery blocked by lender custody;
- newest-first financial and per-item custody reversal tests;
- existing release, auction, and renewal custody reversal regression tests;
- complete lifecycle through application handlers with null adapters;
- fresh and existing tenant migration replay.

## Review Verdict

The persistence design preserves the successful Gate A boundary. FundingLoan
remains a separate aggregate, collateral ownership remains with PawnLoan, and
accounting is absent from operational truth. Gate B implementation may proceed
in small slices, starting with schema and database guard tests. Runtime support
must remain false until the full Gate B matrix passes.

## Implementation Outcome

Gate B completed on 2026-08-08. Additive tenant migrations `loans.0019` through
`loans.0025` implement the accepted persistence boundary, including immutable
FundingPledge/FundingReturn reversal evidence and funding correction provenance
on the canonical Pawn collateral custody stream.

Application handlers now cover draft, activation, accrual, fee, repayment,
settlement, partial/full return, closure, exact newest-first financial event
reversal, pledge reversal, and return reversal. Corrections append immutable
evidence, exactly invert custody movements, synchronize pledge membership and
custody projections atomically, and remain operational-only through null
outbound adapters.

The final Gate B validation passes 40 FundingLoan domain, persistence,
application, concurrency, and registration tests plus the existing auction
custody reversal regression. Fresh tenant migration replay and Loans migration
drift checks pass. The unrelated DEA model drift warning remains outside this
work. `FUNDING_LOAN_RUNTIME_SUPPORTED` remains false; no route, UI, Girvi, or
accounting delivery was enabled.
