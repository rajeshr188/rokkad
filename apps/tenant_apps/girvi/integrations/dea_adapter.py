"""Synchronous DEA adapter for Girvi accounting integration.

This is the single runtime boundary Girvi services should use for current
DEA posting/read behavior. It can later become an event publisher without
forcing Girvi views and services to know DEA internals.
"""

from django.apps import apps

dea_facade = None

# Draft P7 contract metadata for outbox-backed posting cutover.
EVENT_CONTRACT_VERSION = 1
GIRVI_POSTING_EVENT_TYPES = {
    "disbursal": "DISBURSAL",
    "repayment": "REPAYMENT",
    "release": "RELEASE",
    "accrual": "ACCRUAL",
    "auction_recovery": "AUCTION_RECOVERY",
    "sale_recovery": "SALE_RECOVERY",
}


def _facade():
    global dea_facade
    if dea_facade is None:
        from apps.tenant_apps.dea import facade as loaded_facade

        dea_facade = loaded_facade
    return dea_facade


def create_and_post_voucher_for_doc(source_document, **payment_kwargs):
    return _facade().create_and_post_payment(source_document, **payment_kwargs)


def create_payment_voucher(source_document, **payment_kwargs):
    PaymentVoucher = apps.get_model("dea", "PaymentVoucher")
    return PaymentVoucher.objects.create(
        source_document=source_document,
        **payment_kwargs,
    )


def build_posting_event_payload(*, event_key, source_document, payload):
    """Build draft outbox payload shape for Girvi posting events."""

    return {
        "contract_version": EVENT_CONTRACT_VERSION,
        "event_type": GIRVI_POSTING_EVENT_TYPES[event_key],
        "source": {
            "app": source_document._meta.app_label,
            "model": source_document._meta.model_name,
            "pk": str(source_document.pk),
        },
        "payload": payload or {},
    }


def enqueue_posting_event(*, event_key, source_document, dedupe_key, payload):
    """Draft outbox enqueue bridge used during sync+async parallel cutover."""

    from .outbox import enqueue_posting_event as enqueue

    event_payload = build_posting_event_payload(
        event_key=event_key,
        source_document=source_document,
        payload=payload,
    )
    return enqueue(
        event_type=event_payload["event_type"],
        dedupe_key=dedupe_key,
        payload=event_payload,
        source_model=event_payload["source"]["model"],
        source_pk=event_payload["source"]["pk"],
        contract_version=EVENT_CONTRACT_VERSION,
    )


def get_payment_voucher_counts():
    PaymentVoucher = apps.get_model("dea", "PaymentVoucher")
    return {
        "total_payments": PaymentVoucher.objects.count(),
        "pending_payments": PaymentVoucher.objects.filter(posted=False).count(),
    }


def find_payment_by_marker(source_document, marker):
    return _facade().find_payment_by_marker(source_document, marker)


def has_other_posted_payments(source_document, *, exclude_marker):
    return _facade().has_other_posted_payments(
        source_document,
        exclude_marker=exclude_marker,
    )


def post_payment_voucher(payment, user, **kwargs):
    return _facade().post_payment_voucher(payment, user, **kwargs)


def reverse_payment_by_marker(source_document, marker, user):
    return _facade().reverse_payment_by_marker(source_document, marker, user)


def resolve_customer_account(customer, **kwargs):
    return _facade().resolve_customer_account(customer, **kwargs)


def post_interest_accrual_batch(command, preview, created_rows, **kwargs):
    return _facade().post_interest_accrual_batch(
        command,
        preview,
        created_rows,
        **kwargs,
    )


def get_loan_journal_entries(loan):
    return _facade().get_loan_journal_entries(loan)


__all__ = [
    "build_posting_event_payload",
    "create_and_post_voucher_for_doc",
    "create_payment_voucher",
    "enqueue_posting_event",
    "find_payment_by_marker",
    "GIRVI_POSTING_EVENT_TYPES",
    "get_payment_voucher_counts",
    "get_loan_journal_entries",
    "has_other_posted_payments",
    "post_interest_accrual_batch",
    "post_payment_voucher",
    "resolve_customer_account",
    "reverse_payment_by_marker",
]
