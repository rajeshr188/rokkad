---
status: accepted
owner: loans
updated: 2026-08-11
tags: [loans, products, obligations, exposure, risk, roadmap]
related:
  - ../architecture-plan.md
  - ../concepts/loan-products.md
  - ../decisions/ADR-006-four-repayment-products.md
  - ../../../adr/2026-08-11-loans-product-obligation-and-risk-architecture.md
  - status.md
---

# Loan Products, Exposure, and Risk Implementation Roadmap

This is the execution sequence for the accepted architecture. It does not by
itself authorize a phase: start a phase only after its dependencies are
complete and its stated inputs are available.

## Governing standards and defaults

The regulatory baseline is the RBI gold/silver-collateral framework applicable
to the lender category, loan purpose, sanction date, and jurisdiction. Keep
limits policy-driven because regulatory profiles differ across regulated entity
types and may change.

The initial standard profile is:

- bullet means both principal and interest are due at maturity;
- consumption bullet tenor cannot exceed 12 months;
- bullet LTV uses total amount repayable at maturity, not only original
  principal;
- LTV is monitored throughout the loan tenor;
- exact contractual due dates drive overdue and DPD;
- the configured three-day customer grace suppresses charges/escalation only;
  it does not move the due date or regulatory DPD;
- penal charges, if supported, apply only to the amount in default, are
  disclosed, and are not capitalized;
- interest starts from actual disbursal and must reflect repayments from their
  effective date; and
- the contract, KFS/loan ticket, and schedule disclose exact dates, principal,
  interest, charges, collateral, and repayment method.

The four initial ProductVersion structures are:

1. **Single-payment bullet:** no ordinary partial servicing; full principal and
   interest due at maturity/redemption.
2. **Periodic-interest bullet:** monthly-anniversary interest obligations;
   principal due at maturity.
3. **Flexible partial-payment bullet:** voluntary partial payments at any time;
   remaining principal and interest due at maturity; no partial collateral
   release.
4. **Installment:** fixed schedule using EMI or equal-principal amortisation;
   extra principal keeps payment amount and shortens tenure by default.

## Global invariants

These apply to every phase and must never be weakened:

1. `PawnLoan.state` is contractual lifecycle only, never delinquency or risk.
2. ProductVersion, approved terms, obligations, allocations, appraisals, loan
   events, risk events, and posted accounting evidence are immutable.
3. Corrections append exact compensating evidence; posted records are not
   edited or deleted.
4. Loans owns contractual/economic facts; DEA owns vouchers and journals; risk
   interprets facts and performs no posting.
5. Recorded balances and projected, unfinalized exposure remain separately
   labelled.
6. Due, overdue, DPD, LTV status, performance class, and severity are derived.
7. Every persisted row is tenant/workspace safe and every background operation
   enters one explicit tenant context.
8. Commands recalculate current authority; projections never authorize notices,
   collateral release, renewal, or auction.
9. No implementation may invent historical contractual, valuation, or
   accounting evidence.
10. Tenant model migrations use `migrate_schemas`, not plain `migrate`.

## Phase 0 — Regulatory and current-behavior characterization

### Objective

Freeze the actual current behavior and identify every difference from the
accepted product and RBI-aligned contract before changing schema.

### Invariants

- No runtime behavior or persisted evidence changes.
- Every current calculation is characterized, including known undesirable
  behavior.
- Regulatory rules are represented as a versioned compliance profile, not
  scattered constants.

### Implementation work

- Inventory draft, approval, disbursal, accrual, repayment, release, renewal,
  auction, notices, reports, documents, Rates, and DEA contracts.
- Create a decision table for lender category, loan purpose, sanction date,
  tenor, applicable LTV ceiling, bullet definition, and disclosure rules.
- Compare current period-opening monthly interest with actual-outstanding-time
  requirements for mid-period disbursal/repayment.
- Freeze example schedules for all four products, month-end dates, leap year,
  three-day operational grace, and early/late payments.

### Migrations

- None.

### Tests

- Characterization tests for the existing balance fold and all event reversals.
- Golden tests for current accrual preview/finalization and mid-period repayment.
- Contract examples for due-date/DPD day-end behavior.
- Two-workspace isolation tests for existing selectors and commands.

### Acceptance criteria

- A reviewed conformance matrix identifies every keep/change decision.
- Golden examples reconcile to existing immutable events and DEA payloads.
- The interest-timing decision is explicit; no known regulatory conflict is
  deferred silently.
- Django checks and the focused existing Loans suite pass unchanged.

## Phase 1 — Product and immutable contract-version foundation

### Objective

Make repayment structure an explicit, versioned source of contract behavior.

### Invariants

- Product identity is workspace-owned; ProductVersion is immutable after use.
- Every new PawnLoan references exactly one ProductVersion.
- Product never owns Series/License numbering, economic rates, balances,
  collateral state, accounting, or risk classifications.
- Approved/disbursed loans retain frozen product evidence after configuration
  changes.

### Models and migrations

- Add `LoanProduct` with workspace, stable code, name, active state, and audit
  fields.
- Add `LoanProductVersion` with version, availability dates/status, repayment
  structure, amortisation method, payment frequency, tenor bounds, operational
  grace days, extra-payment rule, and calculation-contract version.
- Add required `PawnLoan.product_version` because development data may be reset.
- Add workspace-leading unique constraints and indexes.
- Seed four default products through an explicit idempotent tenant command, not
  a migration side effect.

### Service changes

- Resolve ProductVersion in draft creation/edit and validate workspace,
  availability, loan date, tenure, and supported structure.
- Freeze identity, code, version, structure, and rule fingerprint in approval
  and disbursal evidence.
- Make renewal select an eligible current ProductVersion for the successor.

### Tests

- Product/version validation, immutability, uniqueness, and tenant isolation.
- Draft/approval/disbursal stale-version and cross-workspace rejection.
- Later product edits do not change approved loan evidence.
- Renewal source retains its version and successor freezes its selected version.
- All four defaults seed idempotently in two tenant schemas.

### Acceptance criteria

- Each new PawnLoan has one explainable frozen ProductVersion.
- Existing interest, collateral, numbering, accounting, release, renewal, and
  document gates remain green.
- `migrate_schemas` succeeds on a fresh tenant and all development tenants.

## Phase 2 — Deterministic repayment schedule engine

### Objective

Generate an exact, non-writing schedule from frozen contract/economic inputs.

### Invariants

- Schedule generation is pure and deterministic.
- No arbitrary executable formula or opaque JSON calculation is allowed.
- Component totals reconcile to principal and contractual interest.
- Due dates use one documented calendar-clamping rule.
- Rounding differences are absorbed only by the final obligation and disclosed.

### Models and migrations

- No persisted obligation models yet.
- Add typed value objects/enums for schedule version, obligation components,
  repayment frequency, amortisation method, and extra-payment behavior.

### Service changes

- Add schedule strategies for single bullet, periodic-interest bullet, flexible
  partial bullet, EMI, and equal principal.
- Reuse the corrected canonical interest calculation; do not duplicate formulas.
- Produce exact principal/interest breakdown, maturity, payment dates, totals,
  and fingerprint.

### Tests

- Golden schedules for each product and mixed-metal tranche rates.
- EMI and equal-principal totals, final rounding adjustment, zero-rate cases,
  month-end/leap-year dates, and tenure boundaries.
- Bullet maturity interest and ongoing LTV exposure basis.
- Property tests: principal components sum to principal; balances never become
  negative; identical inputs produce identical fingerprints.

### Acceptance criteria

- Owner-readable examples match contractual expectations for all products.
- Every schedule reconciles exactly at the frozen currency quantum.
- Preview produces no database, outbox, voucher, or journal writes.

## Phase 3 — Immutable obligations and allocations

### Objective

Persist what was contractually due and how economic events satisfied it.

### Invariants

- Obligations and allocations are append-only.
- Derived outstanding/satisfied/overdue values are never mutable truth fields.
- Allocation cannot exceed the remaining obligation component.
- Reversal appends exact inverse allocations.
- Existing component priority and highest-rate collateral-tranche allocation
  remain authoritative for their respective questions.

### Models and migrations

- Add `RepaymentScheduleVersion`, `RepaymentObligation`, and
  `ObligationAllocation` with workspace, loan, source evidence, component,
  dates, sequence, fingerprint, and reversal/supersession links.
- Add uniqueness for schedule fingerprint/sequence and allocation source,
  obligation, component, and order.
- Add database checks for positive/non-negative amounts and tenant consistency.

### Service changes

- Disbursal creates schedule version and obligations idempotently.
- Repayment, release, renewal settlement, auction recovery, waiver (when
  supported), and reversal append allocations in their existing transactions.
- Apply due obligations oldest-first after existing component allocation.
- Extra installment principal creates a new future schedule version with fixed
  payment/shorter tenure; already-due or satisfied obligations remain intact.

### Tests

- Four product schedules persisted exactly once.
- Partial, exact, excess, early, late, full settlement, release, renewal,
  auction, and reversal allocations.
- Oldest-first application across several unpaid obligations.
- Concurrent duplicate request and reversal safety.
- Schedule supersession preserves past obligations and regenerates only future
  obligations.

### Acceptance criteria

- Obligation fold reconciles to the canonical economic component balances for
  every supported event path.
- Any mismatch is an integrity finding, never an automatic repair.
- Immutability and tenant guards pass at service and database boundaries.

## Phase 4 — Exposure foundation

### Objective

Provide one pure as-of-date contractual exposure result.

### Invariants

- Recorded balance, projected interest, due now, overdue, and accounting
  receivable are distinct values.
- Exposure calculation performs no writes.
- Future events, obligations, allocations, and rates are excluded.
- Unknown or inconsistent evidence fails explicitly.

### Models and migrations

- None. `PawnLoanExposure` is an immutable value object.

### Service changes

- Compose the canonical event fold, corrected accrual preview, obligation fold,
  and ProductVersion rules.
- Return original/repaid/outstanding principal, recorded/projected interest,
  fees/penalties, due, overdue, total economic exposure, maturity payoff, and
  LTV exposure basis.

### Tests

- Newly disbursed, accrual, partial principal, interest payment, fees, waiver,
  reversal, full settlement, each product, and as-of future exclusion.
- Recorded totals match `get_pawn_loan_balance()` during compatibility.
- Projected exposure does not create accrual or accounting evidence.

### Acceptance criteria

- Every amount has one source and explanation.
- Existing balance/report discrepancies are documented and reconciled.
- Detail previews clearly label recorded versus projected amounts.

## Phase 5 — DPD and delinquency

### Objective

Derive deterministic due, overdue, oldest unpaid date, DPD, and product-aware
delinquency without changing lifecycle.

### Invariants

- Contractual due date is exact; operational grace does not move DPD.
- DPD comes only from the oldest unpaid overdue obligation.
- Payment cures only the obligations actually satisfied.
- Buckets and performance classes are policy interpretations, not loan state.

### Models and migrations

- No new authoritative model. Extend typed assessment vocabulary only.

### Service changes

- Add pure obligation-fold and DPD calculation.
- Expose both regulatory DPD and operational escalation eligibility after the
  three-day grace.
- Keep legacy `balance.is_overdue` and notice/auction authority unchanged for
  compatibility until Phase 11.

### Tests

- Due today, day-end overdue, DPD 1/29/30/59/60/89/90, operational grace,
  partial payment, oldest of multiple dues, cure, reversal, and all products.
- Monthly periodic interest and installment missed-payment sequences.
- Loan lifecycle remains `ACTIVE` while delinquency changes.

### Acceptance criteria

- DPD examples agree with exact due-date/day-end convention.
- No grace-period case understates regulatory DPD.
- Legacy and new overdue variance report is available.

## Phase 6 — Collateral valuation and RBI-aligned LTV

### Objective

Create reusable historical valuation and ongoing product-aware LTV monitoring.

### Invariants

- Only eligible collateral and intrinsic metal value participate.
- Weight, purity, source price, valuation date, and method are explainable.
- Bullet LTV uses total amount repayable at maturity.
- LTV is checked throughout tenor and unknown data never becomes healthy.
- Frozen origination LTV and current monitoring LTV remain distinct.

### Models and migrations

- Add immutable `CollateralAppraisal` versions and evidence/review fields.
- Strengthen Rates business-effective-date/provenance where needed.
- Add indexes for item/date/status and rate commodity/purity/effective date.

### Service changes

- Extract valuation from release readiness into a workflow-neutral service.
- Resolve policy-selected RBI-compatible reference prices and appraisal inputs.
- Return per-item and aggregate value, freshness, blockers, LTV, headroom,
  breach, and full shortfall.

### Tests

- Gold/silver, purity conversion, stones excluded, multiple items, price rise/
  fall, appraisal versions, stale/missing rates, custody eligibility, and
  historical as-of.
- Tier/profile LTV boundaries, exact limit, warning, breach, repayment cure,
  and price-recovery cure.
- Bullet maturity-payoff numerator versus non-bullet outstanding numerator.

### Acceptance criteria

- Values reproduce from persisted evidence and source rates.
- LTV results identify the applicable compliance profile/version.
- Release/renewal valuation consumers pass parity tests before switching.

## Phase 7 — Monitoring policy and pure risk assessment

### Objective

Interpret exposure, delinquency, tenure, and collateral through a versioned
policy and produce an explainable assessment.

### Invariants

- Facts are calculated before classifications.
- Policy is effective-dated workspace scope with optional license override.
- Severity is derived from flags and never authoritative state.
- Assessment performs no side effects.

### Models and migrations

- Add `LoanMonitoringPolicy` with DPD/performance thresholds, maturity windows,
  operational grace/escalation, LTV thresholds, freshness, custody eligibility,
  severity mapping, and compliance-profile identity.
- Add effective-date, scope, range, overlap, and workspace indexes/constraints.

### Service changes

- Resolve and fingerprint policy.
- Add pure `assess_pawn_loan_risk()` returning tenure, exposure, delinquency,
  performance, collateral, flags, explanations, severity, and action hint.

### Tests

- Every threshold edge and policy override/version boundary.
- Maturity, DPD upgrades/downgrades, LTV warning/breach/cure, missing valuation,
  accounting variance, and multi-flag severity.
- Historical assessment never uses future policy or evidence.

### Acceptance criteria

- Every result says why it received each flag/classification.
- Identical inputs/policy produce an identical assessment fingerprint.
- No assessment call writes or triggers a workflow.

## Phase 8 — Current risk snapshot projection

### Objective

Materialize current assessment for efficient portfolio queries.

### Invariants

- Snapshot is rebuildable and never source of contractual truth.
- One current row exists per workspace/loan.
- Stale/error state is visible.
- A concurrent source change cannot publish an obsolete snapshot.

### Models and migrations

- Add `LoanRiskSnapshot` with typed exposure, due, DPD, maturity, valuation,
  LTV, classification, severity, freshness, policy, input fingerprint, status,
  and timestamps.
- Add unique `(workspace, loan)` and workspace-leading portfolio indexes.

### Service changes

- Calculate without locks, then lock snapshot, compare source fingerprint, and
  upsert or retry.
- Add rebuild and diagnostic services; no workflow side effects.

### Tests

- Idempotent refresh, stale-input race, two workers, error recovery, closed-loan
  handling, and tenant isolation.
- Snapshot values equal fresh pure assessment.

### Acceptance criteria

- Repeated refresh has no duplicate or semantic drift.
- Stale snapshots are detectable and repairable.
- Backfill/rebuild completes for the agreed pilot portfolio with diagnostics.

## Phase 9 — Immutable risk transitions

### Objective

Persist meaningful changes for audit and later workflow consumption.

### Invariants

- Events are append-only, deduplicated, and reference old/new fingerprints.
- Daily reruns do not duplicate transitions.
- Transition persistence shares the snapshot-update transaction.

### Models and migrations

- Add `LoanRiskEvent` with workspace, loan, event type, occurred/as-of dates,
  old/new values, snapshot/fingerprint references, policy, trigger key, and
  metadata.
- Add transition-deduplication and workspace/date/type indexes.

### Service changes

- Detect maturity, delinquency enter/exit/bucket, LTV warning/breach/cure,
  performance, severity, and assessment-error transitions.

### Tests

- Every transition in both directions, repeated refresh, reversal-driven cure,
  price-driven cure, policy change, and concurrent workers.

### Acceptance criteria

- Each real transition appears once with explainable old/new facts.
- Rebuilding current snapshot never deletes or rewrites history.

## Phase 10 — Monitoring orchestration and portfolio selectors

### Objective

Refresh changed/time-sensitive loans safely and make the projection queryable.

### Invariants

- Every job has explicit tenant/workspace context.
- Work is bounded, idempotent, retryable, and observable.
- Portfolio views use selectors, not template/view calculations.

### Models and migrations

- Add a small dirty/reassessment queue only if event-triggered selection cannot
  be represented reliably from existing evidence.
- Add/adjust partial indexes after measured query plans.

### Service changes

- Refresh on committed economic, obligation, collateral, appraisal, rate,
  custody, contract, or policy change.
- Add daily `reassess_pawn_loans` tenant command for time-only transitions.
- Add selectors for maturity, DPD, performance, LTV, severity, exposure,
  borrower, ProductVersion, and aggregate concentration.

### Tests

- Daily boundary changes, bounded batching, `skip_locked`, safe retry, failure
  diagnostics, cross-tenant rejection, filters, pagination, aggregation, and
  query counts.
- Benchmarks for 1,000 and 10,000 active loans; document the 100,000+ plan.

### Acceptance criteria

- Daily rerun is idempotent and finishes inside the agreed operating window.
- Portfolio queries have no per-loan query/calculation loop.
- Missing/stale/error assessments remain visible and filterable.

## Phase 11 — Documents, reconciliation, and workflow adoption

### Objective

Expose the new contract/risk facts and let existing workflows react safely.

### Invariants

- Official documents freeze ProductVersion and exact repayment schedule.
- DEA reconciliation is read-only across a facade.
- Notice, collection, renewal, release, and auction commands recalculate their
  own authority and freeze current evidence.
- Risk assessment never performs workflow side effects.

### Models and migrations

- Add immutable issued-document payload fields only where current issue evidence
  cannot preserve product/schedule identity.
- No mutable workflow flags on PawnLoan.

### Service/UI changes

- Show Product, schedule, due/overdue, DPD, recorded/projected exposure,
  collateral value, LTV, flags, severity, and explanations on detail/previews.
- Add KFS/schedule document output and exact stored reprint behavior.
- Add DEA aggregate receivable reconciliation contract.
- Migrate notices/auction eligibility only through the accepted ADR and parity
  period; keep snapshot advisory.

### Tests

- Document totals/schedules and immutable reprints for every product.
- Loans exposure versus DEA receivable match/variance/error.
- Workflow eligibility under fresh, stale, cured, reversed, and cross-workspace
  conditions.
- Full report/export parity and authorization tests.

### Acceptance criteria

- Owner accepts one complete browser/document/accounting walkthrough per
  product.
- Regulatory disclosures and due-date examples are readable and exact.
- Existing workflow authority is retired only after zero unexplained parity
  differences and explicit Owner acceptance.

## Final completion gate

The architecture is implemented only when:

- all four products originate, freeze, schedule, service, reverse, renew, and
  close correctly;
- exposure, obligation, DPD, valuation, LTV, risk, projection, and transition
  invariants pass;
- tenant isolation and `migrate_schemas` gates pass on fresh and existing
  development schemas;
- Loans/DEA reconciliation has no unexplained difference;
- documents reproduce exact contract and repayment schedules; and
- the Owner accepts each product and the portfolio monitoring workflow.
