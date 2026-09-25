---
status: active
owner: loans
updated: 2026-09-24
tags: [loans, license, series, numbering, policy]
related:
  - ../adr/2026-08-09-girvi-capability-extraction-into-loans.md
  - ../adr/2026-08-09-loans-effective-dated-calculation-policy.md
  - ../implementation/pawn-loan-interest-calculation.md
  - ../implementation/loans-girvi-operator-parity-pilot.md
---

# Loans Regulatory Setup And Policy

Operational loan pages and the new-loan/list series pickers display the pawn-number
prefix, or "No prefix" for an unprefixed register. Internal migration series codes
remain stable identifiers; presentation does not rename registers or reset counters.
The loan directory's borrower picker includes inactive customers with existing loans,
whereas new-loan borrower selection continues to require an active Party.

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

New customer Workspaces arrive with four standard loan-product drafts. In Loan
setup > Loan products, review their repayment rules, term bounds, operational grace
and availability, then enable only the products the business offers. Drafts cannot
be selected for new loans. This product choice does not configure or approve the
licence, series or interest policies below. Existing/import-created Workspaces can
receive missing drafts through the explicit operator command; existing terms and
statuses are preserved. See the [preparation decision](../adr/2026-09-24-automatic-draft-loan-products.md).

The ticket-template feature adds optional printed business name/address fields
to each licence, separate from its internal staff-facing name. Licence creation
and amendments record these in immutable revisions; renewal retains them.
Existing records and historical revisions receive empty values, never inferred
identity/address data. Precision ticket layouts can bind these display fields;
when selected, missing values block a new issue and are labelled in previews.
The first issue captures the current licence display values; existing loan terms
and linked regulatory revisions are unaffected, and saved PDFs reprint unchanged.

For historical imports, the setup operator can reserve a reviewed numeric range
through `reserve_sequence_through`. It requires setup authorization and a bounded
evidence reference, locks the existing sequence, and advances only beyond the
reviewed last used number. Lower/repeated requests never rewind later allocations.
The maximum itself can be reserved, leaving the exhausted marker; values above
the configured maximum fail. Reservations are audited and do not issue documents
or alter the independent release counter. Include released and excluded source
numbers when deriving a range. This does not certify source completeness or grant
new lending authority to an inactive/legacy-reference licence. See the
[legacy import plan](../plans/first-legacy-import.md).

Number prefixes may be empty for numeric-only registers. Keep the configured
digit width and reserve the complete source range, including closed/excluded
numbers; an unnamed legacy series must never receive an invented prefix.
The Linode packager scans all matching identifiers in the source Workspace to
avoid reusing a historical number even if its original series association differs.

1. Create a regulatory license with supporting evidence.
2. Create a series and configure independent PawnLoan and release sequences.
3. Add an effective workspace calculation policy, or a license override.
4. Add the required gold/silver monthly rate policies.
   A series can have its own effective-dated gold/silver override under
   Calculation, fees and monitoring > Series-specific monthly interest. Resolution
   uses series, then licence, then Workspace rates. Other economic rules still use
   their existing licence/Workspace scopes; approved loans remain frozen.
5. Add any fee policy deducted or collected by the business.
6. Confirm the license detail shows non-consuming next numbers and readiness.

The calculation policy includes simple/compound interest, full-month/slab
part-month treatment, slab cutoff and lower fraction, capitalization interval,
cash/accrual recognition, valuation method, maximum LTV, advance-interest
periods, per-period currency rounding, and currency quantum.

See [PawnLoan Interest Calculation Internals](../implementation/pawn-loan-interest-calculation.md)
for the implemented period, tranche, advance-interest, finalization,
capitalization, repayment, balance, and overdue rules.

## Freeze Boundary

Calculation and metal-rate policies support same-day numbered revisions.
Scope precedence is unchanged; within a scope the latest applicable effective
date and then highest revision wins. Saving appends evidence and atomically
retains the calculation policy with gold/silver rates. See the
[decision](../adr/2026-09-25-same-day-economic-policy-revisions.md) and
[operator guide](../flows/changing-loan-calculation-settings.md).

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
- The workspace Owner accepted P1 on 2026-08-09. P2 mixed-metal origination and
  disbursal is the next capability gate.
