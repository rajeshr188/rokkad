---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, girvi, consolidation, capability-extraction, retirement]
related:
  - 2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md
  - 2026-08-08-loans-consolidation-and-girvi-retirement-evaluation.md
  - ../plans/loan-operational-parity-pilot.md
  - ../plans/loans-girvi-consolidation-fit-gap.md
supersedes:
  - 2026-08-08-temporary-girvi-loans-coexistence-and-parity-selection.md
  - 2026-08-08-loans-consolidation-and-girvi-retirement-evaluation.md
---

# ADR: Extract Mature Girvi Capabilities Into Loans

## Context

The neutral Girvi-versus-Loans selection pilot no longer matches the product
goal. Loans already provides the cleaner aggregate, service, immutable-evidence,
custody, tenant, correction, and accounting boundaries. Girvi remains valuable
because it contains mature business rules and operator workflows that must not
be lost.

Requiring both products to compete indefinitely would spend time polishing two
destinations. Copying Girvi code, models, statuses, or migration history into
Loans would import the architectural coupling the rewrite was created to avoid.

## Decision

1. `apps.tenant_apps.loans` is the target operational loan platform.
2. Girvi is the temporary capability and business-rule reference. It remains
   runnable for its own records until a separate retirement decision.
3. Work extracts the operator outcome, regulatory rule, calculation, document,
   custody rule, correction rule, and failure behavior from Girvi, then
   implements the simplest faithful form through Loans' architecture.
4. Girvi classes, database shape, URLs, mutable totals, compatibility aliases,
   generic transitions, and migration history are not porting contracts.
5. Each discovered capability is classified:
   - `PORT`: preserve the workflow substantially as-is in Loans;
   - `REPLACE`: preserve the business outcome through a simpler Loans workflow;
   - `RETIRE`: deliberately omit obsolete or unsafe behavior with owner evidence;
   - `DEFER`: retain as named future work with an explicit trigger and risk.
6. The twelve operator scenarios are Loans acceptance gates. Girvi is inspected
   or exercised only as needed to extract the rule and expected outcome; it is
   not independently scored as a competing destination.
7. Loans' boundaries remain non-negotiable: separate PawnLoan and FundingLoan
   aggregates, service-owned commands, selector-owned reads, immutable evidence,
   compensating reversals, explicit custody, Party identity, tenant isolation,
   and outbound accounting events through the configured adapter.
8. New Girvi product development is frozen except critical safety fixes and
   changes required to expose or document a mature rule during extraction.

## Runtime Coexistence Boundary

Selecting Loans as the destination does not transfer existing records or
authorize deletion:

- Girvi owns and services every record created in Girvi.
- Loans owns and services every record created in Loans.
- There is no synchronization, mirroring, migration, or dual write.
- A route preference is not record ownership or retirement.
- Girvi remains available until Loans acceptance, backup/restore, physical
  document checks, reconciliation, and a separate retirement ADR are complete.

## Capability Acceptance

A capability is complete only when:

1. its current Girvi business rule and operator outcome are written down;
2. the chosen `PORT`, `REPLACE`, `RETIRE`, or `DEFER` decision is explicit;
3. the Loans command, evidence, selector, document, and permission boundaries
   are identified;
4. focused automated tests cover lifecycle, money, custody, correction,
   idempotency, and tenant boundaries as applicable;
5. the operator completes the corresponding Loans scenario without a database
   or admin shortcut; and
6. required printed output and physical handling are verified where applicable.

Failure in money, custody, tenant isolation, required regulatory evidence,
backup/restore, or unexplained reconciliation remains a blocking failure.

## Consequences

- The former winner scorecard is retired. Scenario evidence now measures Loans
  readiness and identifies the next capability gap.
- The FundingLoan and operational-parity work already completed in Loans is
  retained as implementation evidence, not a prototype competing with Girvi.
- The proposed destructive Girvi operational-core rebuild remains on hold. It
  may be reconsidered only by a new ADR if a required business capability
  demonstrably cannot fit Loans without breaking these boundaries.
- Girvi retirement still requires a later accepted ADR covering origination
  shutdown, retained-record treatment, exports, rollback, and schema cleanup.

