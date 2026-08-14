---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

Yes, understood clearly.

Your `renew` flow is:

1. Start from an existing `GivenLoan`.
2. Compute current outstanding position:
- outstanding principal
- accrued interest due
- collateral value / eligibility

Then two business paths:

1. Pay-and-renew path:
- borrower pays interest and/or part principal
- create a new loan from the same collateral context
- new principal = updated outstanding principal after payment
- new loan date = renewal date
- original loan is released/closed as part of renewal handoff

2. Top-up renew path (borrow more):
- borrower requests additional amount
- validate: `(requested_extra + outstanding_due) <= collateral_current_value` (or your exact value policy threshold)
- if valid, create new loan principal = `outstanding_due + requested_extra` (or outstanding principal + requested as per your accounting rule)
- release original loan in the same operation

Key requirement I infer:
1. Renewal should be an atomic workflow (payment, validation, new-loan creation, old-loan release).
2. Renewal is effectively a structured â€œclose old + open newâ€ operation, not a field edit.

If you want, next I can translate this into:
1. exact domain rules (inputs, formulas, validations),
2. a `LoanRenewalService` command design,
3. a minimal implementation plan in your current Girvi architecture.

Perfect. First, quick answer:

A command design means modeling a write operation as an explicit command object or command method, for example:
- `LoanRenewalService.renew(command)`
where `command` contains all inputs needed to perform one business action.
It is the write-side equivalent of selectors: selectors read, commands mutate.

Now your renewal flow translated.

## Domain Rules

Inputs:
1. `source_loan_id`
2. `renewal_date`
3. `mode`: `PAY_AND_RENEW` or `TOPUP_RENEW`
4. `interest_paid` (optional, non-negative)
5. `principal_paid` (optional, non-negative)
6. `requested_extra_amount` (required for top-up mode, non-negative)
7. `created_by` user
8. optional metadata: notes, payment method, reference

Computed values:
1. `outstanding_principal_before = source_loan.outstanding_principal`
2. `accrued_interest = source_loan.interest_due(as_of=renewal_date)` (or your existing method)
3. `outstanding_due = outstanding_principal_before + accrued_interest`
4. `collateral_value = source_loan.current_value`
5. `principal_after_payment = outstanding_principal_before - principal_paid`

Renew formulas:
1. Pay-and-renew:
- `new_principal = principal_after_payment`
- interest payment may be full or partial depending on policy
2. Top-up renew:
- Validate `requested_extra_amount + outstanding_due <= collateral_value` (or policy threshold)
- `new_principal = principal_after_payment + requested_extra_amount` or `outstanding_due + requested_extra_amount` based on your accounting policy

Validations:
1. Source loan must exist and be renewable status (`DISBURSED` usually).
2. Loan must not be released/cancelled/sold/auctioned.
3. No active blockers (for example unresolved custody constraints if your process requires).
4. `interest_paid >= 0`, `principal_paid >= 0`, `requested_extra_amount >= 0`.
5. `principal_paid <= outstanding_principal_before`.
6. If policy says interest must be settled before top-up, enforce that.
7. `new_principal > 0`.
8. Top-up LTV check passes.
9. Renewal date cannot be before source loan date.
10. Operation is idempotent guarded (optional but recommended) via renewal reference key.

Lifecycle effects (atomic):
1. Record payment(s) against source loan.
2. Create new renewed loan with same borrower and collateral lineage.
3. Release or close source loan via existing release workflow.
4. Post accounting entries for payments and renewal disbursal.
5. Link old/new loans with a renewal relation.

## LoanRenewalService Command Design

Command DTO:
1. `LoanRenewalCommand`
- `source_loan_id: int`
- `renewal_date: datetime`
- `mode: str`
- `interest_paid: Decimal = 0`
- `principal_paid: Decimal = 0`
- `requested_extra_amount: Decimal = 0`
- `created_by: User`
- `payment_method: str = "CASH"`
- `reference_number: str = ""`
- `notes: str = ""`

Result DTO:
1. `LoanRenewalResult`
- `success: bool`
- `message: str`
- `source_loan_id: int`
- `new_loan_id: int | None`
- `payments_created: list`
- `warnings: list[str]`

Service API:
1. `LoanRenewalService.preview(command) -> LoanRenewalPreview`
- no writes, only computed numbers and validation messages
2. `LoanRenewalService.execute(command) -> LoanRenewalResult`
- writes inside one `transaction.atomic()`
3. Internal steps:
- `_load_and_validate_source()`
- `_validate_command()`
- `_compute_renewal_financials()`
- `_apply_payments_to_source()`
- `_create_renewed_loan()`
- `_release_source_loan()`
- `_post_accounting()`
- `_record_renewal_audit()`

Why command design here:
1. Renewal is a multi-step write transaction crossing domain boundaries.
2. You need explicit, testable input contract.
3. Easy to expose same operation from UI, API, or background jobs without duplicating logic.

## Minimal Implementation Plan in Current Girvi

Phase 1: Data shape
1. Add `LoanRenewal` model (or self-FK fields on `GivenLoan`):
- `source_loan` (OneToOne/ForeignKey)
- `renewed_loan` (ForeignKey)
- `mode`, `renewal_date`
- `interest_paid`, `principal_paid`, `requested_extra_amount`
- `created_by`, timestamps, notes
2. Add indexes and uniqueness constraints to prevent duplicate renewals.

Phase 2: Service
1. Implement `LoanRenewalService` in services.py (or new `services/renewal.py`).
2. Reuse existing pieces:
- payment creation logic from payment services
- release transition path already hardened
- loan ID generation + loan creation flow
3. Ensure one atomic transaction and clear rollback on failure.

Phase 3: UI integration
1. Add `LoanRenewForm` with mode-dependent fields.
2. Update `loan_renew` view in loan.py to call service instead of placeholder message.
3. Add preview section in form: outstanding, due, value, eligible top-up.

Phase 4: Accounting and audit
1. Ensure payment vouchers and disbursal vouchers are posted in correct sequence.
2. Add changelog/audit entries linking source and renewed loan.
3. Add idempotency reference for retry-safe behavior.

Phase 5: Tests
1. Unit tests for formulas/validations.
2. Service transaction tests (all-or-nothing).
3. Integration test for both modes.
4. Negative tests for LTV violation and invalid statuses.

If you want, I can draft the exact `LoanRenewalCommand` and `LoanRenewalService` skeleton in code next, without yet enabling it in UI.
