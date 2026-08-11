---
status: proposed
owner: loans
updated: 2026-08-11
tags: [loans, risk, policy, configuration]
related: [risk-assessment.md, delinquency-dpd.md, ltv-monitoring.md]
---

# Loan Monitoring Policy

Monitoring policy interprets contractual and valuation facts. It does not
change the loan contract or accounting recognition.

## Initial scope

Use an effective-dated workspace policy with optional license override. Code
may provide safe platform defaults. Do not add individual-loan overrides in the
first version. Every assessment records the resolved policy/version.

Potential settings include:

- DPD and performance-classification boundaries;
- maturity warning windows and grace periods;
- monitoring LTV warning, breach, and critical thresholds;
- rate and appraisal freshness limits;
- eligible collateral custody states; and
- mapping from facts/flags to severity and recommended action.

## Separation from existing policy

`PawnLoanEconomicPolicy` and `LoanPolicySnapshot` govern calculation and frozen
origination economics. Monitoring policy governs current interpretation. Do
not merge them merely because both mention LTV.

## Decisions still required

NPA rules, cure behavior, freshness, custody eligibility, notice consequences,
and auction authority need Owner/legal approval before implementation.
