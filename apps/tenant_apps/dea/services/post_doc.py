from datetime import datetime

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.tenant_apps.dea.posting.commands import PostVoucherCommand
from apps.tenant_apps.dea.posting.context import PostingContext, compute_fingerprint
from apps.tenant_apps.dea.posting.registry import registry
from apps.tenant_apps.dea.posting.types import PostingError
from apps.tenant_apps.dea.models import Voucher, VoucherStatus, VoucherType
from apps.tenant_apps.dea.services.voucher_type_seed import ensure_seeded_voucher_type
from apps.tenant_apps.dea.services.voucher_numbering import generate_date_based_voucher_number


def _resolve_voucher_type(voucher_type_input):
    """
    Resolve voucher_type input to a VoucherType instance.
    Accepts:
      - VoucherType instance → return as-is
      - string (name) → lookup by name
      - int (pk) → lookup by pk
    Raises ValueError if input is invalid or not found.
    """
    if isinstance(voucher_type_input, VoucherType):
        return voucher_type_input

    if isinstance(voucher_type_input, str):
        try:
            return VoucherType.objects.get(name=voucher_type_input)
        except VoucherType.DoesNotExist:
            try:
                return ensure_seeded_voucher_type(voucher_type_input)
            except VoucherType.DoesNotExist:
                raise ValueError(f"VoucherType with name '{voucher_type_input}' not found")

    if isinstance(voucher_type_input, int):
        try:
            return VoucherType.objects.get(pk=voucher_type_input)
        except VoucherType.DoesNotExist:
            raise ValueError(f"VoucherType with pk {voucher_type_input} not found")

    raise ValueError(
        f"Invalid voucher_type input: expected VoucherType, str, or int, got {type(voucher_type_input)}"
    )


def _resolve_voucher_date(doc):
    """Pick the business-effective date for voucher posting."""
    candidate_fields = (
        "voucher_date",
        "je_date",
        "expense_date",
        "invoice_date",
        "movement_date",
        "period_end",
        "period_start",
        "effective_date",
        "date",
    )

    for field_name in candidate_fields:
        value = getattr(doc, field_name, None)
        if value:
            return value.date() if isinstance(value, datetime) else value

    created_at = getattr(doc, "created_at", None)
    if created_at:
        return created_at.date() if isinstance(created_at, datetime) else created_at

    return timezone.now().date()


def create_and_post_voucher_for_doc(doc, user, voucher_type_input, engine):
    """
    Create and post a voucher for `doc` only when economic payload differs from
    the latest posted voucher for that doc (idempotent, supersede semantics).

    Args:
        doc: business document instance (must be a model with content_type/object_id support).
        user: User instance (or object with .id attribute).
        voucher_type_input: VoucherType instance, or string name, or int pk.
        engine: PostingEngine instance (DjangoPostingEngine).

    Returns:
        tuple (voucher, journal_entry): newly-created (voucher, je) or existing (prev_voucher, prev_je) if no change.
    """
    ct = ContentType.objects.get_for_model(doc)
    user_id = getattr(user, "id", None)

    # Resolve voucher_type to VoucherType instance
    voucher_type = _resolve_voucher_type(voucher_type_input)

    # Resolve rule and compute fingerprint from business doc only (no voucher created yet)
    rule = registry.get(voucher_type.name)
    tmp_ctx = PostingContext(voucher=None, doc=doc, user_id=user_id)
    payload = None
    try:
        fp_payload_fn = getattr(rule, "fingerprint_payload", None)
        if callable(fp_payload_fn):
            payload = fp_payload_fn(tmp_ctx)
        elif hasattr(doc, "get_economic_payload"):
            payload = doc.get_economic_payload()
        else:
            payload = {"id": getattr(doc, "id", None)}
    except Exception:
        payload = {"id": getattr(doc, "id", None)}

    new_fp = compute_fingerprint(payload, getattr(rule, "rule_version", "1"))

    # find latest posted voucher / JE for this business doc (if any)
    prev_voucher = (
        Voucher.objects.filter(
            doc_content_type=ct,
            doc_object_id=doc.pk,
            voucher_type=voucher_type,
            status=VoucherStatus.POSTED,
        )
        .order_by("-last_posted_at")
        .select_related("voucher_type")
        .first()
    )

    prev_je = (
        prev_voucher.journal_entries.order_by("-id").first()
        if prev_voucher
        else None
    )

    # Idempotent early-return: nothing to do if fingerprint unchanged
    if prev_voucher and getattr(prev_voucher, "fingerprint", None) == new_fp:
        return prev_voucher, prev_je

    # create new voucher and post it
    with transaction.atomic():
        voucher_date = _resolve_voucher_date(doc)
        voucher_no = generate_date_based_voucher_number(
            voucher_type=voucher_type,
            transaction_date=voucher_date,
        )

        voucher = Voucher.objects.create(
            voucher_no=voucher_no,
            voucher_type=voucher_type,
            voucher_date=voucher_date,
            status=VoucherStatus.DRAFT,
            created_by_id=user_id,
            updated_by_id=user_id,
            doc_content_type=ct,
            doc_object_id=doc.pk,
            corrected_from=prev_voucher if prev_voucher else None,
        )

        # Preserve the original business doc instance so any transient posting
        # context attached by the caller remains visible to the posting rule.
        voucher.business_doc = doc

    je = PostVoucherCommand(engine).execute(voucher, user)
    voucher.refresh_from_db()

    # Safety check: verify only one POSTED voucher exists
    posted_count = Voucher.objects.filter(
        doc_content_type=ct,
        doc_object_id=doc.pk,
        voucher_type=voucher_type,
        status=VoucherStatus.POSTED,
    ).count()

    if posted_count > 1:
        raise PostingError(
            f"Integrity violation: {posted_count} POSTED vouchers found for this document. "
            f"Expected exactly 1."
        )

    return voucher, je
