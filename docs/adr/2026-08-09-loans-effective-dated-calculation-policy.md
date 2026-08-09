---
status: accepted
owner: project
updated: 2026-08-09
tags: [loans, policy, interest, accounting, disbursal]
related:
  - 2026-07-15-loans-rewrite-domain-and-cutover-architecture.md
  - 2026-08-09-girvi-capability-extraction-into-loans.md
  - ../domain/loans-regulatory-setup-and-policy.md
---

# ADR: Effective-Dated PawnLoan Calculation Policy

## Context

Loans already stored effective-dated valuation, LTV, advance-interest, metal
rate, and fee policy. The disbursal snapshot still obtained interest method,
part-month treatment, capitalization interval, accounting recognition, and
rounding from code defaults. The setup UI therefore could not truthfully
configure all business rules that later controlled accrual and accounting.

## Decision

1. `PawnLoanEconomicPolicy` is the effective-dated workspace policy with an
   optional license-specific scope.
2. It owns calculation method, part-month method/cutoff/fraction,
   capitalization interval, cash/accrual recognition, valuation, maximum LTV,
   advance-interest periods, rounding method, and currency quantum.
3. Metal-specific monthly rates and named fees remain separate effective-dated
   policy rows because they vary independently.
4. Approval freezes the complete resolved policy with its collateral economics.
5. Disbursal rehydrates `LoanPolicySnapshot` from that immutable approval
   evidence. Later configuration cannot change an approved or active loan.
6. Workspace defaults apply unless an effective license-specific policy exists.
7. The current rounding contract remains currency rounding per accrual period.

## Consequences

- The setup screen is the operator boundary for all agreed calculation choices.
- Cash/accrual recognition is explicit before disbursal and remains traceable
  in the source event and policy snapshot.
- New configurations are appended by effective date; existing approval and
  disbursal evidence is not rewritten.
- Migration `loans.0034` adds the calculation-policy fields and database value
  constraints without changing existing policy defaults.

