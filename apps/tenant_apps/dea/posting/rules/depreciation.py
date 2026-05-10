from django.core.exceptions import ValidationError

from ..registry import register_rule
from ..types import DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("DEPRECIATION")
class DepreciationPostingRule(BasePostingRule):
    voucher_type = "DEPRECIATION"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        schedule = ctx.doc if hasattr(ctx, "doc") else ctx
        asset = getattr(schedule, "asset", None)

        if asset is None:
            raise ValidationError("Depreciation schedule must reference a fixed asset.")
        if not getattr(asset, "dep_exp_ledger_id", None):
            raise ValidationError("Depreciation expense ledger is required.")
        if not getattr(asset, "acc_dep_ledger_id", None):
            raise ValidationError("Accumulated depreciation ledger is required.")

        amount = getattr(schedule, "amount", None)
        if amount is None:
            raise ValidationError("Depreciation schedule amount is required.")

        if amount.amount <= 0:
            raise ValidationError("Depreciation amount must be positive.")

        return PostingBundle(
            ledger_lines=[
                DualLedgerLine(
                    debit_ledger_id=asset.dep_exp_ledger_id,
                    credit_ledger_id=asset.acc_dep_ledger_id,
                    currency=str(amount.currency),
                    amount=amount.amount,
                    amount_base=amount.amount,
                )
            ],
            account_lines=[],
        )
