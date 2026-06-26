"""Synchronous DEA adapter for Girvi accounting integration.

This is the single runtime boundary Girvi services should use for current
DEA posting/read behavior. It can later become an event publisher without
forcing Girvi views and services to know DEA internals.
"""

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

dea_facade = None

# Contract metadata for outbox-backed posting cutover.
EVENT_CONTRACT_VERSION = 2
GIRVI_POSTING_EVENT_TYPES = {
    "disbursal": "DISBURSAL",
    "taken_loan_activation": "TAKEN_LOAN_ACTIVATION",
    "repayment": "REPAYMENT",
    "taken_loan_repayment": "TAKEN_LOAN_REPAYMENT",
    "release": "RELEASE",
    "accrual": "ACCRUAL",
    "auction_recovery": "AUCTION_RECOVERY",
    "sale_recovery": "SALE_RECOVERY",
    "renewal": "RENEWAL",
    "write_off": "WRITE_OFF",
    "reversal": "REVERSAL",
}
GIRVI_POSTING_EVENT_CONTRACTS = {
    "disbursal": {
        "source_model": "GivenLoan",
        "expected_dea_rule": "given_loan_disbursal",
        "economic_fields": ("principal_amount", "cash_account", "borrower_account", "posting_date"),
    },
    "taken_loan_activation": {
        "source_model": "TakenLoan",
        "expected_dea_rule": "taken_loan_activation",
        "economic_fields": ("principal_amount", "cash_account", "lender_account", "posting_date"),
    },
    "repayment": {
        "source_model": "PaymentVoucher",
        "expected_dea_rule": "given_loan_receipt",
        "economic_fields": ("total_amount", "principal_amount", "interest_amount", "payment_date"),
    },
    "taken_loan_repayment": {
        "source_model": "PaymentVoucher",
        "expected_dea_rule": "taken_loan_payment",
        "economic_fields": ("total_amount", "principal_amount", "interest_amount", "payment_date"),
    },
    "release": {
        "source_model": "Release",
        "expected_dea_rule": "given_loan_release",
        "economic_fields": ("release_date", "settlement_amount", "principal_amount", "interest_amount"),
    },
    "accrual": {
        "source_model": "LoanInterestAccrual",
        "expected_dea_rule": "given_loan_interest_accrual",
        "economic_fields": ("period_start", "period_end", "interest_amount", "posting_date"),
    },
    "auction_recovery": {
        "source_model": "GivenLoan",
        "expected_dea_rule": "girvi_auction_recovery",
        "economic_fields": ("recovery_amount", "posting_date", "residual_outstanding"),
    },
    "sale_recovery": {
        "source_model": "GivenLoan",
        "expected_dea_rule": "girvi_sale_recovery",
        "economic_fields": ("sale_amount", "expenses_amount", "posting_date", "residual_outstanding"),
    },
    "renewal": {
        "source_model": "LoanRenewal",
        "expected_dea_rule": "girvi_renewal",
        "economic_fields": ("source_loan_id", "renewed_loan_id", "paid_amount", "top_up_amount", "posting_date"),
    },
    "write_off": {
        "source_model": "GivenLoan",
        "expected_dea_rule": "girvi_write_off",
        "economic_fields": ("write_off_amount", "posting_date", "reason"),
    },
    "reversal": {
        "source_model": "PaymentVoucher",
        "expected_dea_rule": "dea_reversal",
        "economic_fields": ("source_voucher_id", "reversal_date", "reason"),
    },
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


def get_payment_voucher_model():
    """Return the DEA PaymentVoucher model class via lazy app lookup."""
    return apps.get_model("dea", "PaymentVoucher")


def _serialize_economic_value(value):
    if value is None:
        return None
    amount = getattr(value, "amount", None)
    currency = getattr(value, "currency", None)
    if amount is not None:
        payload = {"amount": str(amount)}
        if currency is not None:
            payload["currency"] = str(currency)
        return payload
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _source_ref(source_document):
    if source_document is None:
        return None
    meta = getattr(source_document, "_meta", None)
    return {
        "app": getattr(meta, "app_label", ""),
        "model": getattr(meta, "model_name", ""),
        "pk": str(getattr(source_document, "pk", "")),
    }


def _call_or_value(obj, name, default=None):
    value = getattr(obj, name, default)
    if callable(value):
        return value()
    return value


def build_source_document_economic_payload(*, event_key, source_document):
    """Build deterministic economic payload fields for a Girvi posting source."""

    if event_key not in GIRVI_POSTING_EVENT_CONTRACTS:
        raise ValidationError(f"Unknown Girvi posting event key: {event_key}")

    payload = {
        "source_ref": _source_ref(source_document),
    }

    if event_key in {"disbursal", "taken_loan_activation"}:
        party = getattr(source_document, "borrower", None) or getattr(
            source_document, "lender", None
        )
        party_ref = getattr(source_document, "borrower_party", None) or getattr(
            source_document, "lender_party", None
        )
        payload.update(
            {
                "loan_id": getattr(source_document, "loan_id", ""),
                "principal_amount": _serialize_economic_value(
                    _call_or_value(source_document, "get_loan_amount", default=None)
                ),
                "interest_amount": _serialize_economic_value(
                    _call_or_value(source_document, "get_interest_amount", default=None)
                ),
                "posting_date": _serialize_economic_value(
                    getattr(source_document, "loan_date", None)
                ),
                "party_id": str(getattr(party, "pk", "")) if party else "",
                "party_ref": _source_ref(party_ref) if party_ref else None,
            }
        )
        return payload

    if event_key in {"repayment", "taken_loan_repayment", "reversal"}:
        payload.update(
            {
                "payment_id": getattr(source_document, "payment_id", ""),
                "direction": getattr(source_document, "direction", ""),
                "total_amount": _serialize_economic_value(
                    getattr(source_document, "amount_in_base_currency", None)
                    or getattr(source_document, "total_amount", None)
                ),
                "principal_amount": _serialize_economic_value(
                    getattr(source_document, "principal_amount", None)
                ),
                "interest_amount": _serialize_economic_value(
                    getattr(source_document, "interest_amount", None)
                ),
                "payment_date": _serialize_economic_value(
                    getattr(source_document, "payment_date", None)
                ),
                "source_document_ref": _source_ref(
                    getattr(source_document, "source_document", None)
                ),
            }
        )
        return payload

    if event_key == "release":
        loan = getattr(source_document, "loan", None)
        try:
            from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance

            settlement = build_loan_settlement_balance(loan) if loan else None
        except Exception:
            settlement = None
        payload.update(
            {
                "release_id": getattr(source_document, "release_id", ""),
                "loan_ref": _source_ref(loan),
                "release_date": _serialize_economic_value(
                    getattr(source_document, "release_date", None)
                ),
                "settlement_amount": _serialize_economic_value(
                    getattr(settlement, "total_outstanding", None)
                ),
                "principal_amount": _serialize_economic_value(
                    getattr(settlement, "principal_due", None)
                ),
                "interest_amount": _serialize_economic_value(
                    getattr(settlement, "interest_due", None)
                ),
            }
        )
        return payload

    if event_key == "accrual":
        payload.update(
            {
                "loan_ref": _source_ref(getattr(source_document, "loan", None)),
                "period_start": _serialize_economic_value(
                    getattr(source_document, "period_start", None)
                ),
                "period_end": _serialize_economic_value(
                    getattr(source_document, "period_end", None)
                ),
                "interest_amount": _serialize_economic_value(
                    getattr(source_document, "accrued_amount", None)
                ),
                "posting_date": _serialize_economic_value(
                    getattr(source_document, "recognized_at", None)
                ),
            }
        )
        return payload

    if event_key == "renewal":
        payload.update(
            {
                "source_loan_id": getattr(source_document, "source_loan_id", None),
                "renewed_loan_id": getattr(source_document, "renewed_loan_id", None),
                "posting_date": _serialize_economic_value(
                    getattr(source_document, "renewal_date", None)
                ),
                "paid_amount": _serialize_economic_value(
                    (getattr(source_document, "principal_paid", 0) or 0)
                    + (getattr(source_document, "interest_paid", 0) or 0)
                ),
                "top_up_amount": _serialize_economic_value(
                    getattr(source_document, "requested_extra_amount", None)
                ),
            }
        )
        return payload

    payload.update(
        {
            "amount": _serialize_economic_value(
                getattr(source_document, "recovery_amount", None)
                or getattr(source_document, "sale_amount", None)
                or getattr(source_document, "write_off_amount", None)
            ),
            "posting_date": _serialize_economic_value(
                getattr(source_document, "posting_date", None)
                or getattr(source_document, "updated_at", None)
            ),
            "reason": getattr(source_document, "reason", ""),
        }
    )
    return payload


def build_posting_idempotency_key(*, event_key, source_document):
    """Return a deterministic idempotency key for a Girvi posting event."""

    event_type = GIRVI_POSTING_EVENT_TYPES.get(event_key)
    if not event_type:
        raise ValidationError(f"Unknown Girvi posting event key: {event_key}")

    return (
        f"girvi:{EVENT_CONTRACT_VERSION}:"
        f"{event_type}:"
        f"{source_document._meta.app_label}:"
        f"{source_document._meta.model_name}:"
        f"{source_document.pk}"
    )


def build_posting_event_payload(*, event_key, source_document, payload, idempotency_key=None):
    """Build the canonical Girvi-to-DEA posting event contract payload."""

    event_type = GIRVI_POSTING_EVENT_TYPES.get(event_key)
    contract = GIRVI_POSTING_EVENT_CONTRACTS.get(event_key)
    if not event_type or not contract:
        raise ValidationError(f"Unknown Girvi posting event key: {event_key}")

    economic_payload = payload
    if economic_payload is None:
        economic_payload = build_source_document_economic_payload(
            event_key=event_key,
            source_document=source_document,
        )
    source = {
        "app": source_document._meta.app_label,
        "model": source_document._meta.model_name,
        "pk": str(source_document.pk),
    }
    dedupe_key = idempotency_key or build_posting_idempotency_key(
        event_key=event_key,
        source_document=source_document,
    )

    return {
        "contract_version": EVENT_CONTRACT_VERSION,
        "event_type": GIRVI_POSTING_EVENT_TYPES[event_key],
        "event_key": event_key,
        "idempotency_key": dedupe_key,
        "source": {
            **source,
            "expected_model": contract["source_model"],
        },
        "economic_payload": economic_payload,
        "payload": economic_payload,
        "expected_dea_rule": contract["expected_dea_rule"],
        "required_economic_fields": list(contract["economic_fields"]),
        "posting_boundary": {
            "girvi_owns": [
                "loan domain state",
                "source document identity",
                "collateral/custody state",
                "workflow decision",
            ],
            "dea_owns": [
                "voucher creation",
                "posting",
                "journal entries",
                "period locks",
                "reversals",
                "ledger reports",
            ],
        },
        "adapter_mode": "sync_runtime_outbox_ready",
    }


def enqueue_posting_event(*, event_key, source_document, dedupe_key, payload):
    """Draft outbox enqueue bridge used during sync+async parallel cutover."""

    from .outbox import enqueue_posting_event as enqueue

    event_payload = build_posting_event_payload(
        event_key=event_key,
        source_document=source_document,
        payload=payload,
        idempotency_key=dedupe_key,
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
    PaymentVoucher = get_payment_voucher_model()
    return {
        "total_payments": PaymentVoucher.objects.count(),
        "pending_payments": PaymentVoucher.objects.filter(posted=False).count(),
    }


def get_payment_voucher_posting_counts():
    """Return total/posted/pending PaymentVoucher counts for operational summaries."""
    PaymentVoucher = get_payment_voucher_model()
    return {
        "total": PaymentVoucher.objects.count(),
        "posted": PaymentVoucher.objects.filter(posted=True).count(),
        "pending": PaymentVoucher.objects.filter(posted=False).count(),
    }


def get_source_posting_status(source_document):
    """Return accounting posting status for a Girvi source via adapter-owned reads."""

    PaymentVoucher = get_payment_voucher_model()
    content_type = ContentType.objects.get_for_model(
        source_document,
        for_concrete_model=False,
    )
    payment_qs = PaymentVoucher.objects.filter(
        source_content_type=content_type,
        source_object_id=source_document.pk,
    )

    try:
        from apps.tenant_apps.girvi.models import (
            GirviPostingOutboxEvent,
            GirviPostingOutboxStatus,
        )

        outbox_qs = GirviPostingOutboxEvent.objects.filter(
            source_app=source_document._meta.app_label,
            source_model=source_document._meta.model_name,
            source_pk=str(source_document.pk),
        )
        failed_outbox_count = outbox_qs.filter(
            status__in=[
                GirviPostingOutboxStatus.FAILED,
                GirviPostingOutboxStatus.DEAD_LETTER,
            ]
        ).count()
        pending_outbox_count = outbox_qs.filter(
            status__in=[
                GirviPostingOutboxStatus.PENDING,
                GirviPostingOutboxStatus.PROCESSING,
            ]
        ).count()
    except Exception:
        failed_outbox_count = 0
        pending_outbox_count = 0

    posted_payment_count = payment_qs.filter(posted=True).count()
    pending_payment_count = payment_qs.filter(posted=False).count()
    total_payment_count = payment_qs.count()

    if failed_outbox_count:
        label = "Failed"
        badge_class = "bg-danger"
    elif pending_payment_count or pending_outbox_count:
        label = "Pending"
        badge_class = "bg-warning text-dark"
    elif posted_payment_count:
        label = "Posted"
        badge_class = "bg-success"
    else:
        label = "Not started"
        badge_class = "bg-secondary"

    return {
        "label": label,
        "badge_class": badge_class,
        "posted_payment_count": posted_payment_count,
        "pending_payment_count": pending_payment_count,
        "total_payment_count": total_payment_count,
        "failed_outbox_count": failed_outbox_count,
        "pending_outbox_count": pending_outbox_count,
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
    "build_posting_idempotency_key",
    "build_source_document_economic_payload",
    "create_and_post_voucher_for_doc",
    "create_payment_voucher",
    "get_payment_voucher_model",
    "get_payment_voucher_posting_counts",
    "get_source_posting_status",
    "enqueue_posting_event",
    "find_payment_by_marker",
    "GIRVI_POSTING_EVENT_TYPES",
    "GIRVI_POSTING_EVENT_CONTRACTS",
    "get_payment_voucher_counts",
    "get_loan_journal_entries",
    "has_other_posted_payments",
    "post_interest_accrual_batch",
    "post_payment_voucher",
    "resolve_customer_account",
    "reverse_payment_by_marker",
]
