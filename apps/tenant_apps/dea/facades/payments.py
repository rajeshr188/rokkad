from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.dea.models.voucher import Voucher, VoucherStatus
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
from apps.tenant_apps.dea.services.reversal import reverse_posted_voucher


def create_and_post_payment(
    source_obj,
    *,
    direction: str,
    payment_type: str,
    total_amount,
    amount_in_base_currency,
    payment_date,
    payment_method: str = "CASH",
    reference_number: str,
    description: str,
    created_by,
    updated_by=None,
    create_release: bool = False,
    principal_amount=None,
    interest_amount=None,
    is_final_payment: bool = False,
) -> tuple:
    """Create a PaymentVoucher for source_obj and immediately post it."""
    if updated_by is None:
        updated_by = created_by

    ct = ContentType.objects.get_for_model(source_obj)
    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=reference_number,
    ).first()
    if existing:
        if not existing.posted:
            create_and_post_voucher_for_doc(
                doc=existing,
                user=created_by,
                voucher_type_input=existing.get_voucher_type(),
                engine=DjangoPostingEngine(),
            )
            existing.posted = True
            existing.save(update_fields=["posted"])
        return existing, False

    create_kwargs = dict(
        source_document=source_obj,
        direction=direction,
        payment_type=payment_type,
        total_amount=total_amount,
        amount_in_base_currency=amount_in_base_currency,
        payment_date=payment_date,
        payment_method=payment_method,
        reference_number=reference_number,
        description=description,
        is_final_payment=is_final_payment,
        create_release=create_release,
        created_by=created_by,
        updated_by=updated_by,
    )
    if principal_amount is not None:
        create_kwargs["principal_amount"] = principal_amount
    if interest_amount is not None:
        create_kwargs["interest_amount"] = interest_amount

    payment = PaymentVoucher.objects.create(**create_kwargs)

    create_and_post_voucher_for_doc(
        doc=payment,
        user=created_by,
        voucher_type_input=payment.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )

    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True


def reverse_payment_by_marker(source_obj, marker: str, user) -> PaymentVoucher:
    """Find a posted PaymentVoucher by marker and reverse its accounting voucher."""
    payment = find_payment_by_marker(source_obj, marker)
    if not payment:
        raise ValueError(
            f"No PaymentVoucher found for {source_obj.__class__.__name__} "
            f"pk={source_obj.pk} with marker '{marker}'."
        )

    pv_ct = ContentType.objects.get_for_model(PaymentVoucher)
    try:
        accounting_voucher = Voucher.objects.get(
            doc_content_type=pv_ct,
            doc_object_id=payment.pk,
            status=VoucherStatus.POSTED,
        )
    except Voucher.DoesNotExist:
        raise ValueError(
            f"No POSTED accounting voucher found for PaymentVoucher {payment.pk}."
        )

    reverse_posted_voucher(
        voucher=accounting_voucher,
        actor=user,
        reason=f"Reverse payment marker {marker}",
        source_action="payment_marker_reversal",
    )
    payment.posted = False
    payment.save(update_fields=["posted"])
    return payment


def has_other_posted_payments(source_obj, exclude_marker: str) -> bool:
    """Return True if source_obj has posted PaymentVouchers excluding marker."""
    ct = ContentType.objects.get_for_model(source_obj)
    exclude_payment = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=exclude_marker,
    ).values_list("pk", flat=True).first()

    qs = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        posted=True,
    )
    if exclude_payment:
        qs = qs.exclude(pk=exclude_payment)
    return qs.exists()


def find_payment_by_marker(source_obj, marker: str):
    """Return the PaymentVoucher for a source object/idempotency marker, or None."""
    ct = ContentType.objects.get_for_model(source_obj)
    return PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=source_obj.pk,
        reference_number=marker,
    ).first()


def post_payment_voucher(
    payment,
    user,
    *,
    voucher_type_override: str | None = None,
) -> None:
    """Post an already-created PaymentVoucher to accounting."""
    create_and_post_voucher_for_doc(
        doc=payment,
        user=user,
        voucher_type_input=voucher_type_override or payment.get_voucher_type(),
        engine=DjangoPostingEngine(),
    )
    payment.posted = True
    payment.save(update_fields=["posted"])
