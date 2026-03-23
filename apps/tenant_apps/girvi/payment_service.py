from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.models import PaymentVoucher
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
    Create and post a release accounting voucher for GivenLoan release.

    Current policy:
    - If outstanding principal <= 0: skip posting (no economic amount left).
    - If outstanding principal > 0: post GIVENLOAN_RELEASE using PaymentVoucher.

    Idempotency:
    - Deterministic marker in reference_number per release document.
    """
    loan = release.loan
    if not isinstance(loan, GivenLoan):
        raise ValueError("record_loan_release supports GivenLoan releases only")

    outstanding = loan.outstanding_principal
    amount = outstanding.amount if hasattr(outstanding, "amount") else outstanding
    if amount <= 0:
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

    payment = PaymentVoucher.objects.create(
        source_document=loan,
        direction="RECEIPT",
        payment_type="OTHER",
        total_amount=outstanding,
        amount_in_base_currency=outstanding,
        payment_date=release.release_date,
        payment_method="OTHER",
        reference_number=marker,
        description=f"Release write-off for {loan.loan_id} ({release.release_id})",
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
