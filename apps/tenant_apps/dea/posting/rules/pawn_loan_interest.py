"""DEA rules for PawnLoan interest accrual and capitalization events."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.models import Ledger
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_INTEREST_ACCRUAL")
class PawnLoanInterestAccrualRule(BasePostingRule):
    voucher_type = "PAWN_LOAN_INTEREST_ACCRUAL"
    rule_version = "2"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        if getattr(event, "event_kind", None) != "INTEREST_ACCRUAL":
            raise ValidationError("PawnLoan event must be INTEREST_ACCRUAL.")
        values = event.payload.get("values") or {}
        interest = Decimal(str(values.get("interest", "0")))
        advance_applied = Decimal(
            str(values.get("advance_interest_applied", "0"))
        )
        if min(interest, advance_applied) < 0 or interest + advance_applied <= 0:
            raise ValidationError("PawnLoan accrual amounts must be non-negative and non-zero.")
        currency = event.payload.get("currency") or "INR"
        ledger_lines = []
        account_lines = []
        if interest:
            borrower_account = _borrower_account(event)
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=_ledger_id("INTEREST_RECEIVABLE"),
                    credit_ledger_id=_ledger_id("INTEREST_INCOME"),
                    currency=currency,
                    amount=interest,
                    amount_base=interest,
                )
            )
            account_lines.append(
                AccountLine(
                    ledger_id=_ledger_id("BORROWER_LOAN_CTRL"),
                    account_id=borrower_account.pk,
                    side="Dr",
                    currency=currency,
                    amount=interest,
                    amount_base=interest,
                    xact_type_ext="IA",
                )
            )
        if advance_applied:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=_ledger_id("Unearned Revenue"),
                    credit_ledger_id=_ledger_id("INTEREST_INCOME"),
                    currency=currency,
                    amount=advance_applied,
                    amount_base=advance_applied,
                )
            )
        return PostingBundle(
            ledger_lines=ledger_lines,
            account_lines=account_lines,
        )

    def fingerprint_payload(self, ctx):
        return _fingerprint(ctx.doc)


@register_rule("PAWN_LOAN_INTEREST_CAPITALIZATION")
class PawnLoanInterestCapitalizationRule(BasePostingRule):
    voucher_type = "PAWN_LOAN_INTEREST_CAPITALIZATION"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        event = ctx.doc
        interest = _interest(event, "INTEREST_CAPITALIZATION")
        currency = event.payload.get("currency") or "INR"
        return PostingBundle(
            ledger_lines=[
                DualLedgerLine(
                    debit_ledger_id=_ledger_id("LOAN_PRINCIPAL_CTRL"),
                    credit_ledger_id=_ledger_id("INTEREST_RECEIVABLE"),
                    currency=currency,
                    amount=interest,
                    amount_base=interest,
                )
            ],
            account_lines=[],
        )

    def fingerprint_payload(self, ctx):
        return _fingerprint(ctx.doc)


def _interest(event, expected_kind):
    if getattr(event, "event_kind", None) != expected_kind:
        raise ValidationError(f"PawnLoan event must be {expected_kind}.")
    interest = Decimal(str((event.payload.get("values") or {}).get("interest", "0")))
    if interest <= 0:
        raise ValidationError("PawnLoan interest amount must be positive.")
    return interest


def _borrower_account(event):
    resolved = resolve_party_account(
        event.loan.borrower,
        role_key="BORROWER",
        purpose="BORROWER_LOAN_RECEIVABLE",
        create=False,
    )
    if resolved is None:
        raise ValidationError("Borrower loan-receivable account mapping is missing.")
    return getattr(resolved, "account", resolved)


def _ledger_id(key):
    try:
        return Ledger.objects.only("pk").get(name=key).pk
    except Ledger.DoesNotExist as exc:
        raise ValidationError(f"Required ledger {key} was not found.") from exc


def _fingerprint(event):
    return {
        "source_event_id": event.pk,
        "idempotency_key": event.idempotency_key,
        "payload_fingerprint": event.payload_fingerprint,
        "effective_date": event.effective_date,
        "payload": event.payload,
    }
