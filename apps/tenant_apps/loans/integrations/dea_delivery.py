"""Concrete Loans-to-DEA outbox delivery adapter."""

from apps.tenant_apps.dea import facade as dea_facade
from apps.tenant_apps.loans.domain import TransactionKind


class UnsupportedLoanAccountingEvent(ValueError):
    pass


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
    raise UnsupportedLoanAccountingEvent(
        f"No DEA delivery adapter is registered for {event.event_kind}."
    )
