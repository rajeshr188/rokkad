"""DEA posting rule for the side-by-side Loans PawnLoan disbursal event."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_DISBURSAL")
class PawnLoanDisbursalRule(BasePostingRule):
    """Post gross principal paid to a PawnLoan borrower.

    GL: Dr LOAN_PRINCIPAL_CTRL for gross principal, with credits to cash and
    the exact advance-interest/fee deduction destinations.
    Subledger attribution: Dr borrower account against BORROWER_LOAN_CTRL
    """

    voucher_type = "PAWN_LOAN_DISBURSAL"
    rule_version = "2"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        payload = getattr(event, "payload", {}) or {}
        values = payload.get("values", {})
        principal = Decimal(str(values.get("principal", "0")))
        if principal <= 0:
            raise ValidationError("PawnLoan disbursal principal must be positive.")
        if getattr(event, "event_kind", None) != "DISBURSAL":
            raise ValidationError("PAWN_LOAN_DISBURSAL requires a disbursal source event.")

        loan = getattr(event, "loan", None)
        borrower = getattr(loan, "borrower", None)
        if borrower is None:
            raise ValidationError("PawnLoan disbursal source is missing its borrower.")
        resolved = resolve_party_account(
            borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        )
        if resolved is None:
            raise ValidationError("Borrower loan-receivable account mapping is missing.")
        borrower_account = getattr(resolved, "account", resolved)

        net_cash = Decimal(str(values.get("net_cash", principal)))
        advance_interest = Decimal(str(values.get("advance_interest", "0")))
        fees = Decimal(str(values.get("fees", "0")))
        if min(net_cash, advance_interest, fees) < 0:
            raise ValidationError("PawnLoan disbursal values cannot be negative.")
        if net_cash + advance_interest + fees != principal:
            raise ValidationError(
                "PawnLoan net cash plus deductions must equal gross principal."
            )

        principal_control_id = _ledger_id("LOAN_PRINCIPAL_CTRL")
        cash_id = _ledger_id("CASH")
        borrower_control_id = _ledger_id("BORROWER_LOAN_CTRL")
        currency = payload.get("currency") or "INR"
        ledger_lines = []
        if net_cash:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=principal_control_id,
                    credit_ledger_id=cash_id,
                    currency=currency,
                    amount=net_cash,
                    amount_base=net_cash,
                )
            )
        if advance_interest:
            recognition = (payload.get("disbursal") or {}).get(
                "accounting_recognition", "CASH"
            )
            interest_destination = (
                "Unearned Revenue" if recognition == "ACCRUAL" else "INTEREST_INCOME"
            )
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=principal_control_id,
                    credit_ledger_id=_ledger_id(interest_destination),
                    currency=currency,
                    amount=advance_interest,
                    amount_base=advance_interest,
                )
            )
        if fees:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=principal_control_id,
                    credit_ledger_id=_ledger_id("DOCUMENT_CHARGE_INCOME"),
                    currency=currency,
                    amount=fees,
                    amount_base=fees,
                )
            )
        return PostingBundle(
            ledger_lines=ledger_lines,
            account_lines=[
                AccountLine(
                    ledger_id=borrower_control_id,
                    account_id=borrower_account.pk,
                    side="Dr",
                    currency=currency,
                    amount=principal,
                    amount_base=principal,
                    xact_type_ext="LG",
                )
            ],
        )

    def fingerprint_payload(self, ctx):
        event = ctx.doc
        return {
            "source_event_id": getattr(event, "pk", None),
            "idempotency_key": getattr(event, "idempotency_key", None),
            "payload_fingerprint": getattr(event, "payload_fingerprint", None),
            "effective_date": getattr(event, "effective_date", None),
            "payload": getattr(event, "payload", None),
        }


def _ledger_id(key):
    return get_ledger_id_by_key(key)
