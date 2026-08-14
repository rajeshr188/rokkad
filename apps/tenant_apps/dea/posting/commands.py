# accounting/posting/commands.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .context import PostingContext, compute_fingerprint
from .engine import BasePostingEngine
from .registry import registry
from .types import RuleNotFoundError
from ..models import AccountingPeriod, Voucher, VoucherLine, VoucherStatus
from ..models.audit import AccountingAuditEvent
from ..services.audit import AuditService
from ..services.materialize_journal import materialize_journal_from_voucher_lines


class PostVoucherCommand:
    """
    Entry point for outside world.  (views / signals / services)
    """

    def __init__(self, engine: BasePostingEngine):
        self.engine = engine

    def execute(self, voucher, user):
        voucher_type = getattr(voucher.voucher_type, "name", voucher.voucher_type)
        try:
            registry.get(voucher_type)
        except RuleNotFoundError:
            if voucher.lines.exists():
                return self._post_stored_voucher_lines(voucher, user)
            raise

        ctx = PostingContext(
            voucher=voucher,
            doc=getattr(voucher, "business_doc", None),
            user_id=getattr(user, "id", None),
        )
        return self.engine.post(ctx)

    def _post_stored_voucher_lines(self, voucher, user):
        with transaction.atomic():
            locked_voucher = (
                Voucher.objects.select_for_update()
                .select_related("voucher_type")
                .get(pk=voucher.pk)
            )
            existing_je = locked_voucher.journal_entries.order_by("-id").first()
            if locked_voucher.status == VoucherStatus.POSTED and existing_je:
                return existing_je
            if locked_voucher.status != VoucherStatus.DRAFT:
                raise ValidationError(
                    f"Cannot post {locked_voucher.status} voucher. "
                    "Only DRAFT vouchers can be posted."
                )

            period = AccountingPeriod.objects.get_period_for_date(
                locked_voucher.voucher_date
            )
            if not period:
                raise ValidationError(
                    f"No accounting period found for voucher date {locked_voucher.voucher_date}"
                )
            if not period.can_modify_transactions():
                raise ValidationError(
                    f"Cannot post voucher {locked_voucher.voucher_no} dated "
                    f"{locked_voucher.voucher_date}: accounting period "
                    f"'{period.name}' is {period.status}."
                )

            if not locked_voucher.lines.exists():
                raise ValidationError("Voucher has no lines to post.")

            previous_status = locked_voucher.status
            fingerprint = compute_fingerprint(
                _stored_line_fingerprint_payload(locked_voucher),
                "manual-voucher-lines-v1",
            )
            if locked_voucher.fingerprint == fingerprint and existing_je:
                return existing_je

            journal_entry = materialize_journal_from_voucher_lines(
                voucher=locked_voucher,
                posted_by_id=getattr(user, "id", None),
                period=period,
            )
            locked_voucher.fingerprint = fingerprint
            locked_voucher.last_posted_at = timezone.now()
            locked_voucher.status = VoucherStatus.POSTED
            locked_voucher.save(
                update_fields=["fingerprint", "last_posted_at", "status"]
            )
            _log_manual_line_post(
                voucher=locked_voucher,
                actor=user,
                previous_status=previous_status,
                journal_entry=journal_entry,
            )
            return journal_entry


def _stored_line_fingerprint_payload(voucher):
    lines = (
        VoucherLine.objects.filter(voucher=voucher)
        .order_by("line_no", "id")
        .values(
            "line_no",
            "side",
            "ledger_id",
            "account_id",
            "amount",
            "amount_currency",
            "amount_base",
            "amount_base_currency",
            "exchange_rate",
            "xact_type_ext",
            "tax_code",
        )
    )
    return {
        "posting_source": "stored_voucher_lines",
        "voucher_no": voucher.voucher_no,
        "voucher_type": voucher.voucher_type.name,
        "voucher_date": str(voucher.voucher_date),
        "narration": voucher.narration or "",
        "lines": list(lines),
    }


def _log_manual_line_post(*, voucher, actor, previous_status, journal_entry):
    try:
        AuditService.log_event(
            event_type=AccountingAuditEvent.EventType.VOUCHER_POSTED,
            actor=actor,
            obj=voucher,
            payload_before={"status": previous_status},
            payload_after={
                "status": voucher.status,
                "fingerprint": voucher.fingerprint,
                "posted_at": (
                    voucher.last_posted_at.isoformat()
                    if voucher.last_posted_at
                    else None
                ),
                "je_id": journal_entry.pk if journal_entry else None,
                "posting_source": "stored_voucher_lines",
            },
            description=f"Posted manual voucher {voucher.voucher_no} from stored lines",
        )
    except Exception:
        pass
