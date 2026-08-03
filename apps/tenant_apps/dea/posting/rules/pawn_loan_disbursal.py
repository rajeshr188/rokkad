"""DEA posting rule for the side-by-side Loans PawnLoan disbursal event."""

from decimal import Decimal

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.models import Ledger
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account

from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PAWN_LOAN_DISBURSAL")
class PawnLoanDisbursalRule(BasePostingRule):
    """Post gross principal paid to a PawnLoan borrower.

    GL: Dr LOAN_PRINCIPAL_CTRL / Cr CASH
    Subledger attribution: Dr borrower account against BORROWER_LOAN_CTRL
    """

    voucher_type = "PAWN_LOAN_DISBURSAL"
    rule_version = "1"

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

        principal_control_id = _ledger_id("LOAN_PRINCIPAL_CTRL")
        cash_id = _ledger_id("CASH")
        borrower_control_id = _ledger_id("BORROWER_LOAN_CTRL")
        currency = payload.get("currency") or "INR"
        return PostingBundle(
            ledger_lines=[
                DualLedgerLine(
                    debit_ledger_id=principal_control_id,
                    credit_ledger_id=cash_id,
                    currency=currency,
                    amount=principal,
                    amount_base=principal,
                )
            ],
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
    try:
        return Ledger.objects.only("pk").get(name=key).pk
    except Ledger.DoesNotExist as exc:
        raise ValidationError(f"Required ledger {key} was not found.") from exc
