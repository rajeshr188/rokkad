from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable

from dateutil.relativedelta import relativedelta
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.notify_v2.models import (
    NotificationArtifact,
    NotificationBatch,
    NotificationEventType,
    NotificationJob,
    NotificationPolicy,
    NotificationRecipient,
    NotificationTemplate,
)
from apps.tenant_apps.notify_v2.renderers.pdf.girvi import render_girvi_notice_bundle

from .event_service import emit_event

DEFAULT_GIRVI_EVENT_KEY = "loan.first_reminder_due"

_EVENT_DEFAULTS = {
    "loan.first_reminder_due": {
        "name": "Loan First Reminder Due",
        "description": "Initial Girvi reminder notice for a selected batch of overdue or maturing loans.",
        "sort_order": 10,
    },
    "loan.second_reminder_due": {
        "name": "Loan Second Reminder Due",
        "description": "Second reminder notice for overdue Girvi loans that still require follow-up.",
        "sort_order": 15,
    },
    "loan.final_notice_due": {
        "name": "Loan Final Notice Due",
        "description": "Final printed notice before recovery escalation.",
        "sort_order": 20,
    },
    "loan.auction_notice_due": {
        "name": "Loan Auction Notice Due",
        "description": "Auction workflow notice for defaulted Girvi loans.",
        "sort_order": 30,
    },
}

DEFAULT_GIRVI_CHANNELS = (
    NotificationJob.Channel.LETTER,
    NotificationJob.Channel.POST,
    NotificationJob.Channel.EMAIL,
    NotificationJob.Channel.SMS,
    NotificationJob.Channel.WHATSAPP,
)


@dataclass(slots=True)
class GirviReminderBatchPreview:
    event_key: str
    channel: str
    loan_count: int
    borrower_count: int
    grouped_loans: list[dict[str, Any]]
    selection_snapshot: list[dict[str, Any]]


@dataclass(slots=True)
class GirviReminderBatchResult:
    batch: NotificationBatch
    preview: GirviReminderBatchPreview
    recipients: list[NotificationRecipient]
    events: list[Any]
    jobs: list[NotificationJob]
    template: NotificationTemplate


def _resolve_due_date(loan):
    due_date = getattr(loan, "maturity_date", None)
    if due_date:
        return due_date.date() if hasattr(due_date, "date") else due_date

    loan_date = getattr(loan, "loan_date", None)
    if not loan_date:
        return None

    base_date = loan_date.date() if hasattr(loan_date, "date") else loan_date
    tenure = int(getattr(loan, "tenure", 0) or 0)
    return base_date + relativedelta(months=tenure)


def _resolve_amount(loan) -> Decimal:
    amount = getattr(loan, "get_loan_amount", None)
    if callable(amount):
        amount = amount()
    elif amount is None:
        amount = getattr(loan, "loanamount", None)

    if amount in (None, ""):
        return Decimal("0")
    return Decimal(str(amount))


def _borrower_name(borrower) -> str:
    if borrower is None:
        return "Unknown"
    for attr in ("name", "fullname", "full_name"):
        value = getattr(borrower, attr, None)
        if value:
            return str(value)
    first = getattr(borrower, "firstname", "")
    last = getattr(borrower, "lastname", "")
    full = f"{first} {last}".strip()
    return full or str(borrower)


def _borrower_email(borrower) -> str:
    return (getattr(borrower, "email", None) or "").strip()


def _borrower_phone(borrower) -> str:
    for attr in ("phone", "mobile", "contact", "phone_number"):
        value = getattr(borrower, attr, None)
        if value:
            return str(value).strip()
    return ""


def _borrower_address_payload(borrower) -> dict[str, Any]:
    address_obj = getattr(borrower, "address", None)
    if not address_obj:
        return {}
    if isinstance(address_obj, dict):
        return address_obj
    return {"display": str(address_obj)}


def _borrower_customer_instance(borrower):
    meta = getattr(borrower, "_meta", None)
    if meta and getattr(meta, "label_lower", "") == "contact.customer" and getattr(
        borrower, "pk", None
    ):
        return borrower
    return None


def _build_selection_snapshot(loans: Iterable[Any]) -> list[dict[str, Any]]:
    return [
        {
            "pk": getattr(loan, "pk", None),
            "loan_id": getattr(loan, "loan_id", str(getattr(loan, "pk", ""))),
            "borrower_name": _borrower_name(getattr(loan, "borrower", None)),
        }
        for loan in loans
    ]


def ensure_girvi_batch_defaults(
    *,
    event_key: str = DEFAULT_GIRVI_EVENT_KEY,
    channel: str = NotificationJob.Channel.LETTER,
):
    defaults = _EVENT_DEFAULTS.get(
        event_key,
        {
            "name": event_key.replace(".", " ").title(),
            "description": "Notify V2 event type for Girvi batch reminders.",
            "sort_order": 99,
        },
    )
    event_type, _ = NotificationEventType.objects.update_or_create(
        key=event_key,
        defaults={
            "name": defaults["name"],
            "domain": NotificationEventType.Domain.LOAN,
            "description": defaults["description"],
            "payload_schema": {
                "customer": {"name": "string"},
                "loans": [{"loan_id": "string", "amount": "string"}],
                "loan_count": "integer",
                "total_amount": "string",
            },
            "sort_order": defaults["sort_order"],
            "is_active": True,
        },
    )
    policy, _ = NotificationPolicy.objects.update_or_create(
        event_type=event_type,
        channel=channel,
        defaults={
            "priority": 10,
            "is_required": channel in {NotificationJob.Channel.LETTER, NotificationJob.Channel.POST},
            "batch_enabled": True,
            "is_active": True,
        },
    )
    renderer_type = (
        NotificationTemplate.RendererType.PDF
        if channel in {NotificationTemplate.Channel.LETTER, NotificationTemplate.Channel.POST}
        else NotificationTemplate.RendererType.DJANGO
    )
    template_defaults = {
        "renderer_type": renderer_type,
        "name": f"{event_type.name} {channel.title()} Template",
        "subject_template": event_type.name,
        "body_template": (
            ""
            if renderer_type == NotificationTemplate.RendererType.PDF
            else "Dear {{ customer.name }}, this is a reminder regarding {{ loan_count }} loan(s)."
        ),
        "layout_key": event_key if renderer_type == NotificationTemplate.RendererType.PDF else "",
        "sample_payload": {
            "customer": {"name": "Asha"},
            "loans": [{"loan_id": "GL-001", "amount": "1000.00"}],
            "loan_count": 1,
            "total_amount": "1000.00",
        },
        "is_active": True,
    }
    template, _ = NotificationTemplate.objects.get_or_create(
        event_type=event_type,
        channel=channel,
        locale="en",
        version=1,
        defaults=template_defaults,
    )
    return event_type, policy, template


def seed_girvi_batch_defaults(*, event_keys=None, channels=None):
    event_keys = tuple(event_keys or _EVENT_DEFAULTS.keys())
    channels = tuple(channels or DEFAULT_GIRVI_CHANNELS)

    seeded = []
    for event_key in event_keys:
        for channel in channels:
            seeded.append(
                ensure_girvi_batch_defaults(
                    event_key=event_key,
                    channel=channel,
                )
            )
    return seeded


def preview_girvi_reminder_batch(
    *,
    loans: Iterable[Any],
    event_key: str = DEFAULT_GIRVI_EVENT_KEY,
    channel: str = NotificationJob.Channel.LETTER,
) -> GirviReminderBatchPreview:
    loan_list = list(loans or [])
    if not loan_list:
        raise ValueError("At least one loan is required to build a notify_v2 batch.")

    grouped = OrderedDict()
    for loan in loan_list:
        borrower = getattr(loan, "borrower", None)
        borrower_key = getattr(borrower, "pk", None) or id(borrower)
        bucket = grouped.setdefault(
            borrower_key,
            {
                "borrower": borrower,
                "loans": [],
            },
        )
        bucket["loans"].append(loan)

    grouped_loans = list(grouped.values())
    return GirviReminderBatchPreview(
        event_key=event_key,
        channel=channel,
        loan_count=len(loan_list),
        borrower_count=len(grouped_loans),
        grouped_loans=grouped_loans,
        selection_snapshot=_build_selection_snapshot(loan_list),
    )


def _build_payload(*, borrower, loans: list[Any], event_key: str) -> dict[str, Any]:
    loan_rows = []
    total_amount = Decimal("0")
    for loan in loans:
        amount = _resolve_amount(loan)
        total_amount += amount
        due_date = _resolve_due_date(loan)
        loan_rows.append(
            {
                "pk": getattr(loan, "pk", None),
                "loan_id": getattr(loan, "loan_id", str(getattr(loan, "pk", ""))),
                "amount": str(amount),
                "due_date": due_date.isoformat() if hasattr(due_date, "isoformat") else due_date,
            }
        )

    return {
        "event_key": event_key,
        "customer": {
            "name": _borrower_name(borrower),
            "email": _borrower_email(borrower),
            "phone": _borrower_phone(borrower),
        },
        "loans": loan_rows,
        "loan_count": len(loan_rows),
        "total_amount": str(total_amount),
        "generated_at": timezone.now().isoformat(),
    }


def create_girvi_reminder_batch(
    *,
    loans: Iterable[Any],
    created_by=None,
    event_key: str = DEFAULT_GIRVI_EVENT_KEY,
    channel: str = NotificationJob.Channel.LETTER,
    batch_name: str | None = None,
    notes: str = "",
) -> GirviReminderBatchResult:
    preview = preview_girvi_reminder_batch(
        loans=loans,
        event_key=event_key,
        channel=channel,
    )
    event_type, _policy, template = ensure_girvi_batch_defaults(
        event_key=event_key,
        channel=channel,
    )

    saved_user = created_by if getattr(created_by, "pk", None) else None
    batch_name = batch_name or f"Girvi Reminder Batch {timezone.now():%Y-%m-%d %H:%M}"

    recipients: list[NotificationRecipient] = []
    events = []
    jobs: list[NotificationJob] = []

    with transaction.atomic():
        batch = NotificationBatch.objects.create(
            name=batch_name[:150],
            event_type=event_type,
            created_by=saved_user,
            selection_snapshot=preview.selection_snapshot,
            notes=notes,
        )

        for grouped in preview.grouped_loans:
            borrower = grouped["borrower"]
            customer_instance = _borrower_customer_instance(borrower)
            recipient = NotificationRecipient.objects.create(
                customer=customer_instance,
                name_snapshot=_borrower_name(borrower),
                email=_borrower_email(borrower),
                phone=_borrower_phone(borrower),
                postal_address_json=_borrower_address_payload(borrower),
            )
            payload = _build_payload(
                borrower=borrower,
                loans=grouped["loans"],
                event_key=event_key,
            )
            event = emit_event(
                recipient=recipient,
                event_type=event_type,
                payload=payload,
                batch=batch,
                source_app="girvi",
                source_model="GivenLoan",
                source_pk=getattr(grouped["loans"][0], "pk", ""),
            )
            job = NotificationJob.objects.create(
                event=event,
                batch=batch,
                channel=channel,
                template=template,
            )
            recipients.append(recipient)
            events.append(event)
            jobs.append(job)

        batch.job_count = len(jobs)
        batch.save(update_fields=["job_count", "modified"])

    return GirviReminderBatchResult(
        batch=batch,
        preview=preview,
        recipients=recipients,
        events=events,
        jobs=jobs,
        template=template,
    )


def _load_loans_from_batch(batch: NotificationBatch):
    snapshot = batch.selection_snapshot or []
    loan_pks = [row.get("pk") for row in snapshot if isinstance(row, dict) and row.get("pk")]
    if not loan_pks:
        return []

    from apps.tenant_apps.girvi.models import GivenLoan

    return list(GivenLoan.objects.filter(pk__in=loan_pks).select_related("borrower"))


def render_batch_pdf(batch: NotificationBatch, *, loans: Iterable[Any] | None = None):
    loan_list = list(loans) if loans is not None else _load_loans_from_batch(batch)
    if not loan_list:
        return None

    template = (
        NotificationTemplate.objects.filter(
            event_type=batch.event_type,
            channel__in=[NotificationTemplate.Channel.LETTER, NotificationTemplate.Channel.POST],
            is_active=True,
        )
        .order_by("channel", "-version")
        .first()
    )

    pdf_bytes = render_girvi_notice_bundle(
        loans=loan_list,
        template=template,
        event_key=batch.event_type.key,
    )
    if not pdf_bytes:
        return None

    layout_key = getattr(template, "layout_key", "") or batch.event_type.key
    batch_id = getattr(batch, "pk", "preview") or "preview"

    with transaction.atomic():
        printable_jobs = list(
            batch.jobs.filter(
                channel__in=[NotificationJob.Channel.LETTER, NotificationJob.Channel.POST]
            )
        )
        for index, job in enumerate(printable_jobs, start=1):
            artifact = NotificationArtifact.objects.create(
                job=job,
                artifact_type=NotificationArtifact.ArtifactType.PDF,
                rendered_text=f"Girvi batch PDF for {len(loan_list)} loan(s).",
                metadata={
                    "batch_id": batch_id,
                    "loan_count": len(loan_list),
                    "layout_key": layout_key,
                    "bundle": True,
                },
            )
            filename = f"notify_v2_batch_{batch_id}_job_{getattr(job, 'pk', index) or index}.pdf"
            artifact_file = getattr(artifact, "file", None)
            if artifact_file is not None and hasattr(artifact_file, "save"):
                artifact_file.save(filename, ContentFile(pdf_bytes), save=False)
            if hasattr(artifact, "save"):
                try:
                    artifact.save()
                except Exception:
                    pass
            job.mark_rendered(message=f"Batch PDF generated for {len(loan_list)} loan(s).")
        batch.mark_rendered()

    return pdf_bytes
