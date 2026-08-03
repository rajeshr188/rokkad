"""Concrete Loans-to-DEA outbox delivery adapter."""

from dataclasses import dataclass

from apps.tenant_apps.dea import facade as dea_facade
from apps.tenant_apps.loans.domain import TransactionKind


class UnsupportedLoanAccountingEvent(ValueError):
    pass


@dataclass(frozen=True)
class OperationalOnlyDeliveryReceipt:
    dea_voucher_id: int | None = None
    dea_journal_entry_id: int | None = None


def deliver_loan_accounting_event(event):
    """Dispatch a durable loan source event through DEA's public facade."""
    if event.event_kind == TransactionKind.DISBURSAL.value:
        return dea_facade.post_pawn_loan_disbursal_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.REPAYMENT.value:
        return dea_facade.post_pawn_loan_repayment_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.INTEREST_ACCRUAL.value:
        if (event.payload.get("accrual") or {}).get("accounting_recognition") == "CASH":
            return OperationalOnlyDeliveryReceipt()
        return dea_facade.post_pawn_loan_interest_accrual_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.INTEREST_CAPITALIZATION.value:
        if (event.payload.get("capitalization") or {}).get(
            "accounting_recognition"
        ) == "CASH":
            return OperationalOnlyDeliveryReceipt()
        return dea_facade.post_pawn_loan_interest_capitalization_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.REVERSAL.value:
        return dea_facade.reverse_pawn_loan_accounting_event(
            event,
            actor=event.created_by,
        )
    raise UnsupportedLoanAccountingEvent(
        f"No DEA delivery adapter is registered for {event.event_kind}."
    )
