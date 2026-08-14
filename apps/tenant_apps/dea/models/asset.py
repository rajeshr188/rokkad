from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from djmoney.models.fields import MoneyField
from moneyed import Money

from .doc import BusinessDoc


class DepreciationMethod(models.TextChoices):
    SLM = "SLM", "Straight Line Method"
    WDV = "WDV", "Written Down Value"


class FixedAsset(BusinessDoc):
    name = models.CharField(max_length=200)
    purchase_date = models.DateField()
    cost = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    salvage_value = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    useful_life_months = models.PositiveIntegerField()
    method = models.CharField(
        max_length=3,
        choices=DepreciationMethod.choices,
        default=DepreciationMethod.SLM,
    )
    ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="fixed_assets",
        help_text="Asset GL ledger",
    )
    acc_dep_ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="accumulated_depreciation_assets",
        help_text="Accumulated depreciation ledger",
    )
    dep_exp_ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="depreciation_expense_assets",
        help_text="Depreciation expense ledger",
    )

    class Meta:
        app_label = "dea"
        ordering = ["purchase_date", "id"]

    def __str__(self):
        return self.name

    def _auto_post_to_accounting(self):
        """Asset creation is not itself a depreciation event."""
        return None

    def clean(self):
        super().clean()
        if self.useful_life_months <= 0:
            raise ValidationError("useful_life_months must be greater than zero.")
        if self.salvage_value.amount < 0:
            raise ValidationError("salvage_value cannot be negative.")
        if self.cost.amount < 0:
            raise ValidationError("cost cannot be negative.")
        if self.salvage_value.amount > self.cost.amount:
            raise ValidationError("salvage_value cannot exceed cost.")

    def get_voucher_type(self) -> str:
        return "DEPRECIATION"

    def get_depreciable_base(self) -> Decimal:
        return Decimal(str(self.cost.amount - self.salvage_value.amount))

    def get_monthly_depreciation(self) -> Money:
        base = self.get_depreciable_base()
        amount = (base / Decimal(str(self.useful_life_months))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return Money(amount, str(self.cost.currency))

    def get_depreciation_amount_for_period(self, period) -> Money:
        if period.end_date < self.purchase_date:
            return Money(Decimal("0.00"), str(self.cost.currency))

        monthly = self.get_monthly_depreciation()
        if self.method == DepreciationMethod.SLM:
            return monthly

        posted_count = self.depreciation_schedules.filter(
            posted_voucher__isnull=False
        ).count()
        remaining_months = max(self.useful_life_months - posted_count, 1)
        remaining_base = max(
            self.get_depreciable_base() - self.depreciated_amount(), Decimal("0.00")
        )
        amount = (remaining_base / Decimal(str(remaining_months))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        return Money(amount, str(self.cost.currency))

    def depreciated_amount(self) -> Decimal:
        total = Decimal("0.00")
        for schedule in self.depreciation_schedules.filter(posted_voucher__isnull=False):
            total += Decimal(str(schedule.amount.amount))
        return total

    def get_economic_payload(self) -> dict:
        payload = {
            "asset_id": self.id,
            "name": self.name,
            "purchase_date": str(self.purchase_date),
            "cost": str(self.cost.amount),
            "cost_currency": str(self.cost.currency),
            "salvage_value": str(self.salvage_value.amount),
            "salvage_currency": str(self.salvage_value.currency),
            "useful_life_months": self.useful_life_months,
            "method": self.method,
            "ledger_id": self.ledger_id,
            "acc_dep_ledger_id": self.acc_dep_ledger_id,
            "dep_exp_ledger_id": self.dep_exp_ledger_id,
        }
        period = getattr(self, "_posting_period", None)
        if period is not None:
            payload["period_id"] = getattr(period, "pk", None)
            payload["period_start"] = str(getattr(period, "start_date", ""))
            payload["period_end"] = str(getattr(period, "end_date", ""))
        amount = getattr(self, "_posting_amount", None)
        if amount is not None:
            payload["posting_amount"] = str(amount.amount)
            payload["posting_currency"] = str(amount.currency)
        return payload


class DepreciationSchedule(BusinessDoc):
    asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name="depreciation_schedules",
    )
    period = models.ForeignKey(
        "dea.AccountingPeriod",
        on_delete=models.CASCADE,
        related_name="depreciation_schedules",
    )
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    posted_voucher = models.ForeignKey(
        "dea.Voucher",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="depreciation_schedules",
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "dea"
        constraints = [
            models.UniqueConstraint(
                fields=["asset", "period"],
                name="unique_depreciation_schedule_asset_period",
            )
        ]

    def __str__(self):
        return f"{self.asset.name} / {self.period.name} / {self.amount}"

    def _auto_post_to_accounting(self):
        return None

    @property
    def voucher_date(self):
        return self.period.end_date

    def get_voucher_type(self) -> str:
        return "DEPRECIATION"

    def get_economic_payload(self) -> dict:
        return {
            "schedule_id": self.id,
            "asset_id": self.asset_id,
            "asset_name": self.asset.name,
            "period_id": self.period_id,
            "period_start": str(self.period.start_date),
            "period_end": str(self.period.end_date),
            "amount": str(self.amount.amount),
            "currency": str(self.amount.currency),
            "asset_method": self.asset.method,
        }