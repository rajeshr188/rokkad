---
status: accepted
owner: project
updated: 2026-09-12
tags: [loans, portability, database, immutability]
---

# Protect Loans evidence before historical import

The [complete-history review](2026-09-12-loans-complete-history-mvp.md) found missing
SQL immutability guards on core evidence. The owner authorized implementing this
prerequisite before the historical command.

Migration 0008 adds BEFORE INSERT/UPDATE/DELETE row triggers to fifteen tables:
LoanPolicySnapshot, PawnLoanApprovalSnapshot, PawnLoanEvent,
PawnLoanDisbursalSnapshot, PawnLoanInterestAccrual, PawnLoanInterestAccrualLine,
PawnLoanRepaymentAllocationLine, PawnLoanPrincipalClosingLine, PawnLoanRelease,
PawnLoanReleaseItem, PawnCollateralCustodyEvent, RepaymentScheduleVersion,
RepaymentObligation, RepaymentScheduleChange and ObligationAllocation.

Updates and deletes are rejected, including no-op updates and clearing actor
references. Corrections and schedule changes append evidence. Existing actor
SET_NULL declarations do not bypass the guard: hard-deleting a referenced user
is rejected if Django attempts to clear that evidence reference. Account
deactivation remains available; any future provenance redaction/retention workflow
requires a separate design. No selective actor-null exemption is introduced.

Insert guards verify every direct reference to a Workspace-owned model has the
same Workspace. Where a parent exposes a loan reference, it must match the row's
loan (directly or through its accrual/event/release/collateral parent). These
checks are additional to forced RLS and existing foreign-key/check constraints.
Non-Workspace user references remain actor identities, not tenant-owned rows.
Renewal/funding graph semantics beyond direct loan-bearing references retain
existing specialized guards and service rules.

Mutable PawnLoan and collateral state is not made append-only. The guards do not
replace authorization, lifecycle services, event financial validation or aggregate
completeness checks, and do not make arbitrary direct INSERTs a supported importer.
They validate new references, not every pre-existing historical row. Installation
adds no tables, columns, defaults or data rewrite. Reversal drops only this
migration's triggers/functions under owner-only migration access.

The next portability implementation is explicit historical setup/number mapping
and the Loans-owned historical command, with schema, reconciliation, staging,
preview, approved commit and canonical export. No Loans import endpoint is added
by these guards.
