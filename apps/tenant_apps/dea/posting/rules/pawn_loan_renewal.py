"""DEA posting rule for atomic PawnLoan renewal net settlement."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.models import Ledger
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_RENEWAL")
class PawnLoanRenewalRule(BasePostingRule):
    voucher_type = "PAWN_LOAN_RENEWAL"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        if getattr(event, "event_kind", None) != "RENEWAL_SETTLEMENT":
            raise ValidationError(
                "PAWN_LOAN_RENEWAL requires a renewal settlement event."
            )
        payload = event.payload or {}
        values = payload.get("values") or {}
        renewal = payload.get("renewal") or {}
        source_control = _amount(renewal, "source_control_principal")
        successor_control = _amount(renewal, "successor_control_principal")
        interest = _amount(values, "interest")
        fees = _amount(values, "fees")
        if not renewal.get("successor_loan_id"):
            raise ValidationError("Renewal successor identity is required.")

        resolved = resolve_party_account(
            event.loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        )
        if resolved is None:
            raise ValidationError("Borrower loan-receivable account mapping is missing.")
        borrower_account = getattr(resolved, "account", resolved)
        currency = payload.get("currency") or "INR"
        cash_id = _ledger_id("CASH")
        principal_id = _ledger_id("LOAN_PRINCIPAL_CTRL")
        ledger_lines = []
        account_lines = []
        principal_delta = source_control - successor_control
        if principal_delta > 0:
            ledger_lines.append(
                _line(cash_id, principal_id, principal_delta, currency)
            )
            account_lines.append(
                _account_line(
                    borrower_account.pk,
                    "Cr",
                    principal_delta,
                    currency,
                )
            )
        elif principal_delta < 0:
            amount = -principal_delta
            ledger_lines.append(_line(principal_id, cash_id, amount, currency))
            account_lines.append(
                _account_line(borrower_account.pk, "Dr", amount, currency)
            )
        if interest:
            recognition = renewal.get("accounting_recognition", "CASH")
            credit = (
                "INTEREST_RECEIVABLE"
                if recognition == "ACCRUAL"
                else "INTEREST_INCOME"
            )
            ledger_lines.append(
                _line(cash_id, _ledger_id(credit), interest, currency)
            )
        if fees:
            ledger_lines.append(
                _line(
                    cash_id,
                    _ledger_id("DOCUMENT_CHARGE_INCOME"),
                    fees,
                    currency,
                )
            )
        if not ledger_lines:
            raise ValidationError(
                "Renewal must have a principal delta, interest, or fees to post."
            )
        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

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
        raise ValidationError(f"Renewal {key} cannot be negative.")
    return amount


def _ledger_id(key):
    try:
        return Ledger.objects.only("pk").get(name=key).pk
    except Ledger.DoesNotExist as exc:
        raise ValidationError(f"Required ledger {key} was not found.") from exc


def _line(debit_id, credit_id, amount, currency):
    return DualLedgerLine(
        debit_ledger_id=debit_id,
        credit_ledger_id=credit_id,
        currency=currency,
        amount=amount,
        amount_base=amount,
    )


def _account_line(account_id, side, amount, currency):
    return AccountLine(
        ledger_id=_ledger_id("BORROWER_LOAN_CTRL"),
        account_id=account_id,
        side=side,
        currency=currency,
        amount=amount,
        amount_base=amount,
        xact_type_ext="RN",
    )
