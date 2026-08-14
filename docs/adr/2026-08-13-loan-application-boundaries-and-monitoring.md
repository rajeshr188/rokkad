---
status: accepted
owner: project
updated: 2026-08-13
tags: [loans, funding-loan, pawn-loan, girvi, risk, documents]
related:
  - 2026-08-09-girvi-capability-extraction-into-loans.md
  - 2026-08-11-loans-product-obligation-and-risk-architecture.md
supersedes:
  - 2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md
---

# ADR: Loan Application Boundaries and Risk Monitoring

## Context

The repository implemented FundingLoan persistence and operator workflows while
still describing FundingLoan as a disabled architecture probe. It also used a
workspace preference to choose either Girvi or PawnLoan as the owner of generic
loan navigation and origination links. That preference confused navigation with
record ownership and contradicted the accepted capability-extraction strategy.

PawnLoan risk can be calculated live, but persistent risk snapshots and portfolio
selectors were not yet presented to operators. Document schema v1/v2 layouts and
the audited legacy print-profile path also appeared removable without a written
account of why they remain.

## Decision

1. FundingLoan is a supported Loans aggregate and workflow. Its persistence,
   lifecycle, custody evidence, services, routes, operator UI, documents, and
   tests are production-domain code. It is not a future or disabled prototype.
2. Girvi and Loans are independent applications during the extraction period.
   Each application owns and services the records created within it. Neither is
   selected as a workspace default, and runtime navigation must not silently
   redirect an operator from one application into the other.
3. Girvi remains available as an established business-rule and operator-workflow
   reference. New Girvi product development stays frozen except for safety fixes
   and work needed to expose a rule being extracted. Its eventual retirement
   requires a separate ADR and explicit operational acceptance.
4. Generic loan entry surfaces present explicit Girvi and PawnLoan choices.
   Application-local create actions always remain in their own application.
5. Persisted `LoanRiskSnapshot` rows are the monitoring and reporting read model.
   The live risk calculation is the authority used to create or refresh a
   snapshot; it is not a second independently reported portfolio source.
   Stale/error snapshots remain visible and must never be presented as current.
6. Risk portfolio selectors are retained and wired into an Owner/Admin operations
   screen. Batch reassessment remains the supported refresh boundary. Material
   immutable risk transitions project into risk-specific internal work items;
   these alerts are not outbound notices and create no email/SMS delivery.
7. Schema-v1/v2 document layouts and `print_profile=legacy` are retained for now.
   They reproduce already configured embedded physical composition and provide
   an explicit, audited recovery path for previously issued or operationally
   required documents. New authoring remains schema v3 and uses an explicit print
   profile. Removal requires evidence that no configured layout, issued artifact,
   or physical printer workflow depends on the compatibility path.

## Consequences

- The FundingLoan runtime-disabled constant, warnings, and contradictory tests are
  removed; FundingLoan still retains its own aggregate boundaries.
- The `loan__new_module_enabled` preference, cutover settings screen, context
  flag, and conditional Girvi/Loans routing are removed.
- Existing preference rows may remain harmless historical data until the clean
  pre-production migration rebuild; they no longer influence runtime behavior.
- Girvi and Loans receive separate navigation and origination actions.
- Portfolio monitoring reads snapshots and clearly reports snapshot freshness;
  refresh services continue to calculate risk live and persist immutable
  transition evidence.
- Document compatibility is a deliberate retained contract, not accidental dead
  code. Its eventual deletion is a separately reviewed cleanup decision.
