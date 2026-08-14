---
status: accepted
owner: loans
updated: 2026-08-11
tags: [loans, exposure, obligations, delinquency, collateral, risk, monitoring, portfolio]
related:
  - README.md
  - pawn-collateral-risk-and-appraisal.md
  - ../implementation/pawn-loan-interest-calculation.md
  - ../adr/2026-08-09-loans-effective-dated-calculation-policy.md
  - ../adr/2026-08-05-pawn-loan-collateral-tranche-economics.md
  - ../adr/2026-08-05-pawn-loan-release-and-renew-only.md
  - ../constitution.md
---

# Loan Exposure, Risk Assessment, and Portfolio Monitoring Blueprint

> For a shorter reading path, start at [Loan Risk Architecture](README.md).
> This file preserves the complete canonical master blueprint.

> This is the accepted living architecture plan. Implementation is controlled
> by the phase invariants and acceptance gates in
> [the execution roadmap](implementation/roadmap.md).

## A. Current-State Architecture

### Contract and lifecycle

- `PawnLoan` is the current customer-loan aggregate. It stores workspace,
  borrower, regulatory identifiers, original principal, loan date, tenure, and
  lifecycle `state`.
- Persisted lifecycle is intentionally narrow: `DRAFT -> APPROVED -> ACTIVE ->
  CLOSED`, plus cancellation. Operational conditions such as overdue remain
  derived in `apps/tenant_apps/loans/domain/vocabulary.py`.
- Maturity is derived as `loan_date + tenure_months`; there is no separately
  versioned contract schedule or maturity amendment model.
- Renewals close the source contract and create a newly numbered successor.
  They do not modify the original contract in place.
- The app does not use `django-fsm2`; transitions are enforced through service
  rules and immutable change-log evidence.

### Principal, interest, repayments, and dues

- `get_pawn_loan_balance()` in `selectors/balances.py` is the canonical
  recorded-balance selector.
- It folds immutable `PawnLoanAccountingEvent` rows through the requested
  `as_of_date`, including compensating reversals.
- Principal distinguishes original and capitalized-interest components.
  `PawnLoan.principal_amount` is contractual origination data, not a mutable
  outstanding balance.
- Finalized interest is evidenced by `PawnLoanInterestAccrual` and itemized
  `PawnLoanInterestAccrualLine`. Read-only previews can calculate unfinalized
  interest without posting it.
- Repayment allocation is fees, overdue interest, current interest, then
  principal. Principal is allocated across collateral tranches highest-rate
  first and persisted in `PawnLoanRepaymentAllocationLine`.
- There are no penalties, waivers, or general post-disbursal fee-assessment
  commands in current Loans, although the event fold has fee-assessed and paid
  components.
- `total_due` currently means all recorded principal, interest, and fees. It
  does not distinguish economic exposure from what is contractually payable
  now.
- Recorded exposure excludes previewed but unfinalized interest. This known gap
  is documented in `docs/implementation/pawn-loan-interest-calculation.md`.

### Obligations, maturity, and delinquency

- No explicit `RepaymentObligation` exists.
- Current overdue logic is `as_of_date > maturity_date AND recorded total_due >
  0`.
- All unpaid interest is current before maturity and overdue afterward. There
  is no oldest unpaid obligation, partial-obligation satisfaction,
  deterministic DPD, or delinquency bucket.
- Notices and auction eligibility depend on this maturity-overdue definition.
  Their authority must not silently move to a risk projection.

### Collateral and valuation

- `PawnCollateralItem` stores metal, weight, purity, latest appraisal, frozen
  principal allocation, frozen interest rate, and custody state.
- Origination economics calculate item metal value through the Rates facade,
  apply the configured valuation method, and enforce item-level maximum LTV.
- `LoanPolicySnapshot` freezes origination valuation method and maximum LTV.
- Release/renewal readiness has reusable item-valuation logic, but it is
  workflow-specific and includes obsolete partial-release calculations.
- `latest_appraised_value` is mutable current data, not immutable appraisal
  history.
- The Rates facade supports historical `as_of` lookup by timestamp, but rates
  lack an explicit business-effective date and revision contract. Backdated
  entry can therefore weaken strict historical reproducibility.
- There is no current collateral-risk projection, appraisal-age policy,
  valuation staleness result, LTV monitoring status, or transition history.

### Policies

- Calculation policy is effective-dated at workspace level with optional
  license override and is frozen at approval/disbursal.
- There is no LoanProduct abstraction currently governing PawnLoan repayment
  structure and no monitoring/performance-classification policy.
- The clean initial inheritance path is platform defaults in code, then
  effective-dated workspace policy, then optional license override. Do not add
  loan-level overrides initially; freeze resolved policy identity in each
  assessment and snapshot.

### Accounting, scheduling, tenancy, and reporting

- Loans owns contractual/economic source events. DEA owns vouchers, journals,
  and posting. The outbox is the integration boundary.
- Posting readiness is accounting-mode aware. Risk reads must not create or
  repair accounting evidence.
- Existing reconciliation validates event/outbox/DEA references, but does not
  compare contractual principal outstanding with a DEA loan-receivable control
  balance.
- Current reports load a tenant portfolio and calculate balances in Python.
  This is acceptable for the pilot but unsuitable for large filtered
  dashboards.
- Scheduled notice delivery uses a tenant-aware management command. Celery
  exists elsewhere, but Loans has no established monitoring worker system.
- Current production isolation is `django-tenants` schema isolation plus
  explicit workspace checks. Shared-schema PostgreSQL RLS is a documented
  future target, not completed runtime architecture. New risk tables must be
  schema-local and workspace-owned now while remaining RLS-ready.

## B. Problems and Gaps

| Severity | Finding |
| --- | --- |
| Critical | No obligation ledger exists, so DPD, oldest unpaid due date, partial satisfaction, and delinquency transitions cannot be audited deterministically. |
| Critical | Recorded balance and current economic exposure diverge whenever accruals remain unfinalized. |
| Critical | Mutable `latest_appraised_value` cannot reproduce historical collateral value or prove appraisal history. |
| High | `total_due` conflates total recorded exposure with currently payable amount. |
| High | Maturity-only overdue cannot support periodic-interest or instalment delinquency without changing notice and auction authority. |
| High | Portfolio reporting performs broad prefetches and Python folds and has no queryable current risk state. |
| High | No monitoring policy, versioned classifications, transition history, or idempotent daily reassessment exists. |
| High | No rate/appraisal freshness contract exists. |
| High | Historical rate lookup uses record timestamps instead of a dedicated business-effective interval. |
| High | Background processing must explicitly enter one tenant at a time; shared-schema RLS context is not yet the runtime boundary. |
| Medium | Workflow-specific collateral valuation should become a shared read-only boundary before risk uses it. |
| Medium | Fees exist in payloads but there is no complete penalty/waiver domain vocabulary. |
| Medium | Maturity amendments lack immutable contract-version evidence; renewal is the supported replacement. |
| Medium | Accounting reconciliation lacks a stable aggregate receivable-balance contract. |
| Medium | Concurrent refreshers could duplicate transitions without snapshot version and uniqueness guards. |
| Low | Loan-level blended interest rate remains for compatibility although item rates are authoritative. |
| Low | Legacy derived labels such as `OVERDUE` are useful for compatibility but too coarse for portfolio risk. |

## C. Recommended Domain Model

Keep the subsystem in the existing `loans` Django app. A separate `loan_risk`
app would add migrations, tenant registration, permissions, and dependency
edges without yet forming an independent bounded context.

| Concept | Kind | Responsibility |
| --- | --- | --- |
| `PawnLoan` | Persisted aggregate | Contract identity, lifecycle, borrower, frozen terms, and source/successor lineage. |
| `LoanProduct` / `LoanProductVersion` | Persisted configuration and immutable contract version | Define one of the approved repayment structures and the deterministic obligation-generation rules frozen by each PawnLoan. |
| `RepaymentObligation` | Persisted immutable/versioned model | Component amounts contractually due on a date and their originating evidence. |
| `ObligationAllocation` | Persisted immutable model | Applies repayment, reversal, or waiver components to obligations and supports exact reversal. |
| `LoanExposure` | Immutable value object | As-of recorded balances, projected accrual, payable-now amounts, overdue amounts, and total economic exposure. |
| `CollateralValuation` | Immutable value object | Per-item and aggregate eligible value with rate/appraisal provenance and freshness. |
| `CollateralAppraisal` | Persisted immutable evidence | Versioned observation, appraiser/reviewer, effective time, evidence, status, and supersession. |
| `LoanMonitoringPolicy` | Persisted effective-dated policy | DPD buckets, monitoring LTV, severity mapping, freshness, and performance classification. |
| `LoanRiskAssessment` | Pure domain service/result | Interprets exposure, obligations, tenure, collateral, and policy without writes. |
| `LoanRiskSnapshot` | Rebuildable projection/cache | One queryable current row per active loan, with fingerprints and refresh state. |
| `LoanRiskEvent` | Persisted immutable audit event | Records meaningful transitions once, referencing old/new evidence. |
| Assessment/refresh functions | Application services | Load inputs, calculate, update projections, and append transitions at explicit boundaries. |
| Portfolio selectors | Query services | Filter and aggregate snapshots without calculations in views/templates. |

### What is a LoanProduct?

A `LoanProduct` is a reusable definition of a kind of loan offered by a
workspace. It is not an individual customer loan and it is not the outstanding
balance. It describes the contract template from which new loans are created.

For example, a future workspace might offer:

- a three-month bullet pawn loan where principal and interest are payable at
  maturity;
- a six-month pawn loan where interest is payable every month and principal is
  payable at maturity; or
- an instalment loan with a fixed repayment schedule.

A product could identify rules that are genuinely shared by all loans of that
kind, such as:

- repayment structure and obligation-generation method;
- permitted tenure range;
- supported collateral types and eligibility rules;
- policy families used to resolve interest, fees, valuation, and monitoring;
- renewal, prepayment, grace-period, and delinquency treatment; and
- default document/layout requirements.

The product should not own changing balances, repayments, collateral values,
DPD, or risk classifications. Those belong to the individual loan's immutable
evidence and derived assessment. When a loan is approved or disbursed, the
resolved contractual rules must still be frozen on that loan; later edits to a
product must not rewrite an existing contract.

### Why LoanProduct is now required

The initial plan deferred `LoanProduct` while the app had only one approved
PawnLoan contract shape. The Owner has now selected four repayment structures:
single-payment bullet, periodic-interest bullet, flexible partial-payment, and
installment. The obligation schedule can therefore no longer be safely
hard-coded as one bullet maturity due.

Adding `LoanProductVersion` requires decisions about:

- which current fields move to the product and which remain workspace or
  license policy;
- whether Series selects a product, a product selects a Series, or both;
- whether changing a product creates a new effective version;
- how existing loans are backfilled without inventing historical facts; and
- whether a product controls accounting, documents, risk, or only contractual
  obligations.

The product boundary must stay narrow so it does not duplicate current policy
models. It owns repayment structure, schedule-generation rules, permitted
contract ranges, and payment rights. The individual PawnLoan still freezes
resolved terms. Series/License, economic policy, collateral tranches,
accounting, monitoring policy, and risk classification retain their existing
authority.

### How LoanProduct could help later

Once the app supports materially different loan offerings, a product would
provide a clean selection point at origination and remove scattered branching
such as `if bullet`, `if monthly interest`, or `if instalment` from services.
It could help the app:

- generate the correct repayment obligations for each contract type;
- validate that tenure, collateral, and policy choices are allowed together;
- show operators a small set of approved loan offerings instead of unrelated
  configuration fields;
- group portfolio exposure, delinquency, and concentration by product;
- version product terms while preserving the exact version frozen on each
  loan; and
- introduce another loan structure without overloading `PawnLoan.state` or
  weakening current accounting and tenant boundaries.

The concrete triggers for introducing `LoanProduct` now exist:

1. a second repayment structure is approved for implementation;
2. workspaces need multiple named PawnLoan offerings with different contract
   rules;
3. obligation generation contains repeated product-specific branching; or
4. regulatory/reporting requirements demand product-level classification.

Before implementation, write an ADR defining the boundary between Product,
Series/License, economic policy, monitoring policy, and the frozen loan
contract. Prefer an effective-dated or immutable product version referenced by
new loans. Do not retrofit existing loans to a product version unless their
historical evidence proves the mapping.

### How repayment obligations fit the current Loans app

The current app records what economically happened, but it does not separately
record what the contract required to be paid on a particular date.

Today a repayment answers two allocation questions:

1. Which balance component did the receipt settle? The current order is fees,
   overdue interest, current interest, then principal.
2. Which collateral principal tranche did the principal portion reduce? The
   current rule is highest monthly interest rate first, evidenced by
   `PawnLoanRepaymentAllocationLine`.

Those are important and must remain. Neither one answers a third question:

> Which dated contractual obligation did this payment satisfy?

`RepaymentObligation` and `ObligationAllocation` add that missing dimension.
They sit alongside the existing event fold and tranche allocation; they do not
replace either one.

```text
Money received
      |
      v
PawnLoan repayment event
      |
      +--> component allocation
      |    fees / interest / principal
      |
      +--> principal tranche allocation
      |    which collateral principal was reduced
      |
      +--> obligation allocation
           which dated contractual dues were satisfied
```

### RepaymentObligation

A repayment obligation is immutable evidence of an amount the borrower was
contractually required to pay by a due date. It should identify:

- the PawnLoan and workspace;
- the due date;
- principal, interest, fee, and penalty components, using only components the
  app actually supports;
- the source contract, accrual, amendment, or renewal evidence that created it;
- a stable obligation type and sequence; and
- correction/supersession evidence when the contractual schedule changes.

Do not persist mutable fields such as `amount_satisfied`, `outstanding`, or
`is_overdue` as independent truth. Derive them by folding immutable obligation
allocations and reversals through the requested as-of date.

For the current bullet PawnLoan, the first implementation can be small: create
one maturity obligation whose due date is `loan_date + tenure_months`. The exact
components included must follow the approved contractual rule. A later
monthly-interest or instalment product could generate several obligations, but
the current PawnLoan does not justify that complexity yet.

### ObligationAllocation

An obligation allocation is immutable evidence that some component of a source
event satisfied a particular obligation. It should link:

- one repayment, release receipt, auction recovery, renewal settlement,
  approved waiver, or its reversal;
- one repayment obligation;
- the component being satisfied; and
- the amount applied.

Allocations should follow a deterministic rule. For example, after applying
the existing component priority, an interest amount should satisfy the oldest
eligible unpaid interest obligation first, and principal should satisfy the
oldest eligible principal obligation first. The service must reject allocation
beyond the obligation's remaining component balance.

A reversal must append exact compensating allocations against the original
allocations. It must not edit or delete them. Release, renewal, and auction
commands also need allocations because they settle contractual dues even
though they are not ordinary repayment commands.

### Concrete example

Assume a PawnLoan has a maturity obligation due on 31 March:

```text
Principal due:  100,000
Interest due:     6,000
Total due:      106,000
```

The borrower pays 20,000 on 10 April. Existing component allocation may record:

```text
Interest:  6,000
Principal: 14,000
```

Existing tranche lines then explain which collateral principal balances lost
the 14,000. New obligation allocations explain that the payment satisfied
6,000 interest and 14,000 principal of the 31 March obligation. The remaining
obligation is 86,000, its oldest unpaid due date is still 31 March, and DPD on
10 April is deterministically 10 days. A later reversal restores exactly those
obligation components without guessing.

### What this makes useful or simpler

- `amount_due` becomes distinct from total economic exposure. Future principal
  or projected interest can be exposed without being overdue.
- DPD becomes `as_of_date - oldest unpaid obligation due date`, rather than a
  proxy based only on loan age or maturity.
- Partial payment is explainable: the system can show which due components
  remain unpaid and since when.
- Multiple unpaid dues can be handled oldest-first without hiding their dates
  inside one aggregate balance.
- Historical assessment becomes reproducible because future payments and
  obligations are excluded from an earlier as-of date.
- Delinquency buckets, cure events, collection worklists, and customer notices
  can use one auditable fact boundary.
- Renewals, extensions, releases, auctions, waivers, and reversals can prove
  how old obligations were settled, replaced, or restored.
- A later monthly-interest or instalment structure can reuse the same DPD and
  allocation engine rather than adding status-specific logic.

### What changes and what does not

Changes:

- Disbursal/renewal activation must create the approved obligations
  idempotently from frozen contract evidence.
- Repayment, release, renewal settlement, auction recovery, waiver, and
  reversal services must append obligation allocations inside their existing
  transactions.
- Exposure selectors derive due, overdue, oldest unpaid date, and DPD from
  obligations and allocations.
- Backfill tooling must reconstruct historical obligations and allocations and
  quarantine any loan that cannot reconcile exactly.

Does not change:

- `PawnLoanAccountingEvent` remains the source of economic money movement.
- The canonical event fold remains the source of recorded principal, interest,
  and fee balances.
- `PawnLoanRepaymentAllocationLine` remains the source of item-principal
  movement across collateral tranches.
- DEA remains authoritative for vouchers and journal balances.
- Existing notice and auction eligibility remains maturity-overdue until an
  ADR explicitly adopts obligation-based authority.
- `PawnLoan.state` remains contractual lifecycle, not delinquency state.

The implementation must enforce a reconciliation invariant:

```text
sum of unapplied economic component balances
    ==
sum of outstanding obligation component balances that are currently due
    + components not yet contractually due
```

Any difference is an integrity finding. It must not be repaired by silently
editing obligations or allocations.

Obligation generation is product-version driven. The architecture must support
single-payment bullet, periodic-interest bullet, flexible partial-payment, and
installment schedules. Their exact cadence, due-date, grace, amortisation,
prepayment, and maturity rules must be approved before implementation.

## D. Source-of-Truth Matrix

| Value | Authoritative source | Calculated by | Persisted? | Projection? | Historical reconstruction |
| --- | --- | --- | --- | --- | --- |
| Original principal | Disbursal/renewal-opening evidence | Existing event fold | Immutable evidence | Yes | Fold events through date |
| Principal outstanding | Accounting events and allocation lines | Exposure calculator | No | Yes | As-of event fold |
| Recorded interest outstanding | Finalized accrual/payment events | Existing balance fold | Evidence only | Yes | As-of event fold |
| Projected interest | Frozen terms/tranches and accrual evidence | Existing accrual preview reused by exposure | No | Yes | Preview from evidence available at date |
| Interest currently due | Obligations and allocations | Obligation calculator | Obligation facts persisted | Yes | Reconstruct obligations/allocations |
| Fees/penalties outstanding | Typed source events and allocations | Exposure calculator | Immutable evidence | Yes | As-of fold |
| Amount due now | Outstanding obligations due by as-of | Exposure calculator | No | Yes | Recalculate from obligations |
| Overdue amount | Unpaid obligations before as-of | Exposure calculator | No | Yes | Recalculate from obligations |
| DPD | Oldest unpaid overdue obligation | Risk assessment | No | Yes | Date difference at requested date |
| Total economic exposure | Principal, recorded components, separately disclosed projected accrual | Exposure calculator | No | Yes | Event fold plus preview |
| LTV exposure | Policy-selected exposure components | Risk assessment | No | Yes | Resolve monitoring policy version |
| Collateral value | Rate/appraisal evidence and eligible custody | Valuation service | Evidence persisted | Yes | Historical source selection |
| Current LTV | LTV exposure divided by eligible collateral value | Risk assessment | No | Yes | Recalculate; unknown without value |
| Tenure status | Contract version and date | Risk assessment | No | Yes | Contract effective at date |
| Performance classification | Facts and monitoring policy | Risk assessment | No | Yes | Policy effective at date |
| Overall severity | Flags and policy mapping | Risk assessment | No | Yes | Recalculate; never lifecycle authority |
| Accounting receivable | DEA journals/control ledger | DEA facade | Yes in DEA | Optional reconciliation projection | DEA as-of ledger balance |

## E. Proposed Service Architecture

```text
Immutable loan events + frozen contract + obligations/allocations
                              |
                              v
                 calculate_loan_exposure(as_of)
                              |
Collateral items + custody + historical rates/appraisals
                              |
                              v
                 value_loan_collateral(as_of)
                              |
          Exposure + valuation + tenure + resolved policy
                              |
                              v
                      assess_loan_risk()
                              |
                    pure result, no writes
                              |
                              v
                refresh_loan_risk_snapshot()
                              |
                compare previous committed result
                              |
                              v
              append deduplicated LoanRiskEvents
```

Proposed read interfaces:

- `calculate_pawn_loan_exposure(loan_id, *, as_of_date) -> PawnLoanExposure`
- `value_pawn_loan_collateral(loan_id, *, as_of_date, policy) -> PawnCollateralValuation`
- `assess_pawn_loan_risk(loan_id, *, as_of_date) -> PawnLoanRiskAssessment`
- `refresh_pawn_loan_risk(loan_id, *, as_of_date, trigger_key) -> LoanRiskSnapshot`

Transaction rules:

- Pure exposure, valuation, and assessment functions never write or lock.
- Commands continue to lock `PawnLoan` and create immutable source evidence.
- Snapshot refresh calculates optimistically, then locks the snapshot row and
  compares the source fingerprint/version before upsert.
- If authoritative inputs changed during calculation, discard and retry.
- Transition persistence shares the snapshot-update transaction.
- A uniqueness key over workspace, loan, event type, and old/new fingerprints
  prevents duplicate transition events.
- Workflows consume committed events or perform a fresh command-side eligibility
  check. A stale snapshot is never legal authority.
- DEA stays behind a reconciliation facade returning aggregate receivable and
  variance; risk code does not query journal internals.

## F. Event and Recalculation Matrix

| Trigger | Exposure | Collateral | Risk | Snapshot | Transition possible |
| --- | ---: | ---: | ---: | ---: | ---: |
| Disbursal or renewal opening | Yes | Yes | Yes | Yes | Initial assessment |
| Repayment or reversal | Yes | No | Yes | Yes | DPD/LTV/severity cure or deterioration |
| Interest accrual, reversal, or capitalization | Yes | No | Yes | Yes | Exposure/LTV/severity |
| Fee, penalty, waiver, or reversal | Yes | No | Yes | Yes | DPD/exposure/severity |
| Release, auction, renewal close, or reversal | Yes | Yes | Yes | Yes | Terminal/reopened assessment |
| Contract extension/amendment | Yes | No | Yes | Yes | Maturity/DPD |
| Appraisal approved/superseded | No | Yes | Yes | Yes | LTV/staleness/severity |
| Custody corrected/transferred | No | Yes | Yes | Yes | Eligibility/LTV |
| Metal rate effective | No | Yes | Yes | Yes | LTV warning/breach/cure |
| Monitoring policy effective | No | Policy-dependent | Yes | Yes | Classification/severity |
| Business date advances | Projected interest | Freshness | Yes | Yes | Maturity, DPD, staleness |
| Accounting delivery changes | No contractual change | No | Reconciliation only | Yes | Integrity flag |

## G. Query and Portfolio Architecture

- Maintain one `LoanRiskSnapshot` per active PawnLoan and workspace. Keep
  transition history in `LoanRiskEvent`, not duplicate daily snapshots.
- Store typed filter columns for exposure, overdue, DPD, maturity, valuation,
  LTV, classifications, severity, freshness, assessment date, input
  fingerprint, and policy version. Detailed flags/explanations may also use
  structured JSON, but JSON must not replace filterable columns.
- Portfolio selectors query snapshots first and join lightweight loan,
  borrower, and license data. Detail views may request a fresh read-only
  assessment.
- Aggregate customer concentration by borrower/workspace. Defer product
  concentration until a real `LoanProduct` exists.
- Expected indexes:
  - `(workspace, as_of_date, overall_severity)`
  - `(workspace, delinquency_bucket, days_past_due)`
  - `(workspace, tenure_status, maturity_date)`
  - `(workspace, collateral_status, current_ltv)`
  - `(workspace, total_exposure)`
  - `(workspace, borrower, total_exposure)`
  - partial indexes for overdue, LTV breach, and stale rows
  - unique `(workspace, loan)` for current snapshots
- At 1,000 to 10,000 active loans, a daily tenant command plus event-driven
  dirty refresh is sufficient.
- At 100,000+, process indexed dirty IDs in bounded batches with
  `select_for_update(skip_locked=True)`, reuse a rate watermark per metal, and
  aggregate from snapshots in SQL. Kafka and event sourcing remain out of
  scope.

## H. Migration Strategy

1. Add new models without changing balance, notice, auction, or lifecycle
   behavior.
2. Introduce monitoring policy and immutable appraisal evidence; retain
   `latest_appraised_value` as compatibility input until active loans have an
   eligible appraisal strategy.
3. Backfill one maturity obligation for active historical PawnLoans from
   immutable disbursal/renewal evidence. Record provenance and failures; never
   invent missing economics.
4. Reconstruct obligation satisfaction from repayment, release, auction, and
   renewal allocation evidence in chronological order.
5. Produce a dry-run reconciliation report before persistence. Quarantine any
   loan whose obligations do not reconcile to the canonical balance.
6. Initialize snapshots only after exposure, obligation, and valuation checks.
   Unassessable loans use explicit `UNKNOWN/INCOMPLETE`, not fabricated low
   risk.
7. Run old reports and new selectors in parallel during compatibility.
8. Move dashboards only after variance tests and Owner acceptance.
9. Do not remove `balance.is_overdue`, `total_due`, or appraisal compatibility
   fields until dependent workflows have explicit replacement contracts.
10. Use `migrate_schemas` for tenant-app migrations. Include workspace ownership
    and workspace-leading indexes so the models remain RLS-ready.

## I. Phased Implementation Plan

### Phase 0 - Characterization and decisions

- Document balance, projected interest, maturity overdue, notice, auction,
  renewal, and reversal invariants.
- Add characterization tests for as-of folds and historical rates.
- Decide interest cadence, monitoring LTV, freshness, custody eligibility, NPA
  thresholds, and workflow consequences.
- Acceptance: terminology and authority matrix approved; no runtime change.
- Out of scope: schema and UI changes.

### Phase 1 - Loan product foundation

- Add workspace-owned Product and immutable ProductVersion boundaries.
- Freeze product-version identity and repayment rules at approval/disbursal.
- Define deterministic schedule strategies for the four approved structures.
- Test tenancy, version immutability, origination eligibility, renewal, and
  separation from Series/License and economic policy.
- Out of scope: obligations, balances, and risk calculations.

### Phase 2 - Exposure foundation

- Extract a pure `PawnLoanExposure` calculator around balance and accrual
  preview.
- Keep recorded/projected amounts separate; define total exposure, due now, and
  LTV exposure.
- Test every existing event, reversals, future-event exclusion, advance
  interest, capitalization limitation, and settlement.
- Acceptance: recorded components exactly reconcile to existing selectors.
- Out of scope: DPD and persistence.

### Phase 3 - Obligations and DPD

- Add immutable obligations and allocations.
- Generate obligations from the frozen product version and apply repayments,
  settlements, and reversals deterministically.
- Test due today, 1 DPD, partial payment, oldest unpaid due, renewal, settlement,
  and reversal.
- Acceptance: every supported loan has explainable due/overdue/DPD and balance
  reconciliation.
- Out of scope: instalments and silent notice/auction changes.

### Phase 4 - Collateral valuation boundary

- Extract reusable valuation from release readiness.
- Add immutable appraisal versions and missing/stale/disputed results.
- Strengthen rate effective-date/provenance semantics before claiming
  deterministic historical valuation.
- Test mixed metals, price changes, appraisals, custody, and missing/stale data.
- Acceptance: item values sum exactly with provenance.
- Out of scope: rich appraisal UI.

### Phase 5 - Monitoring policy

- Add effective-dated workspace policy with optional license override.
- Configure DPD buckets, warning/breach/critical LTV, freshness, performance,
  severity, and assessment version.
- Freeze resolved policy identity in assessment outputs.
- Acceptance: deterministic boundary and version-selection tests.
- Out of scope: loan overrides and generic product inheritance.

### Phase 6 - Pure risk assessment

- Implement tenure, exposure, delinquency, performance, collateral status,
  composable flags, explanations, severity, and recommended action.
- Test thresholds, unknown valuation, maturity, DPD changes, LTV cure, and
  historical as-of behavior.
- Acceptance: every classification exposes facts and policy identity.
- Out of scope: persistence, alerts, and workflow effects.

### Phase 7 - Current snapshot projection

- Add `LoanRiskSnapshot`, source fingerprints, refresh timestamps, and
  stale/error state.
- Implement calculate-then-lock upsert and idempotent retry.
- Backfill tenant by tenant with reconciliation reports.
- Acceptance: concurrent changes cannot publish stale snapshots.
- Out of scope: dashboards and transition events.

### Phase 8 - Transition history

- Add immutable `LoanRiskEvent`.
- Detect maturity, delinquency entry/exit/bucket changes, LTV warning/breach/
  cure, performance changes, and severity changes.
- Acceptance: each transition is emitted once and references old/new evidence.
- Out of scope: sending notices or starting collection/auction.

### Phase 9 - Monitoring orchestration

- Add a schema-explicit `reassess_pawn_loans` command with bounded batches,
  dirty selection, safe retry, and diagnostics.
- Refresh after committed loan events; daily scheduling handles time changes.
- Process one tenant schema at a time and fail closed without context.
- Acceptance: reruns are idempotent and workers do not duplicate events.
- Out of scope: a new distributed platform.

### Phase 10 - Portfolio and reconciliation integration

- Add snapshot-backed selectors, filters, aggregates, exports, detail view
  models, and DEA aggregate receivable reconciliation.
- Test query counts, pagination, filters, concentration, tenancy, and staleness.
- Acceptance: an agreed 10,000-loan benchmark has no per-loan query loop.
- Out of scope: detailed dashboard redesign.

### Phase 11 - Workflow adoption and legacy cleanup

- Allow workflows to react to approved risk transitions, but recheck legal
  eligibility and freeze current facts inside every command.
- Retain maturity-overdue compatibility until an ADR authorizes obligation-
  based notice/auction behavior.
- Deprecate duplicate reporting only after parity and Owner acceptance.
- Acceptance: workflows react to risk without assessment side effects.
- Out of scope: automatic adverse customer action from cached classification.

## J. Recommended Final Architecture

```text
Frozen PawnLoan contract -- immutable events -- obligations/allocations
             |                         |
             +-------------+-----------+
                           v
                    Loan Exposure
           recorded facts + projected accrual
                           |
Collateral + custody + historical rates + immutable appraisals
                           |
                           v
                Collateral Valuation
                           |
 Exposure + obligations + valuation + tenure + monitoring policy
                           |
                           v
                 Loan Risk Assessment
                   pure and explainable
                           |
                           v
              Current LoanRiskSnapshot
                rebuildable projection
                           |
                           v
             Immutable LoanRiskEvents
                    transition audit
                           |
          +----------------+------------------+
          v                v                  v
 Portfolio selectors  Collections/notices  Auction readiness
                      recheck authority     rechecks authority

Loan events -- outbox -- DEA posting
      |                    |
      +-- contractual/DEA reconciliation facade --+
```

## Assumptions and Business Decisions to Review

The blueprint uses these accepted defaults:

- First implementation covers customer `PawnLoan` only; `FundingLoan` remains
  outside this product family.
- Product foundation supports the four approved repayment structures. Exact
  schedule and delinquency rules remain decisions to resolve.
- Monitoring uses a separate effective-dated workspace/license policy. Frozen
  origination LTV remains contractual evidence and is shown for comparison.
- Initial flags include maturity within 30 days, past maturity, payment
  overdue, DPD buckets, valuation missing/stale, LTV warning/breach/critical,
  performance change, and accounting-reconciliation variance.
- `LOW/MEDIUM/HIGH/CRITICAL` is derived presentation data only.
- NPA definitions, cure rules, freshness, eligible custody, customer-notice
  consequences, and auction authority require explicit Owner/legal approval.
- Implementation requires an ADR because it introduces obligation authority,
  projection/event contracts, and future workflow dependencies.

## Implementation Gate

Begin with Phase 0 only. Each later phase starts after the previous phase's
invariants, migration checks, tests, and acceptance evidence pass. The detailed
gates live in `implementation/roadmap.md`.

Financial events → balance
Contract schedule → obligations
Balance + obligations + projections → exposure
Exposure + delinquency + valuation + policy → live risk calculation
Live calculation → persisted risk snapshot
Snapshot changes → immutable risk transition events
