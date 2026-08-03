"""Public DEA posting boundary for loan-domain accounting events."""

from dataclasses import dataclass

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc


@dataclass(frozen=True)
class LoanEventPostingReceipt:
    dea_voucher_id: int
    dea_journal_entry_id: int


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
