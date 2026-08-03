"""Public DEA posting boundary for loan-domain accounting events."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc


@dataclass(frozen=True)
class LoanEventPostingReceipt:
    dea_voucher_id: int | None
    dea_journal_entry_id: int | None


def post_pawn_loan_disbursal_event(source_event, *, actor=None):
    """Idempotently convert one durable PawnLoan disbursal event into DEA effects."""
    if getattr(source_event, "event_kind", None) != "DISBURSAL":
        raise ValidationError("Only a PawnLoan disbursal event is supported here.")
    voucher, journal_entry = create_and_post_voucher_for_doc(
        doc=source_event,
        user=actor or getattr(source_event, "created_by", None),
        voucher_type_input="PAWN_LOAN_DISBURSAL",
        engine=DjangoPostingEngine(),
    )
    if journal_entry is None:
        raise ValidationError("DEA did not return a journal entry for the disbursal.")
    return LoanEventPostingReceipt(
        dea_voucher_id=voucher.pk,
        dea_journal_entry_id=journal_entry.pk,
    )


def post_pawn_loan_repayment_event(source_event, *, actor=None):
    """Idempotently convert one durable PawnLoan repayment into DEA effects."""
    if getattr(source_event, "event_kind", None) != "REPAYMENT":
        raise ValidationError("Only a PawnLoan repayment event is supported here.")
    voucher, journal_entry = create_and_post_voucher_for_doc(
        doc=source_event,
        user=actor or getattr(source_event, "created_by", None),
        voucher_type_input="PAWN_LOAN_REPAYMENT",
        engine=DjangoPostingEngine(),
    )
    if journal_entry is None:
        raise ValidationError("DEA did not return a journal entry for the repayment.")
    return LoanEventPostingReceipt(voucher.pk, journal_entry.pk)


def post_pawn_loan_interest_accrual_event(source_event, *, actor=None):
    return _post_interest_event(
        source_event,
        event_kind="INTEREST_ACCRUAL",
        voucher_type="PAWN_LOAN_INTEREST_ACCRUAL",
        actor=actor,
    )


def post_pawn_loan_interest_capitalization_event(source_event, *, actor=None):
    return _post_interest_event(
        source_event,
        event_kind="INTEREST_CAPITALIZATION",
        voucher_type="PAWN_LOAN_INTEREST_CAPITALIZATION",
        actor=actor,
    )


def _post_interest_event(source_event, *, event_kind, voucher_type, actor):
    if getattr(source_event, "event_kind", None) != event_kind:
        raise ValidationError(f"Only a PawnLoan {event_kind} event is supported here.")
    voucher, journal_entry = create_and_post_voucher_for_doc(
        doc=source_event,
        user=actor or getattr(source_event, "created_by", None),
        voucher_type_input=voucher_type,
        engine=DjangoPostingEngine(),
    )
    if journal_entry is None:
        raise ValidationError("DEA did not return a journal entry for the interest event.")
    return LoanEventPostingReceipt(voucher.pk, journal_entry.pk)


def reverse_pawn_loan_accounting_event(source_event, *, actor=None):
    """Idempotently reverse the DEA effect linked to a Loans reversal event."""
    from apps.tenant_apps.dea.models import Voucher
    from apps.tenant_apps.dea.services.reversal import reverse_posted_voucher

    if getattr(source_event, "event_kind", None) != "REVERSAL":
        raise ValidationError("Only a PawnLoan reversal event is supported here.")
    original = getattr(source_event, "reversal_of", None)
    if original is None:
        raise ValidationError("PawnLoan reversal is missing its original source event.")
    reversal = source_event.payload.get("reversal") or {}
    if reversal.get("original_event_id") != original.pk:
        raise ValidationError("PawnLoan reversal source identity does not match its link.")
    original_outbox = original.outbox
    if original_outbox.dea_voucher_id is None:
        return LoanEventPostingReceipt(None, None)
    try:
        voucher = Voucher.objects.get(pk=original_outbox.dea_voucher_id)
    except Voucher.DoesNotExist as exc:
        raise ValidationError("Original PawnLoan DEA voucher was not found.") from exc
    result = reverse_posted_voucher(
        voucher=voucher,
        actor=actor or getattr(source_event, "created_by", None),
        reason=reversal.get("reason") or "",
        reversal_date=source_event.effective_date,
        source_action=f"pawn_loan_event_reversal:{source_event.pk}",
    )
    reversal_entry = result.reversal_journal_entry
    if reversal_entry is None:
        raise ValidationError("DEA did not return a reversal journal entry.")
    return LoanEventPostingReceipt(voucher.pk, reversal_entry.pk)
