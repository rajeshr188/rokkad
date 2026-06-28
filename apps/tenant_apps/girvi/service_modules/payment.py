"""Payment and accounting side-effect services for Girvi loan lifecycle operations."""

from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from moneyed import Money

from apps.tenant_apps.girvi.integrations.dea_adapter import (
    create_and_post_voucher_for_doc,
    has_other_posted_payments,
    resolve_customer_account,
    reverse_payment_by_marker,
)
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan, TakenLoan
from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService

PaymentVoucher = None  # Compatibility alias for older tests; posting uses DEA facade.


def _money(value, *, currency="INR"):
    if isinstance(value, Money):
        return value
    if isinstance(value, Decimal):
        return Money(value, currency)
    if isinstance(value, str):
        parts = value.strip().split()
        if parts:
            value = parts[0]
    return Money(Decimal(str(value)), currency)


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

    principal_amount = _money(amount)
    interest_deduction = None
    document_charge = None
    payout_amount = principal_amount

    if isinstance(loan, GivenLoan):
        interest_deduction_value = Decimal(
            str(getattr(loan, "disbursal_upfront_interest_deduction", Decimal("0.00")) or Decimal("0.00"))
        )
        document_charge_value = Decimal(
            str(getattr(loan, "disbursal_document_charge", Decimal("0.00")) or Decimal("0.00"))
        )

        if interest_deduction_value < 0 or document_charge_value < 0:
            raise ValueError("Disbursal deductions cannot be negative.")

        if (interest_deduction_value + document_charge_value) > principal_amount.amount:
            raise ValueError(
                "Disbursal deductions cannot exceed principal amount."
            )

        interest_deduction = _money(interest_deduction_value)
        document_charge = _money(document_charge_value)
        payout_amount = _money(
            principal_amount.amount - interest_deduction_value - document_charge_value
        )

    return create_and_post_voucher_for_doc(
        loan,
        direction=direction,
        payment_type="DISBURSAL",
        total_amount=payout_amount,
        amount_in_base_currency=payout_amount,
        payment_date=loan.loan_date,
        payment_method="CASH",
        reference_number=marker,
        description=description,
        principal_amount=principal_amount if isinstance(loan, GivenLoan) else None,
        interest_amount=interest_deduction,
        fee_amount=document_charge,
        created_by=user,
    )


def _ensure_disbursal_party_account(loan):
    if isinstance(loan, GivenLoan):
        party = getattr(loan, "borrower", None) or getattr(loan, "customer", None)
        if party is None:
            raise ValueError(f"Loan {getattr(loan, 'loan_id', loan)} has no borrower")
        resolve_customer_account(
            party,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
        )
        return

    party = getattr(loan, "lender", None)
    if party is None:
        raise ValueError(f"Loan {getattr(loan, 'loan_id', loan)} has no lender")
    resolve_customer_account(
        party,
        role_key="LENDER",
        purpose="LENDER_LOAN_PAYABLE",
    )


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
