"""Payment and accounting side-effect services for Girvi loan lifecycle operations."""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.facade import (
    create_and_post_payment,
    ensure_customer_account,
    has_other_posted_payments,
    post_payment_voucher,
    reverse_payment_by_marker,
)
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan, TakenLoan
from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService

PaymentVoucher = None  # Compatibility alias for older tests; posting uses DEA facade.


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

    _ensure_disbursal_party_account(loan)

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


def _ensure_disbursal_party_account(loan):
    party = (
        getattr(loan, "borrower", None)
        or getattr(loan, "customer", None)
        or getattr(loan, "lender", None)
    )
    if party is None:
        raise ValueError(f"Loan {getattr(loan, 'loan_id', loan)} has no disbursal party")

    ensure_customer_account(party)


def record_loan_release(release, created_by):
    """Create and post a release receipt voucher for GivenLoan release."""
    return GivenLoanPostingService().post_release(release, created_by)


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


def record_loan_auction(loan: GivenLoan, user, amount):
    """Create and post auction recovery receipt for a GivenLoan."""
    return GivenLoanPostingService().post_auction_recovery(loan, amount, user)


def record_loan_sale(loan: GivenLoan, user, amount):
    """Create and post collateral sale recovery receipt for a GivenLoan."""
    return GivenLoanPostingService().post_sale_recovery(loan, amount, user)


def reverse_loan_auction(loan: GivenLoan, user):
    """Reverse auction recovery voucher for a GivenLoan."""
    marker = f"AUCTION-{loan.pk}"
    return reverse_payment_by_marker(loan, marker, user)


def reverse_loan_sale(loan: GivenLoan, user):
    """Reverse sale recovery voucher for a GivenLoan."""
    marker = f"SOLD-{loan.pk}"
    return reverse_payment_by_marker(loan, marker, user)


__all__ = [
    "record_loan_disbursal",
    "record_loan_release",
    "record_loan_auction",
    "record_loan_sale",
    "reverse_loan_disbursal",
    "reverse_loan_release",
    "reverse_loan_auction",
    "reverse_loan_sale",
]


create_and_post_voucher_for_doc = create_and_post_payment
