"""
Purchase invoice posting rules.

Posts goods, services, and fixed-asset purchases with supplier payable attribution.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError

from ..registry import register_rule
from ..resolver import get_ledger_id_by_key
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule
from .party_accounts import resolve_purchase_supplier_account


@register_rule("PURCHASE_GOODS")
class PurchaseGoodsRule(BasePostingRule):
    voucher_type = "PURCHASE_GOODS"
    rule_version = "2"
    debit_ledger_key = "INVENTORY"
    account_xact_type = "CRPU"

    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "GOODS"

    def build_posting(self, ctx) -> PostingBundle:
        return _build_purchase_posting(self, ctx)

    def fingerprint_payload(self, ctx):
        return _purchase_fingerprint(self, ctx)


@register_rule("PURCHASE_SERVICES")
class PurchaseServicesRule(PurchaseGoodsRule):
    voucher_type = "PURCHASE_SERVICES"
    debit_ledger_key = "SERVICES_EXPENSE"

    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "SERVICES"


@register_rule("PURCHASE_ASSETS")
class PurchaseAssetsRule(PurchaseGoodsRule):
    voucher_type = "PURCHASE_ASSETS"
    debit_ledger_key = "FIXED_ASSETS"

    def should_run(self, doc) -> bool:
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "ASSETS"


def _build_purchase_posting(rule, ctx) -> PostingBundle:
    doc = ctx.doc if hasattr(ctx, "doc") else ctx
    tenant_id = getattr(ctx, "tenant_id", None)

    taxable = _money_amount(doc.taxable_amount)
    cgst = _money_amount(doc.cgst_amount)
    sgst = _money_amount(doc.sgst_amount)
    igst = _money_amount(doc.igst_amount)
    tds = _money_amount(doc.tds_amount)
    net_payable = _money_amount(doc.net_payable)
    currency = str(doc.net_payable.currency)

    if net_payable <= 0:
        raise ValidationError("Purchase invoice net payable must be positive")

    supplier_account = resolve_purchase_supplier_account(doc)
    debit_ledger = get_ledger_id_by_key(rule.debit_ledger_key, tenant_id=tenant_id)
    gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT", tenant_id=tenant_id)
    ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE", tenant_id=tenant_id)
    tds_ledger = get_ledger_id_by_key("TDS_PAYABLE", tenant_id=tenant_id)

    ledger_lines = []
    _append_payable_split(
        ledger_lines,
        debit_ledger_id=debit_ledger,
        credit_ledger_id=ap_ledger,
        amount=taxable,
        currency=currency,
    )
    for tax_amount in (cgst, sgst, igst):
        _append_payable_split(
            ledger_lines,
            debit_ledger_id=gst_input_ledger,
            credit_ledger_id=ap_ledger,
            amount=tax_amount,
            currency=currency,
        )
    if tds > 0:
        _append_payable_split(
            ledger_lines,
            debit_ledger_id=ap_ledger,
            credit_ledger_id=tds_ledger,
            amount=tds,
            currency=currency,
        )

    if not ledger_lines:
        raise ValidationError("Purchase invoice has no postable amount")

    account_lines = [
        AccountLine(
            ledger_id=ap_ledger,
            account_id=supplier_account.id,
            side="Cr",
            currency=currency,
            amount=net_payable,
            amount_base=net_payable,
            xact_type_ext=rule.account_xact_type,
        )
    ]

    return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)


def _purchase_fingerprint(rule, ctx):
    doc = ctx.doc
    return {
        "voucher_type": rule.voucher_type,
        "rule_version": rule.rule_version,
        "invoice_id": getattr(doc, "id", None),
        "internal_number": getattr(doc, "internal_number", None),
        "vendor_id": getattr(doc, "vendor_id", None),
        "purchase_type": getattr(doc, "purchase_type", None),
        "net_payable": str(getattr(doc.net_payable, "amount", "")),
        "currency": str(getattr(doc.net_payable, "currency", "")),
    }


def _money_amount(value):
    return Decimal(str(value.amount if hasattr(value, "amount") else value))


def _append_payable_split(lines, *, debit_ledger_id, credit_ledger_id, amount, currency):
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
