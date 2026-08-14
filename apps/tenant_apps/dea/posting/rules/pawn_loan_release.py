"""DEA posting rule for PawnLoan final release settlements."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_RELEASE")
class PawnLoanReleaseRule(BasePostingRule):
    voucher_type = "PAWN_LOAN_RELEASE"
    rule_version = "1"
    event_kind = "RELEASE_RECEIPT"
    event_label = "release"
    recognition_section = "release"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        if getattr(event, "event_kind", None) != self.event_kind:
            raise ValidationError(
                f"{self.voucher_type} requires a {self.event_label} event."
            )
        payload = event.payload or {}
        values = payload.get("values", {})
        principal = _amount(values, "principal", self.event_label)
        capitalized_interest_principal = _amount(
            values,
            "capitalized_interest_principal",
            self.event_label,
        )
        if capitalized_interest_principal > principal:
            raise ValidationError(
                "Capitalized-interest principal cannot exceed total principal."
            )
        interest = _amount(values, "interest", self.event_label)
        fees = _amount(values, "fees", self.event_label)
        if principal + interest + fees <= 0:
            raise ValidationError(
                f"PawnLoan {self.event_label} settlement must be positive."
            )

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
        recognition = (payload.get(self.recognition_section) or {}).get(
            "accounting_recognition", "CASH"
        )
        lines = []
        if principal:
            principal_control_amount = principal
            if recognition == "CASH":
                principal_control_amount -= capitalized_interest_principal
            if principal_control_amount:
                lines.append(
                    _receipt_line(
                        cash_id,
                        _ledger_id("LOAN_PRINCIPAL_CTRL"),
                        principal_control_amount,
                        currency,
                    )
                )
            if recognition == "CASH" and capitalized_interest_principal:
                lines.append(
                    _receipt_line(
                        cash_id,
                        _ledger_id("INTEREST_INCOME"),
                        capitalized_interest_principal,
                        currency,
                    )
                )
        if interest:
            target = (
                "INTEREST_RECEIVABLE"
                if recognition == "ACCRUAL"
                else "INTEREST_INCOME"
            )
            lines.append(
                _receipt_line(cash_id, _ledger_id(target), interest, currency)
            )
        if fees:
            lines.append(
                _receipt_line(
                    cash_id,
                    _ledger_id("DOCUMENT_CHARGE_INCOME"),
                    fees,
                    currency,
                )
            )
        account_lines = []
        account_principal = principal
        if recognition == "CASH":
            account_principal -= capitalized_interest_principal
        if account_principal:
            account_lines.append(
                AccountLine(
                    ledger_id=_ledger_id("BORROWER_LOAN_CTRL"),
                    account_id=borrower_account.pk,
                    side="Cr",
                    currency=currency,
                    amount=account_principal,
                    amount_base=account_principal,
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


def _amount(values, key, event_label):
    amount = Decimal(str(values.get(key, "0")))
    if amount < 0:
        raise ValidationError(f"PawnLoan {event_label} {key} cannot be negative.")
    return amount


def _ledger_id(key):
    return get_ledger_id_by_key(key)


def _receipt_line(cash_id, credit_id, amount, currency):
    return DualLedgerLine(
        debit_ledger_id=cash_id,
        credit_ledger_id=credit_id,
        currency=currency,
        amount=amount,
        amount_base=amount,
    )
