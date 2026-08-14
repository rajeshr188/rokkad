---
status: superseded
owner: project
updated: 2026-08-08
tags: [loans, girvi, consolidation, funding-loan, retirement]
related:
  - ../plans/loans-girvi-consolidation-fit-gap.md
  - 2026-07-15-loans-rewrite-domain-and-cutover-architecture.md
  - 2026-08-08-girvi-loans-permanent-independent-coexistence.md
  - 2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md
  - 2026-08-08-girvi-operational-core-rebuild.md
superseded_by: 2026-08-09-girvi-capability-extraction-into-loans.md
---

# ADR: Evaluate Loans Consolidation And Girvi Retirement

> Superseded on 2026-08-09 after the evaluation succeeded. Loans is the target
> platform; Girvi remains a temporary capability reference and record owner
> until a separate retirement ADR.

Date: 2026-08-08
Status: Superseded

## Context

The production-data preservation constraint that originally justified a
side-by-side Loans rewrite no longer applies. Loans now implements the stronger
customer pawn-loan core and most valuable Girvi capabilities: Party identity,
license/series numbering, collateral economics, custody evidence, repayment,
interest, partial/full release, renewal, recovery, notices, configurable
documents, immutable source events, and compensating corrections.

The largest remaining aggregate gap is lender funding and repledging. Rebuilding
Girvi would duplicate customer-loan origination and servicing indefinitely.
Adding every Girvi behavior directly to existing PawnLoan models would instead
risk conditional fields and an over-general loan abstraction.

## Decision Under Evaluation

Prefer one operational loan platform in `apps.tenant_apps.loans` if the fit-gap
gates prove that Girvi capabilities can be added as explicit aggregates and
modules without weakening the existing Loans boundaries.

The target shape is:

- `PawnLoan`: money lent to a borrower against collateral.
- `FundingLoan`: money borrowed from a lender against selected PawnLoan
  collateral.
- Shared infrastructure only for Party identity, custody, numbering, documents,
  immutable evidence, selectors, and outbound integrations.
- Accounting remains an outbound consumer of operational events. New funding
  workflows must pass with a null accounting adapter first.
- Girvi becomes eligible for retirement only after operational parity, pilot
  acceptance, and an explicit accepted retirement ADR.

This evaluation did not authorize Girvi removal, record transfer, dual write,
or schema deletion. Its neutral winner-selection boundary was later superseded
by ADR `2026-08-09-girvi-capability-extraction-into-loans.md`; the strict
record-ownership boundary remains active.

## Evidence

The completed Gate A database-free architecture probe demonstrates that Loans
can express:

- validated immutable terms and a separate FundingLoan lifecycle;
- deterministic monthly simple interest, repayment allocation, and event-folded
  balances without PawnLoan services;
- one FundingLoan selecting collateral from multiple active PawnLoans;
- vault-to-lender and lender-to-vault custody transitions;
- duplicate selection and active double-pledge rejection;
- rejection of inactive-loan and non-vault collateral;
- funding LTV constraints at pledge and partial return;
- settlement-plus-custody closure readiness;
- exact newest-first financial and custody correction.

All 15 focused tests pass. The probe leaves
`FUNDING_LOAN_RUNTIME_SUPPORTED = False` and adds no model, migration, route,
feature flag, or accounting dependency. This clears the first acceptance gate
but does not authorize persistence, runtime support, or Girvi retirement.

## Acceptance Gates

1. Pure FundingLoan terms, repayment allocation, pledge, return, closure, and
   correction policies are complete and independent of Django/accounting.
2. A tenant-safe persistence and application slice proves multi-PawnLoan
   collateral locking, one-active-pledge exclusion, idempotency, and immutable
   custody evidence using a null accounting adapter.
3. Every Girvi capability is classified as port, replace, or intentionally
   retire with owner approval and operator evidence.
4. Customer and funding loan end-to-end workflows pass without DEA or
   standalone accounting availability.
5. Cross-app callers depend on Loans facades rather than Girvi ORM models.
6. A pilot workspace passes backup, rollback, permissions, documents, reports,
   reconciliation, custody verification, and operator acceptance.
7. A later ADR explicitly supersedes permanent coexistence and authorizes
   Girvi retirement and destructive schema removal.

## Failure Conditions

Keep Girvi independent or revisit its rebuild if the evaluation requires:

- FundingLoan fields or state branches on PawnLoan;
- mutable custody or balance totals as workflow truth;
- direct accounting imports in domain/application policy;
- generic transition engines shared by unlike aggregates;
- unresolved regulatory or operator workflows that cannot fit Loans cleanly;
- retirement before equivalent documents, reports, custody controls, and
  correction evidence exist.

## Consequences

- The proposed in-place Girvi rebuild is paused during this evaluation.
- New feature investment goes to Loans unless needed to keep current Girvi
  records safe while coexistence remains active.
- The existing Loans code is not accepted unchanged as the final architecture;
  its DEA-gated service paths and large web modules remain cleanup concerns.
- Destructive Girvi migration work is deferred until consolidation is proven
  and separately authorized.
