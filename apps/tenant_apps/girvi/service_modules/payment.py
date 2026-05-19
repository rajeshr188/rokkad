"""Payment and accounting side-effect services for Girvi loan lifecycle operations."""

from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.facade import (
    create_and_post_payment,
    has_other_posted_payments,
    reverse_payment_by_marker,
)
from apps.tenant_apps.dea.models.payment import PaymentVoucher
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan, TakenLoan


def record_loan_disbursal(loan, user):
    """
    Create and post a disbursal payment voucher for a loan transition to DISBURSED.

    Idempotency:
    - Uses a deterministic marker in reference_number per source loan.
    - If it exists, the existing voucher is returned without re-posting.

    Accounting direction:
    - GivenLoan: PAYMENT (cash out)
    - TakenLoan: RECEIPT (cash in)

    Returns:
        tuple[PaymentVoucher, bool]: (payment, created_flag)
    """
    if not isinstance(loan, (GivenLoan, TakenLoan)):
        raise ValueError("record_loan_disbursal supports GivenLoan and TakenLoan only")

    marker = f"DISBURSAL-{loan.__class__.__name__.upper()}-{loan.pk}"
    direction = "PAYMENT" if isinstance(loan, GivenLoan) else "RECEIPT"
    description = (
        f"Loan disbursal for {loan.loan_id}"
        if isinstance(loan, GivenLoan)
        else f"Taken loan disbursal receipt for {loan.loan_id}"
    )
    amount = loan.get_loan_amount_with_currency

    return create_and_post_voucher_for_doc(
        loan,
        direction=direction,
        payment_type="DISBURSAL",
        total_amount=amount,
        amount_in_base_currency=amount,
        payment_date=loan.loan_date,
        payment_method="CASH",
        reference_number=marker,
        description=description,
        created_by=user,
    )


def record_loan_release(release, created_by):
    """
    Create and post a release receipt voucher for GivenLoan release.

    Records the cash received from the borrower (principal + accrued interest) when
    the collateral is returned and the loan is closed.

    Amount logic:
    - principal_amount = loan.outstanding_principal  (net of any prior payments)
    - interest_amount  = loan.interest_due()          (total accrued interest)
    - total_amount     = principal + interest

    Idempotency:
    - Deterministic marker in reference_number per release document.
    """
    from decimal import Decimal
    from moneyed import Money

    loan = release.loan
    if not isinstance(loan, GivenLoan):
        raise ValueError("record_loan_release supports GivenLoan releases only")

    outstanding = loan.outstanding_principal
    principal_val = (
        outstanding.amount if hasattr(outstanding, "amount") else Decimal(str(outstanding))
    )
    interest_val = Decimal(str(loan.interest_due()))
    total_val = principal_val + interest_val
    if total_val <= 0:
        return None, False

    marker = f"RELEASE-{release.pk}"
    total_money = Money(total_val, "INR")
    interest_money = Money(interest_val, "INR")

    return create_and_post_voucher_for_doc(
        loan,
        direction="RECEIPT",
        payment_type="RECEIPT",
        total_amount=total_money,
        amount_in_base_currency=total_money,
        principal_amount=outstanding,
        interest_amount=interest_money,
        payment_date=release.release_date,
        payment_method="CASH",
        reference_number=marker,
        description=f"Loan release receipt for {loan.loan_id} ({release.release_id})",
        is_final_payment=True,
        create_release=True,
        created_by=created_by,
    )


def reverse_loan_disbursal(loan: GivenLoan, user):
    """
    Reverse the GIVENLOAN_DISBURSAL accounting voucher for a loan.

    Guard: raises ValueError if:
    - No POSTED disbursal voucher exists for this loan.
    - Other non-reversed PaymentVouchers exist for this loan (e.g. repayments
      were already recorded — reverse those first).

    The FSM transition (DISBURSED → APPROVED) is performed by the caller.

    Returns:
        PaymentVoucher: the disbursal payment (now de-posted)
    """
    marker = f"DISBURSAL-{GivenLoan.__name__.upper()}-{loan.pk}"
    if has_other_posted_payments(loan, exclude_marker=marker):
        raise ValueError(
            f"Loan {loan.loan_id} has other posted payment records "
            "(repayments or release). Reverse those first."
        )
    return reverse_payment_by_marker(loan, marker, user)


def reverse_loan_release(loan: GivenLoan, user):
    """
    Reverse the GIVENLOAN_RELEASE accounting voucher for a loan.

    The Release record is deleted by the caller inside the same atomic block;
    this function only handles the DEA reversal.

    Guard: raises ValueError if no POSTED release voucher is found.

    Returns:
        PaymentVoucher: the release payment (now de-posted)
    """
    try:
        release = loan.release
    except Exception:
        raise ValueError(f"Loan {loan.loan_id} has no Release record to undo.")

    marker = f"RELEASE-{release.pk}"
    return reverse_payment_by_marker(loan, marker, user)


__all__ = [
    "record_loan_disbursal",
    "record_loan_release",
    "reverse_loan_disbursal",
    "reverse_loan_release",
]


create_and_post_voucher_for_doc = create_and_post_payment
