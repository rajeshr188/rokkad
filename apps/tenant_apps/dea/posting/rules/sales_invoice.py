"""
Sales invoice posting rule.

Posts sales revenue, output taxes, and customer receivable attribution.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError

from ..registry import register_rule
from ..resolver import get_ledger_id_by_key
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule
from .party_accounts import resolve_sales_customer_account


@register_rule("SALES_INVOICE")
class SalesInvoiceRule(BasePostingRule):
    voucher_type = "SALES_INVOICE"
    rule_version = "3"

    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import SalesInvoiceVoucher

        return isinstance(doc, SalesInvoiceVoucher)

    def build_posting(self, ctx) -> PostingBundle:
        doc = ctx.doc if hasattr(ctx, "doc") else ctx
        tenant_id = getattr(ctx, "tenant_id", None)

        total = _money_amount(doc.total_amount)
        taxable = _money_amount(doc.taxable_amount)
        cgst = _money_amount(doc.cgst_amount)
        sgst = _money_amount(doc.sgst_amount)
        igst = _money_amount(doc.igst_amount)
        tcs = _money_amount(doc.tcs_amount)
        currency = str(doc.total_amount.currency)

        if total <= 0:
            raise ValidationError("Sales invoice total must be positive")

        customer_account = resolve_sales_customer_account(doc)
        ar_ledger = get_ledger_id_by_key("ACCOUNTS_RECEIVABLE", tenant_id=tenant_id)

        ledger_lines = []
        _append_credit_split(
            ledger_lines,
            debit_ledger_id=ar_ledger,
            credit_ledger_id=get_ledger_id_by_key("SALES_REVENUE", tenant_id=tenant_id),
            amount=taxable,
            currency=currency,
        )
        _append_credit_split(
            ledger_lines,
            debit_ledger_id=ar_ledger,
            credit_ledger_id=get_ledger_id_by_key("CGST_OUTPUT", tenant_id=tenant_id),
            amount=cgst,
            currency=currency,
        )
        _append_credit_split(
            ledger_lines,
            debit_ledger_id=ar_ledger,
            credit_ledger_id=get_ledger_id_by_key("SGST_OUTPUT", tenant_id=tenant_id),
            amount=sgst,
            currency=currency,
        )
        _append_credit_split(
            ledger_lines,
            debit_ledger_id=ar_ledger,
            credit_ledger_id=get_ledger_id_by_key("IGST_OUTPUT", tenant_id=tenant_id),
            amount=igst,
            currency=currency,
        )
        _append_credit_split(
            ledger_lines,
            debit_ledger_id=ar_ledger,
            credit_ledger_id=get_ledger_id_by_key("TCS_PAYABLE", tenant_id=tenant_id),
            amount=tcs,
            currency=currency,
        )

        if not ledger_lines:
            raise ValidationError("Sales invoice has no postable amount")

        account_lines = [
            AccountLine(
                ledger_id=ar_ledger,
                account_id=customer_account.id,
                side="Dr",
                currency=currency,
                amount=total,
                amount_base=total,
                xact_type_ext="CRSL",
            )
        ]

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def fingerprint_payload(self, ctx):
        doc = ctx.doc
        return {
            "voucher_type": self.voucher_type,
            "rule_version": self.rule_version,
            "invoice_id": getattr(doc, "id", None),
            "invoice_number": getattr(doc, "invoice_number", None),
            "party_id": getattr(doc, "party_id", None),
            "total_amount": str(getattr(doc.total_amount, "amount", "")),
            "currency": str(getattr(doc.total_amount, "currency", "")),
        }


def _money_amount(value):
    return Decimal(str(value.amount if hasattr(value, "amount") else value))


def _append_credit_split(lines, *, debit_ledger_id, credit_ledger_id, amount, currency):
    if amount <= 0:
        return
    lines.append(
        DualLedgerLine(
            debit_ledger_id=debit_ledger_id,
            credit_ledger_id=credit_ledger_id,
            currency=currency,
            amount=amount,
            amount_base=amount,
        )
    )
