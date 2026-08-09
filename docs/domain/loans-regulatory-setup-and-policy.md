---
status: active
owner: loans
updated: 2026-08-09
tags: [loans, license, series, numbering, policy]
related:
  - ../adr/2026-08-09-girvi-capability-extraction-into-loans.md
  - ../adr/2026-08-09-loans-effective-dated-calculation-policy.md
  - ../implementation/loans-girvi-operator-parity-pilot.md
---

# Loans Regulatory Setup And Policy

## Extracted Business Rules

P1 classifies the mature Girvi outcomes as follows:

| Rule or outcome | Decision | Loans expression |
| --- | --- | --- |
| One regulatory license owns one or more series | PORT | Workspace-owned `LoanLicense` with protected `LoanSeries` rows. |
| Several licenses may be active in one workspace | PORT | License numbers are workspace-unique; each license has independent series. |
| Loan and release numbers advance independently | PORT | One locked `LoanNumberSequence` per series and document kind. |
| Preview must not consume a number | PORT | Read-only preview; allocation occurs atomically during document creation. |
| A committed number is never recycled | PORT | Locked counter advances once; cancellation or abandoned work does not rewind it. |
| A preset sequence threshold requires a new series | REPLACE | Bounded `maximum_number`; exhaustion fails closed with instructions to select or create a series. |
| Girvi loan-count and loan-amount auto-deactivation thresholds | RETIRE for MVP | They duplicate the accepted bounded-number rule and can unexpectedly stop a register for an unrelated monetary total. Reconsider only from regulatory/operator evidence. |
| License expiry blocks new origination but not servicing | PORT | Issuance checks active status and expiry; existing loans retain the original license revision. |
| License issue, amendment, renewal, and evidence remain explainable | REPLACE | Immutable versioned revisions and hashed supporting documents instead of mutable status/notes history. |
| Business calculation choices vary by workspace or license | REPLACE | Effective-dated workspace policy plus optional license-specific policy. |

## Required Setup Order

1. Create a regulatory license with supporting evidence.
2. Create a series and configure independent PawnLoan and release sequences.
3. Add an effective workspace calculation policy, or a license override.
4. Add the required gold/silver monthly rate policies.
5. Add any fee policy deducted or collected by the business.
6. Confirm the license detail shows non-consuming next numbers and readiness.

The calculation policy includes simple/compound interest, full-month/slab
part-month treatment, slab cutoff and lower fraction, capitalization interval,
cash/accrual recognition, valuation method, maximum LTV, advance-interest
periods, per-period currency rounding, and currency quantum.

## Freeze Boundary

Draft and approval resolve the effective policy for the loan and collateral.
Approval stores the complete calculation and collateral economics. Disbursal
copies that frozen evidence into the one-to-one `LoanPolicySnapshot`. A later
workspace or license configuration applies only to later approvals; it cannot
change the meaning of an existing loan.

## P1 Evidence

- Django system check passes.
- Loans migration drift is clean.
- Migration `loans.0034` passes fresh tenant replay.
- 12 license/series and economic-policy tests pass.
- 5 numbering tests pass, including separate sequences, exhaustion, no reuse,
  non-consuming preview, and concurrent allocation.
- 3 focused setup/disbursal tests pass, proving the Owner UI stores the full
  policy and disbursal uses the policy frozen at approval.
- 16 adjacent approval-lifecycle and core-model tests pass.
- Tenant rollout through `migrate_schemas --tenant` succeeds locally.
- Manual Owner browser walkthrough remains required before P1 is finally marked
  accepted.
