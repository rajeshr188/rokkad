"""Payment and accounting side-effect services for Girvi loan lifecycle operations."""

from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.dea.models.voucher import Voucher, VoucherStatus
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
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
    ct = ContentType.objects.get_for_model(loan)

    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        reference_number=marker,
    ).first()
    if existing:
        return existing, False

    if isinstance(loan, GivenLoan):
        direction = "PAYMENT"
        payment_type = "DISBURSAL"
        description = f"Loan disbursal for {loan.loan_id}"
    else:
        direction = "RECEIPT"
        payment_type = "DISBURSAL"
        description = f"Taken loan disbursal receipt for {loan.loan_id}"

    amount = loan.get_loan_amount_with_currency

    payment = PaymentVoucher.objects.create(
        source_document=loan,
        direction=direction,
        payment_type=payment_type,
        total_amount=amount,
        amount_in_base_currency=amount,
        payment_date=loan.loan_date,
        payment_method="CASH",
        reference_number=marker,
        description=description,
        created_by=user,
        updated_by=user,
    )

    create_and_post_voucher_for_doc(
        doc=payment,
        user=user,
        voucher_type_input=payment.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )

    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True


def record_loan_release(release, created_by):
    """
    Create and post a release receipt voucher for GivenLoan release.

    Records the cash received from the borrower (principal + accrued interest) when
    the collateral is returned and the loan is closed.

    Amount logic:
    - principal_amount = loan.outstanding_principal  (net of any prior payments)
    - interest_amount  = loan.interest_due()          (total accrued interest)
    - total_amount     = principal + interest

    This correctly handles both cases:
    - No prior payments: total = loan_amount + all_interest
    - Periodic interest payments made: total = remaining_balance + total_interest
      which equals loan_amount + unpaid_interest (math works out via outstanding)

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

    interest_raw = loan.interest_due()
    interest_val = Decimal(str(interest_raw))

    total_val = principal_val + interest_val
    if total_val <= 0:
        return None, False

    marker = f"RELEASE-{release.pk}"
    ct = ContentType.objects.get_for_model(loan)

    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        reference_number=marker,
    ).first()
    if existing:
        return existing, False

    total_money = Money(total_val, "INR")
    interest_money = Money(interest_val, "INR")

    payment = PaymentVoucher.objects.create(
        source_document=loan,
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
        created_by=created_by,
        updated_by=created_by,
    )

    create_and_post_voucher_for_doc(
        doc=payment,
        user=created_by,
        voucher_type_input="GIVENLOAN_RELEASE",
        engine=DjangoPostingEngine(),
    )

    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True


def _find_posted_voucher_for_payment(payment: PaymentVoucher) -> Voucher:
    """
    Find the DEA Voucher (accounting layer) linked to a PaymentVoucher.
    Raises ValueError if no POSTED Voucher is found.
    """
    ct = ContentType.objects.get_for_model(PaymentVoucher)
    try:
        return Voucher.objects.get(
            doc_content_type=ct,
            doc_object_id=payment.pk,
            status=VoucherStatus.POSTED,
        )
    except Voucher.DoesNotExist:
        raise ValueError(
            f"No POSTED accounting voucher found for PaymentVoucher {payment.payment_id}"
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
    ct = ContentType.objects.get_for_model(loan)

    payment = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        reference_number=marker,
    ).first()
    if not payment:
        raise ValueError(
            f"No disbursal PaymentVoucher found for loan {loan.loan_id}. "
            "Cannot undo disbursal."
        )

    other_posted = (
        PaymentVoucher.objects.filter(
            source_content_type=ct,
            source_object_id=loan.pk,
            posted=True,
        )
        .exclude(pk=payment.pk)
        .exists()
    )
    if other_posted:
        raise ValueError(
            f"Loan {loan.loan_id} has other posted payment records "
            "(repayments or release). Reverse those first."
        )

    accounting_voucher = _find_posted_voucher_for_payment(payment)
    DjangoPostingEngine().reverse_voucher(accounting_voucher.pk, user)

    payment.posted = False
    payment.save(update_fields=["posted"])
    return payment


def reverse_loan_release(loan: GivenLoan, user):
    """
    Reverse the GIVENLOAN_RELEASE accounting voucher for a loan.

    The Release record is deleted by the caller inside the same atomic block;
    this function only handles the DEA reversal.

    Guard: raises ValueError if no POSTED release voucher is found.

    Returns:
        PaymentVoucher: the release payment (now de-posted)
    """
    ct = ContentType.objects.get_for_model(loan)

    try:
        release = loan.release
    except Exception:
        raise ValueError(f"Loan {loan.loan_id} has no Release record to undo.")

    marker = f"RELEASE-{release.pk}"
    payment = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        reference_number=marker,
    ).first()
    if not payment:
        raise ValueError(
            f"No release PaymentVoucher found for loan {loan.loan_id}. "
            "Cannot undo release."
        )

    accounting_voucher = _find_posted_voucher_for_payment(payment)
    DjangoPostingEngine().reverse_voucher(accounting_voucher.pk, user)

    payment.posted = False
    payment.save(update_fields=["posted"])
    return payment


__all__ = [
    "record_loan_disbursal",
    "record_loan_release",
    "reverse_loan_disbursal",
    "reverse_loan_release",
]
