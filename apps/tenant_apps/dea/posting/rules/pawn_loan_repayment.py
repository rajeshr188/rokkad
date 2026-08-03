"""DEA posting rule for side-by-side Loans PawnLoan repayments."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.models import Ledger
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_REPAYMENT")
class PawnLoanRepaymentRule(BasePostingRule):
    voucher_type = "PAWN_LOAN_REPAYMENT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        if getattr(event, "event_kind", None) != "REPAYMENT":
            raise ValidationError("PAWN_LOAN_REPAYMENT requires a repayment event.")
        payload = event.payload or {}
        values = payload.get("values", {})
        principal = _amount(values, "principal")
        interest = _amount(values, "interest")
        fees = _amount(values, "fees")
        total = principal + interest + fees
        if total <= 0:
            raise ValidationError("PawnLoan repayment amount must be positive.")

        resolved = resolve_party_account(
            event.loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        )
        if resolved is None:
            raise ValidationError("Borrower loan-receivable account mapping is missing.")
        borrower_account = getattr(resolved, "account", resolved)
        cash_id = _ledger_id("CASH")
        currency = payload.get("currency") or "INR"
        lines = []
        if principal:
            lines.append(
                _receipt_line(
                    cash_id,
                    _ledger_id("LOAN_PRINCIPAL_CTRL"),
                    principal,
                    currency,
                )
            )
        if interest:
            recognition = (payload.get("repayment") or {}).get(
                "accounting_recognition", "CASH"
            )
            interest_target = (
                "INTEREST_RECEIVABLE"
                if recognition == "ACCRUAL"
                else "INTEREST_INCOME"
            )
            lines.append(
                _receipt_line(cash_id, _ledger_id(interest_target), interest, currency)
            )
        if fees:
            lines.append(
                _receipt_line(cash_id, _ledger_id("DOCUMENT_CHARGE_INCOME"), fees, currency)
            )
        account_lines = []
        if principal:
            account_lines.append(
                AccountLine(
                    ledger_id=_ledger_id("BORROWER_LOAN_CTRL"),
                    account_id=borrower_account.pk,
                    side="Cr",
                    currency=currency,
                    amount=principal,
                    amount_base=principal,
                    xact_type_ext="RP",
                )
            )
        return PostingBundle(ledger_lines=lines, account_lines=account_lines)

    def fingerprint_payload(self, ctx):
        event = ctx.doc
        return {
            "source_event_id": event.pk,
            "idempotency_key": event.idempotency_key,
            "payload_fingerprint": event.payload_fingerprint,
            "effective_date": event.effective_date,
            "payload": event.payload,
        }


def _amount(values, key):
    amount = Decimal(str(values.get(key, "0")))
    if amount < 0:
        raise ValidationError(f"Repayment {key} cannot be negative.")
    return amount


def _ledger_id(key):
    try:
        return Ledger.objects.only("pk").get(name=key).pk
    except Ledger.DoesNotExist as exc:
        raise ValidationError(f"Required ledger {key} was not found.") from exc


def _receipt_line(cash_id, credit_id, amount, currency):
    return DualLedgerLine(
        debit_ledger_id=cash_id,
        credit_ledger_id=credit_id,
        currency=currency,
        amount=amount,
        amount_base=amount,
    )
