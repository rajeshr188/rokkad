"""Concrete Loans-to-DEA outbox delivery adapter."""

from dataclasses import dataclass
from decimal import Decimal

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
    if event.event_kind == TransactionKind.RELEASE_RECEIPT.value:
        values = event.payload.get("values") or {}
        if not any(Decimal(str(values.get(key, "0"))) for key in (
            "principal",
            "interest",
            "fees",
        )):
            return OperationalOnlyDeliveryReceipt()
        return dea_facade.post_pawn_loan_release_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.AUCTION_RECOVERY.value:
        return dea_facade.post_pawn_loan_auction_recovery_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.RENEWAL_SETTLEMENT.value:
        from apps.tenant_apps.loans.models import PawnLoanAccountingEvent

        values = event.payload.get("values") or {}
        renewal = event.payload.get("renewal") or {}
        catch_up_event_id = renewal.get("catch_up_event_id")
        if catch_up_event_id:
            try:
                catch_up = PawnLoanAccountingEvent.objects.select_related(
                    "outbox"
                ).get(
                    pk=catch_up_event_id,
                    loan_id=event.loan_id,
                    event_kind=TransactionKind.INTEREST_ACCRUAL.value,
                )
            except PawnLoanAccountingEvent.DoesNotExist as exc:
                raise UnsupportedLoanAccountingEvent(
                    "Renewal settlement is missing its catch-up accrual event."
                ) from exc
            if catch_up.outbox.status != "POSTED":
                raise UnsupportedLoanAccountingEvent(
                    "Renewal catch-up accrual must post before settlement."
                )
        if (
            Decimal(str(values.get("interest", "0"))) == 0
            and Decimal(str(values.get("fees", "0"))) == 0
            and Decimal(str(renewal.get("successor_advance_interest", "0"))) == 0
            and Decimal(str(renewal.get("successor_deducted_fees", "0"))) == 0
            and Decimal(str(renewal.get("source_control_principal", "0")))
            == Decimal(str(renewal.get("successor_control_principal", "0")))
        ):
            return OperationalOnlyDeliveryReceipt()
        return dea_facade.post_pawn_loan_renewal_event(
            event,
            actor=event.created_by,
        )
    if event.event_kind == TransactionKind.RENEWAL_OPENING.value:
        from apps.tenant_apps.loans.models import PawnLoanAccountingEvent

        settlement_event_id = (event.payload.get("renewal") or {}).get(
            "settlement_event_id"
        )
        try:
            settlement = PawnLoanAccountingEvent.objects.select_related("outbox").get(
                pk=settlement_event_id,
                loan__workspace_id=event.loan.workspace_id,
                event_kind=TransactionKind.RENEWAL_SETTLEMENT.value,
            )
        except PawnLoanAccountingEvent.DoesNotExist as exc:
            raise UnsupportedLoanAccountingEvent(
                "Renewal opening is missing its settlement event."
            ) from exc
        if settlement.outbox.status != "POSTED":
            raise UnsupportedLoanAccountingEvent(
                "Renewal settlement must post before the successor opening."
            )
        return OperationalOnlyDeliveryReceipt()
    if event.event_kind == TransactionKind.REVERSAL.value:
        return dea_facade.reverse_pawn_loan_accounting_event(
            event,
            actor=event.created_by,
        )
    raise UnsupportedLoanAccountingEvent(
        f"No DEA delivery adapter is registered for {event.event_kind}."
    )
