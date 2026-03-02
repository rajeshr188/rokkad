from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.dea.posting.commands import PostVoucherCommand
from apps.tenant_apps.dea.posting.context import PostingContext, compute_fingerprint
from apps.tenant_apps.dea.posting.registry import registry
from apps.tenant_apps.dea.posting.types import PostingError
from apps.tenant_apps.dea.models import Voucher, VoucherStatus, VoucherType


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
            raise ValueError(f"VoucherType with name '{voucher_type_input}' not found")

    if isinstance(voucher_type_input, int):
        try:
            return VoucherType.objects.get(pk=voucher_type_input)
        except VoucherType.DoesNotExist:
            raise ValueError(f"VoucherType with pk {voucher_type_input} not found")

    raise ValueError(
        f"Invalid voucher_type input: expected VoucherType, str, or int, got {type(voucher_type_input)}"
    )


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
            doc_content_type=ct, doc_object_id=doc.pk, status=VoucherStatus.POSTED
        )
        .order_by("-last_posted_at")
        .select_related("voucher_type")
        .first()
    )

    prev_je = getattr(prev_voucher, "journal_entry", None) if prev_voucher else None

    # Idempotent early-return: nothing to do if fingerprint unchanged
    if prev_voucher and getattr(prev_voucher, "fingerprint", None) == new_fp:
        return prev_voucher, prev_je

    # create new voucher and post it
    with transaction.atomic():
        voucher = Voucher.objects.create(
            voucher_no="",
            voucher_type=voucher_type,
            voucher_date=getattr(doc, "created_at", None) or None,
            status=VoucherStatus.DRAFT,
            created_by_id=user_id,
            doc_content_type=ct,
            doc_object_id=doc.pk,
            corrected_from=prev_voucher if prev_voucher else None,
            fingerprint="",
        )

    je = PostVoucherCommand(engine).execute(voucher, user)

    # Safety check: verify only one POSTED voucher exists
    posted_count = Voucher.objects.filter(
        doc_content_type=ct,
        doc_object_id=doc.pk,
        status=VoucherStatus.POSTED,
    ).count()

    if posted_count > 1:
        raise PostingError(
            f"Integrity violation: {posted_count} POSTED vouchers found for this document. "
            f"Expected exactly 1."
        )

    return voucher, je
