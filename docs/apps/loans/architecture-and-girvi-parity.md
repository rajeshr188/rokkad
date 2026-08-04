---
status: active
owner: loans
updated: 2026-08-04
tags: [loans, girvi, architecture, parity, mvp, cutover]
related: [../../adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, ../../plans/loans-rewrite-roadmap.md, ../girvi/architecture.md, ../girvi/workflows.md, ../../implementation/pawn-loan-mvp-operations-runbook.md]
---

# Loans Architecture And Girvi Parity Review

## Purpose

This document explains why the `loans` app was built beside `girvi`, how its
PawnLoan architecture works, what the rewrite improves, and which Girvi
features and workflows are still absent.

It is the durable parity register for the rewrite. The accepted architecture
decision remains the ADR. The execution order remains the loans rewrite
roadmap.

## Current Verdict

The Loans rewrite is a stronger foundation for new pawn loans. Its accounting,
audit, reversal, policy, custody, and tenant boundaries are explicit and tested.

It is not yet a complete Girvi replacement.

- The PawnLoan MVP lifecycle is implemented and passes the Phase 5 test gate.
- `jcl1` uses Loans as the development origination owner; production enablement
  still requires the full E6.4 sign-off.
- Girvi remains the write owner of existing Girvi loans.
- Phase 6 coexistence, comparison, gating, and development cutover are complete.
- E7.1 repayment, interest-due, overdue, and release-confirmation notices are
  implemented through Notify v2. E7.2 auction/recovery and E7.3 renewals are
  implemented. FundingLoan, repledging, and portal integration remain
  essential future workflows.
- Several Girvi operational conveniences need explicit carry-forward or
  rejection decisions before Girvi can be retired.

Girvi is not treated as wholly obsolete or poorly designed. It has been
stabilized with command services, lifecycle controls, custody history, DEA
integration, an outbox, reconciliation, and operational diagnostics. Its main
architectural burden is the breadth of production behavior and compatibility
history it must continue to carry.

## Why The Rewrite Is Side By Side

An in-place Girvi rewrite would combine three risky jobs:

1. Preserve and service existing production loans.
2. Replace legacy models and compatibility behavior.
3. Introduce a stricter domain and accounting design.

That would make rollback and record ownership ambiguous. The accepted model is:

- Girvi owns and services every loan created in Girvi.
- Loans owns every PawnLoan created in Loans.
- A record is never writable in both apps.
- Active Girvi loans are not copied into Loans as second writable records.
- Unified reads will combine both systems and label the owner.
- Mutating actions always return to the owning app.

Coexistence is therefore a supported product state, not a temporary data error.

## Why PawnLoan And FundingLoan Are Separate

Girvi supports both money lent to a pawn borrower and money borrowed from a
lender against repledged collateral. These workflows share some language, but
they have different parties, accounting, custody, servicing, and closure rules.

The rewrite therefore uses separate aggregates:

- `PawnLoan`: money lent to a borrower against pledged collateral.
- Future `FundingLoan`: money borrowed from a lender, potentially against items
  belonging to several PawnLoans.

They may share numbering helpers, documents, audit infrastructure, and adapter
patterns. They must not be collapsed into one generic `Loan` model.

FundingLoan is intentionally absent until a complete lender funding and
repledging vertical slice can be implemented. New-app collateral cannot be
repledged before that workflow exists.

## Architecture Comparison

| Concern | Girvi | Loans rewrite | Result |
| --- | --- | --- | --- |
| Domain shape | `GivenLoan`, `TakenLoan`, deprecated `Loan`, and compatibility aliases | Explicit `PawnLoan`; separate future `FundingLoan` | Clear aggregate meaning |
| Production responsibility | Broad current production owner | New-loan owner after feature-gated cutover | Safe coexistence |
| Mutation boundary | Newer services coexist with model helpers and legacy view paths | Services/commands own lifecycle mutations | Fewer mutation paths |
| Read boundary | Selectors exist, but older views and reports still carry calculations | Selectors own balances, readiness, reports, and diagnostics | One calculation source |
| Accounting boundary | Stabilized DEA facade and outbox paths coexist with historical integration | DEA facade, event contract, and durable outbox are foundational | Stronger posting isolation |
| Financial history | Operational fields and compatibility behavior coexist with posting history | Immutable source events plus compensating reversals | Auditable corrections |
| Policy | Preferences are read through compatibility adapters | Resolved economics are frozen in approval/disbursal snapshots | Active loans do not drift |
| Balance | Legacy aggregates and newer services coexist | Event-folded balance selector | Less mutable derived state |
| Release | Mature operational workflow, including bulk and lender custody | Immutable valuation, settlement, LTV, release, and custody evidence | Stronger release invariants |
| Documents | Configurable templates and frames | Fixed, source-linked MVP documents | Safer but less configurable |
| Rollout | Visible production workflow | Feature-hidden pending Phase 6 | Reversible launch |

## Loans Internal Layer Map

### Domain contracts

`apps/tenant_apps/loans/domain/` defines:

- PawnLoan lifecycle states and valid transitions.
- Derived operational states.
- Event, custody, document, posting, and reversal vocabulary.
- Workspace defaults and license overrides.
- Interest, partial-period, capitalization, valuation, LTV, recognition, and
  rounding policy contracts.
- Compatibility vocabulary for `GivenLoan -> PawnLoan` and
  `TakenLoan -> FundingLoan`.

These modules are database-free. They express rules before persistence or UI.

### Models

`apps/tenant_apps/loans/models/core.py` contains:

- `LoanLicense`
- `LoanSeries`
- `LoanNumberSequence`
- `PawnLoan`
- `PawnCollateralItem`
- `LoanPolicySnapshot`
- `LoanChangeLog`
- `PawnLoanApprovalSnapshot`
- `PawnLoanAccountingEvent`
- `PawnLoanAccountingOutbox`
- `PawnLoanInterestAccrual`
- `PawnLoanRelease`
- `PawnLoanReleaseItem`
- `PawnCollateralCustodyEvent`
- `PawnLoanReleaseReversal`
- `PawnLoanNotice` (intent and immutable delivery inputs; not provider status)

There is no runtime `FundingLoan` model.

### Services and commands

`apps/tenant_apps/loans/services/` owns writes and workflows:

- license and series setup,
- locked number allocation,
- draft create/edit,
- approval, reopening, cancellation, and license transfer,
- borrower accounting setup and readiness,
- disbursal,
- repayment allocation,
- interest preview, finalization, and capitalization,
- full and partial release,
- accounting and release reversals,
- accounting outbox delivery and retry,
- fixed source-document generation.

Views should coordinate requests and responses. They must not reproduce posting,
balance, release, or lifecycle rules.

### Selectors

`apps/tenant_apps/loans/selectors/` owns read models for:

- event-folded balances,
- release valuation and readiness,
- operational reports and reconciliation,
- outbox, sequence, accounting, reversal, and audit diagnostics.

This prevents different screens from calculating different balances or release
amounts.

### Integrations

`apps/tenant_apps/loans/integrations/` builds deterministic DEA payloads,
delivers durable accounting outbox events through the public DEA facade, and
adapts loan notice intent to Notify v2 jobs.

Loans does not own vouchers, journal entries, period locks, or accounting
reversal mechanics. DEA owns those responsibilities.

### UI

Current staff screens expose setup and the complete implemented PawnLoan
lifecycle under feature-hidden `/loans/setup/` and `/loans/internal/` routes.

The detail view presents the next valid action and surfaces setup, balance,
custody, accrual, release, posting, retry, and reversal state. Loans is not yet
the primary navigation target.

## PawnLoan Runtime Flow

### 1. Regulatory setup

A workspace can own several active regulatory licenses. Each license owns one
or more series. Each series has separate bounded sequences for PawnLoan and
release numbers.

Expiry blocks new drafts and disbursements under that license. Existing loans
remain linked to their original license and can still be serviced, released,
reversed, reported, and reprinted.

### 2. Draft and numbering

The draft service verifies tenant, Party, license, series, economics, and
collateral. It locks the relevant sequence row and allocates the official loan
number inside the same transaction.

Numbers allocate at draft creation. They never recycle or wrap. Sequence
exhaustion requires a different or new series.

### 3. Approval

Approval appends an immutable, versioned snapshot of the approved economics and
collateral. Reopening requires a reason. Any corrected loan must be approved
again, producing another snapshot instead of changing the old evidence.

### 4. Accounting readiness

Drafting is allowed before accounting is complete. Disbursal fails closed until
the effective date has:

- an open accounting period,
- a cash funding ledger,
- loan principal control accounts,
- a borrower loan-receivable account mapping,
- interest income accounts,
- applicable fee income accounts.

The guided borrower setup creates or reuses the current Party-to-Customer
compatibility bridge and the dedicated borrower receivable mapping. It creates
no accounting entry.

### 5. Disbursal

Disbursal locks the approved loan, rechecks regulatory and accounting setup,
freezes the resolved policy, moves the loan to active, and writes the accounting
event, outbox, and audit evidence atomically.

After commit, the adapter sends the event to DEA. DEA creates the source-linked
voucher and balanced immutable journal. Deterministic idempotency prevents
duplicate posting.

Failed delivery remains visible and retryable. Dependent financial actions are
blocked until delivery is resolved.

### 6. Balance and repayment

The canonical balance selector folds source events and reversals. It derives
principal, interest, fees, total due, overdue state, settlement, custody-aware
closure readiness, and posting blockers.

MVP repayments use the current business date and allocate in this order:

1. Fees and charges.
2. Overdue interest.
3. Current interest.
4. Principal.

Repayment does not release collateral. Backdating and staff split overrides are
deferred.

### 7. Interest and capitalization

The disbursal snapshot controls monthly rate, simple or compound calculation,
partial-month slabs, capitalization interval, cash or accrual recognition, and
currency rounding.

Calculations retain high precision. Finalized period rows store rounded currency
amounts and are immutable. Compound behavior requires an explicit
capitalization event at the configured boundary.

### 8. Valuation and partial release

Collateral valuation can use:

- current metal rate multiplied by net weight and purity,
- latest staff appraisal,
- the lower of both.

The release snapshot stores the actual rate, appraisal, weights, purity, method,
and selected/retained values used.

Partial release first clears fees and interest. It then reduces principal enough
to keep retained collateral within the snapshotted maximum LTV. Only selected
vault items move to the customer. The loan remains active.

### 9. Full release and closure

Full release performs catch-up accrual, requires the exact canonical settlement,
records the release and custody evidence, returns the remaining collateral, and
closes the loan.

Zero financial balance alone is not enough. Closure requires every collateral
item to have completed its return workflow.

### 10. Reversal

Posted history is never edited or deleted. An administrator must provide a
reason and reverse dependent events in reverse chronological order.

The original event remains immutable. Loans writes compensating domain evidence
and asks DEA to reverse the posted voucher. Release reversal also restores
custody only when the current physical state is compatible with the reversal.

### 11. Renewal

Renewal is not an in-place edit. It atomically closes one source PawnLoan and
activates one newly numbered successor while retaining the borrower, cloning
the immutable policy boundary, and linking each cloned collateral item to its
source item. Interest and fees settle fully. Pay-and-renew reduces carried
principal; top-up renewal increases it. The successor must remain within the
source snapshot's current valuation and maximum LTV.

DEA receives one `RENEWAL_SETTLEMENT` event for the real net cash movement:
the difference between source and successor control principal, plus interest
and fees collected. The successor `RENEWAL_OPENING` establishes its canonical
balance without inventing a second gross disbursal voucher and cannot deliver
before settlement. Reversal is a composite operation: it reverses the opening
and settlement newest-first, restores the source to active/in-vault, and marks
the successor cancelled with reversed lineage custody.

## Improvements Delivered By The Rewrite

1. Explicit PawnLoan and future FundingLoan aggregate ownership.
2. No dual-write or ambiguous active-loan migration.
3. Direct `Party` borrower relationship in the PawnLoan aggregate.
4. Services own commands; selectors own derived reads.
5. Immutable financial source events and source-linked accounting evidence.
6. Atomic event and durable outbox persistence.
7. Deterministic payload fingerprints and idempotency keys.
8. Visible, retryable posting failure with dependent-event blocking.
9. Immutable approval versions and disbursal policy snapshots.
10. Locked, bounded, non-recycling regulatory numbering.
11. Central event-folded balances instead of competing mutable totals.
12. Explicit high-precision accrual rows and capitalization events.
13. Cash and accrual accounting policies without bypassing DEA.
14. Mathematically enforced partial-release settlement and retained LTV.
15. Immutable release valuation and custody evidence.
16. Closure requiring both financial settlement and physical return.
17. Administrator-only, reason-required, newest-first reversals.
18. Tenant/workspace validation at service and model boundaries.
19. Source-to-outbox-to-DEA reconciliation and operations diagnostics.
20. Fixed, verification-linked tickets, receipts, and release memos.
21. Feature-hidden, reversible rollout rather than a big-bang replacement.

## Parity Register

Nothing in this register should disappear silently. An item must be implemented,
explicitly rejected with a product decision, or retained in Girvi until no
remaining business record depends on it.

### P0: Required before Loans becomes the default for new loans

| Capability | Girvi | Loans | Required work |
| --- | --- | --- | --- |
| Unified portfolio reads | Girvi public facade provides source-owned rows | Implemented in E6.1 | Maintain source-labelled combined reads |
| Cross-system comparison | Girvi reconciliation exists | E6.2 read-only source-to-unified comparison implemented with categorized text/JSON findings | Use as an E6.3/E6.4 pilot gate |
| Workspace enablement | Girvi remains default and services its records | E6.3 audited workspace flag, canonical route switch, reversible navigation, and direct Girvi origination guard implemented | Exercise through the E6.4 pilot checklist |
| Pilot hardening | Production workflow exists | E6.4 fail-closed automated readiness gate implemented; `jcl1` automated checks pass | Complete target backup, rollback, support, monitoring, permission, and real-workflow sign-offs |
| Primary new-loan route | Girvi | Not enabled | E6.5 selected-workspace cutover |

### P1: Essential business workflows after the PawnLoan MVP

| Capability | Current Girvi behavior | Loans gap |
| --- | --- | --- |
| Funding loans | `TakenLoan`, lender repayment, lender statements | No `FundingLoan` aggregate or payable accounting |
| Repledging | Select collateral, create lender loan, track lender custody and return | Deliberately blocked until FundingLoan exists |
| Renewal | Pay-and-renew and successor loan behavior | Implemented with immutable source/successor audit and collateral lineage |
| Top-up renewal | Existing operational renewal path | Implemented with current valuation/LTV enforcement and net DEA cash posting |
| Notices | Reminder, overdue, interest, auction, and release notification paths | Repayment, interest-due, overdue, release-confirmation, and auction-source notices implemented through Notify v2 |
| Auction/recovery | Auction lifecycle and accounting/recovery posting | Initiate/start/cancel/complete/reverse, custody evidence, PDFs, and DEA exact-debt recovery implemented; shortfall write-off and borrower-surplus settlement remain deferred |
| Customer portal | Girvi/Party loan visibility can be exposed through existing portal work | New Loans statements, receipts, notices, and releases are not integrated |

### P2: Girvi operational capabilities requiring carry-forward decisions

These are not automatic cutover blockers. Each must be validated with real
users before Girvi retirement.

| Capability | Girvi support | Loans status |
| --- | --- | --- |
| Bulk release | Bulk release forms and execution | Missing |
| Bulk loan operations | Existing operational helpers | Missing |
| Loan split and merge | Item split and loan merge workflows | Missing |
| Storage boxes | Box ranges, assignment, detail, and CRUD | Missing |
| Physical verification | `Statement` and discrepancy items | Missing |
| Collateral photographs | Item picture upload and display | Missing |
| Collateral labels | Label and loan printing | Missing beyond fixed loan documents |
| License documents | Upload and delete regulatory documents | Missing |
| License renewal | Renewal dates, notes, and expiry reporting | Missing |
| Configurable printing | Templates, frames, clone/default/test print/download pack | Loans has fixed PDFs only |
| Historical archives | Year/month/week/day archive browsing | Missing |
| Detailed exports | Girvi Excel, PDF, ledger, inventory audit, series/license reports | Loans has MVP operational reports only |
| Verification and custody reports | Repledge and physical inventory reports | Only PawnLoan custody/reconciliation reports exist |

### P3: Accepted policy and authorization extensions

| Capability | Current boundary |
| --- | --- |
| Repayment backdating | MVP accepts current business date only |
| Staff allocation override | MVP uses fixed fees/interest/principal order |
| Staff-to-license restriction | Desired future behavior; not enforced in MVP |
| Branch-scoped licenses | Requires a later authorization and tenancy decision |
| Configurable regulatory document variants | Fixed MVP PDFs only |
| Configurable disbursal deductions | Girvi has broader deduction behavior; no equivalent first-class PawnLoan workflow is confirmed |

## Current Architecture Risks And Debt

### Party and Customer bridge

PawnLoan correctly uses Party, but DEA account compatibility still requires a
Customer bridge in the current schema. Guided setup hides this from operators;
it does not remove the underlying compatibility dependency.

### Controlled UI and limited live usage

The lifecycle is test-complete and workspace-gated but has not yet received
broad production usage. E6.4 must validate usability, setup, accounting error
recovery, staff understanding, rollback, and support response with a real pilot
workflow.

### Fixed document formats

Fixed documents provide strong source integrity but do not yet cover local
layout variation, configurable frames, label workflows, or all regulatory
documents supported by Girvi.

### Funding custody boundary

Loans understands that lender-held collateral cannot be returned to the pawn
borrower, but there is no FundingLoan workflow capable of entering and servicing
that state. The unavailable operation must remain blocked.

### Operational automation

The outbox is durable and has controlled retry. Production rollout still needs
monitoring, stale-work recovery policy, support ownership, and scheduled
operational execution where applicable.

### Future read scale

Event-folded selectors are the correct source of truth. If portfolio size makes
these reads slow, optimized projections may be added without replacing the
immutable event history. Performance work should follow measurement.

## Cutover Rules That Must Not Be Weakened

- Do not merge PawnLoan and FundingLoan into a generic model.
- Do not dual-write one loan into Girvi and Loans.
- Do not import active Girvi loans as second writable copies.
- Do not bypass DEA for accounting effects.
- Do not mutate posted source events, vouchers, or journal entries.
- Do not close a loan without completed collateral return.
- Do not enable repledging before the complete FundingLoan workflow exists.
- Do not expose an incomplete feature with a model or UI stub that appears
  operational.
- Do not retire a Girvi capability without implementing it or recording an
  explicit product decision that it is no longer required.

## Recommended Delivery Order

1. Keep the completed E6.1 unified read contract as the coexistence boundary.
2. Keep the completed E6.2 comparison command as the deterministic pilot gate.
3. Keep the completed E6.3 workspace feature flag as the sole origination-owner switch.
4. Execute E6.4 by piloting the implemented PawnLoan lifecycle in one workspace.
5. Resolve usability and accounting-setup friction found during the pilot.
6. Complete E6.4 and E6.5 production enablement gates.
7. Keep E7.1 notices, E7.2 auction/recovery, and E7.3 renewals operational as complete vertical slices.
8. Implement FundingLoan and repledging as one coherent lender workflow.
9. Integrate Loans documents and statements with the customer portal.
10. Review every P2 parity item with real users before Girvi retirement.

The goal is not to copy Girvi screen for screen. The goal is to preserve required
business capability while rebuilding each accepted workflow against the Loans
service, event, custody, reversal, and DEA boundaries.
