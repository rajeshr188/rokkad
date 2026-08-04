The Loans rewrite has a substantially cleaner and safer architecture than Girvi, but it is not yet a complete Girvi replacement. The PawnLoan lifecycle is MVP-complete; coexistence/cutover work and several established Girvi workflows remain outstanding.

## Why Loans was built separately

Rewriting Girvi in place would have mixed three risky jobs:

- preserving existing production loans,
- correcting legacy architecture,
- introducing a new lifecycle and accounting model.

Instead, the architecture deliberately assigns ownership:

- Existing Girvi records remain owned and editable by Girvi.
- Newly created PawnLoans belong exclusively to Loans.
- There is no dual-write between them.
- Eventually, unified reads will show both sources while actions return to the owning application.

This keeps rollback possible and prevents one loan from being mutated by two implementations. The decision is documented in the [Loans architecture ADR](/C:/Users/rajes/OneDrive/Desktop/rokkad/docs/adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md:19).

The second major decision was not to create another overly generic `Loan` model:

- `PawnLoan` represents money lent to a borrower against collateral.
- Future `FundingLoan` will represent money borrowed from a lender against repledged collateral.
- They can share infrastructure, but their accounting, custody, parties and servicing rules remain separate aggregates.

That boundary is explicit in the [ADR](/C:/Users/rajes/OneDrive/Desktop/rokkad/docs/adr/2026-07-15-loans-rewrite-domain-and-cutover-architecture.md:25).

## Architectural comparison

| Concern | Girvi | Loans rewrite |
|---|---|---|
| Domain model | `GivenLoan`, `TakenLoan`, legacy `Loan`, compatibility aliases | Explicit `PawnLoan`; future separate `FundingLoan` |
| Scope | Broad production module accumulated over time | Deliberately narrow PawnLoan-first aggregate |
| Mutations | Mix of legacy paths and newer services | Commands/services own lifecycle mutations |
| Reads | Views, reports and compatibility logic across a large surface | Dedicated selectors derive balances and readiness |
| Accounting | Modernized to use DEA, but carries historical integration paths | DEA boundary designed in from the beginning |
| Financial history | Some mutable operational state plus posting history | Immutable source events and compensating reversals |
| Accounting delivery | Girvi now has an outbox too | Atomic domain event + deterministic outbox is foundational |
| Policy | Configuration can be consulted by different workflows | Economics and policy frozen in a disbursal snapshot |
| Balances | Legacy fields and services coexist | Central event-folded balances |
| Release | Operationally rich, including lender custody | Mathematical settlement/LTV validation plus immutable custody evidence |
| Documents | Large configurable template/frame system | Fixed, source-linked MVP documents |
| Rollout | Current production owner | Feature-hidden until controlled cutover |

Girvi should not be considered poorly designed throughout. It now has services, transition controls, custody history, an accounting outbox, reconciliation and an operations console. Its main problem is accumulated breadth and compatibility: new code must coexist with old models, routes and behaviors.

Loans is cleaner largely because it was allowed to start with strict boundaries.

## How Loans works internally

The normal workflow is:

```text
Regulatory setup
    ↓
Draft + official number
    ↓
Approval snapshot
    ↓
Accounting readiness
    ↓
Disbursement
    ↓
Immutable event + durable outbox
    ↓
DEA voucher and journal
    ↓
Repayment / accrual / capitalization
    ↓
Partial or full collateral release
    ↓
Zero balance + custody returned
    ↓
Closed
```

### 1. Regulatory setup and numbering

A workspace owns licenses. A license can own multiple series, and every series has separate bounded sequences for:

- PawnLoan numbers
- Release numbers

Draft creation locks the relevant sequence row, allocates the official number and never recycles it. Reaching the configured limit requires creating or selecting another series.

The core entities begin in [core.py](/C:/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/loans/models/core.py:37).

### 2. Draft creation

The draft service:

- verifies the active tenant/workspace,
- verifies Party, license and series ownership,
- validates economics and collateral,
- locks and consumes a number,
- creates the loan and collateral atomically,
- records audit history.

Views do not directly reproduce those rules.

### 3. Approval

Approval creates a versioned, immutable approval snapshot. If the loan is reopened and changed, it must be approved again, producing another snapshot instead of modifying the earlier approval evidence.

### 4. Disbursement and accounting

Disbursement checks:

- valid license and series,
- active accounting period,
- cash funding ledger,
- loan control accounts,
- borrower receivable account mapping,
- interest and conditional fee accounts.

It then freezes the effective loan policy in `LoanPolicySnapshot`, creates a source accounting event and an outbox row in the same transaction.

The outbox carries a deterministic idempotency key and economic payload fingerprint. After commit, the adapter asks DEA to create the source-linked voucher and immutable journal entries. A failure remains visible and retryable; dependent financial actions are blocked until it is resolved.

The event/outbox structures are visible in [core.py](/C:/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/loans/models/core.py:540).

### 5. Balances and repayment

Balances are calculated by folding immutable events and their reversals rather than trusting a manually updated “current balance” field.

Repayment allocation is currently fixed:

1. fees,
2. overdue interest,
3. current interest,
4. principal.

Repayments use the current date; backdating and staff-controlled allocation are intentionally deferred.

### 6. Interest

The disbursal snapshot controls:

- monthly rate basis,
- simple or compound calculation,
- part-month slabs,
- capitalization interval,
- cash or accrual accounting.

Calculations retain high precision, while finalized monthly accrual rows are currency-rounded and immutable. Compound interest only occurs through an explicit capitalization event.

### 7. Partial and full release

Release readiness calculates:

- accrued interest,
- total settlement,
- current collateral values,
- selected and retained collateral,
- resulting retained-collateral LTV.

Partial release must clear fees and interest first, then enough principal to keep retained collateral below the configured LTV limit.

Collateral valuation can use:

- metal rate × net weight × purity,
- staff appraisal,
- lower of the two.

Release records store the exact valuation evidence and custody movements used at that time.

### 8. Closure and reversal

A zero balance alone does not close a PawnLoan. Closure requires:

- financial balance of zero,
- every collateral item returned,
- completed release evidence.

Corrections do not delete or edit posted history. Administrators reverse events newest-first, supply a reason, and DEA creates compensating accounting entries. Original events remain available for audit.

## Improvements over Girvi

The most important improvements are:

1. **Clear aggregate ownership**
   Pawn loans and lender funding are no longer forced into one generic model.

2. **Explicit coexistence rules**
   Girvi owns Girvi loans; Loans owns PawnLoans. No ambiguous dual-write.

3. **Direct Party relationship**
   `PawnLoan.borrower` uses Party directly, although DEA still currently needs a compatibility Customer bridge for account mapping.

4. **Immutable financial intent**
   Disbursements, repayments, accruals, capitalization, releases and reversals have durable source events.

5. **Reliable accounting delivery**
   Domain intent and outbox commit atomically. DEA failure cannot silently erase the business event.

6. **Deterministic idempotency**
   Duplicate submissions and retries do not create duplicate accounting.

7. **Frozen loan economics**
   Later workspace preference changes cannot unexpectedly rewrite an active loan’s economics.

8. **Derived balances and statuses**
   The implementation avoids multiple mutable sources of truth.

9. **Strict correction model**
   Posted events are reversed rather than edited or deleted.

10. **Stronger partial-release control**
    Settlement order and retained-collateral LTV are enforced mathematically.

11. **Explicit custody evidence**
    Release, item selection, valuation and physical return are linked.

12. **Operational observability**
    Staff can see failed posting, accounting blockers, stale outbox work, sequence exhaustion and reconciliation problems.

13. **Safer documents**
    Tickets, repayment receipts and release memos use immutable source evidence and deterministic verification identifiers.

14. **Tenant isolation by construction**
    Workspace relationships are validated against the active tenant schema.

The implemented state is summarized in [AGENT_MEMORY.md](/C:/Users/rajes/OneDrive/Desktop/rokkad/docs/AGENT_MEMORY.md:96).

## What Loans is still missing from Girvi

### Required before controlled production cutover

The PawnLoan lifecycle and controlled workspace gate are complete, but production hardening is not:

- E6.1 unified Girvi + Loans read contracts (complete)
- E6.2 read-only comparison/parity command (complete)
- E6.3 workspace feature flag, direct-URL enforcement, primary navigation switch, and reversible enable/disable behavior (complete)
- E6.4 migration/reconciliation/support/backup/rollback rehearsal and real-workflow pilot acceptance
- E6.5 selected-workspace production enablement

The current next slice is recorded in the [roadmap](/C:/Users/rajes/OneDrive/Desktop/rokkad/docs/plans/loans-rewrite-roadmap.md:506).

### Essential business workflows deferred after MVP

- `FundingLoan` and lender payable accounting
- repledging PawnLoan collateral to a funding lender
- return of repledged collateral
- pay-and-renew
- top-up renewal
- repayment reminders and interest notices
- overdue and auction notices
- auction and sale recovery
- customer portal statements, receipts and releases

These are explicitly marked essential—not abandoned—in [Phase 7](/C:/Users/rajes/OneDrive/Desktop/rokkad/docs/plans/loans-rewrite-roadmap.md:553).

### Girvi operational conveniences not yet reproduced

- loan split and merge
- bulk release and bulk operations
- storage-box/vault-location management
- collateral photographs
- collateral label printing
- physical verification statements and inventory checks
- license document uploads
- license renewal workflow and expiry reporting
- configurable document templates and frames
- template cloning and download packs
- Girvi’s larger collection of analytical, archive, Excel and PDF reports
- lender/TakenLoan repayments and statements
- bulk notices and notification workflows

Girvi’s broad route surface—including split/merge, licenses, notices, repledging and storage—is visible in [girvi/urls.py](/C:/Users/rajes/OneDrive/Desktop/rokkad/apps/tenant_apps/girvi/urls.py:42).

### Deferred control features

- repayment backdating
- staff override of repayment allocation
- assigning staff to specific licenses or branches
- more configurable regulatory document formats
- Girvi-style configurable disbursal deductions are not visibly first-class in the current PawnLoan draft model

## Current architectural risks

The rewrite is sound, but I would keep these on the radar:

- DEA’s borrower account still depends on a compatibility Customer record. The guided setup hides this complexity but does not eliminate it.
- Loans is workspace-gated and therefore has not yet had broad real-world usability exposure.
- Fixed PDFs are safer but less flexible than Girvi’s configurable templates.
- Funding-lender custody vocabulary exists conceptually, but the corresponding workflow is deliberately unavailable.
- Event-folded balances and reconciliation are correct, but high loan volumes may eventually require optimized read models.
- Operational retries exist, but automated worker recovery and scheduling will matter in production.
- Feature parity must be decided based on actual business usage; copying every Girvi screen would recreate the same complexity.

## Recommendation

The architecture is ready to become the foundation for the product. I would not redesign it or merge it back into Girvi.

The shortest safe route to a usable MVP is:

1. Keep E6.1 unified reads as the source-ownership boundary.
2. Use the completed E6.2 comparison as the pilot gate.
3. Keep the completed E6.3 feature flag as the sole origination-owner switch.
4. Execute E6.4 by piloting new PawnLoans in one workspace while Girvi retains its existing loans.
5. Fix usability and accounting-setup friction found in the pilot.
6. Then prioritize renewals, notices and auction recovery.
7. Build FundingLoan/repledging as one complete vertical slice when required—never as a partial placeholder model.

So the verdict is: **PawnLoan architecture is materially better than Girvi’s inherited foundation, and its core lifecycle is complete. The remaining problem is product and operational parity, not another architectural rewrite.**
