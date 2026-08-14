from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import models
from djmoney.models.fields import MoneyField
from moneyed import Money

from .doc import BusinessDoc


class PrepaidExpense(BusinessDoc):
    name = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    prepaid_ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="prepaid_expenses",
        help_text="Asset ledger for prepaid expense",
    )
    expense_ledger = models.ForeignKey(
        "dea.Ledger",
        on_delete=models.PROTECT,
        related_name="prepaid_expense_ledgers",
        help_text="Expense ledger for amortization",
    )

    class Meta:
        app_label = "dea"
        ordering = ["start_date", "id"]

    def __str__(self):
        return self.name

    def _auto_post_to_accounting(self):
        return None

    def clean(self):
        super().clean()
        if self.start_date > self.end_date:
            raise ValidationError("start_date must be on or before end_date.")
        if self.total_amount.amount < 0:
            raise ValidationError("total_amount cannot be negative.")

    def get_voucher_type(self) -> str:
        return "PREPAID_EXPENSE"

    def get_total_months(self) -> int:
        months = (self.end_date.year - self.start_date.year) * 12 + (
            self.end_date.month - self.start_date.month
        ) + 1
        return max(months, 1)

    def get_period_amount(self) -> Money:
        amount = (
            Decimal(str(self.total_amount.amount))
            / Decimal(str(self.get_total_months()))
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return Money(amount, str(self.total_amount.currency))

    def get_amount_for_period(self, period) -> Money:
        if period.end_date < self.start_date or period.start_date > self.end_date:
            return Money(Decimal("0.00"), str(self.total_amount.currency))
        return self.get_period_amount()

    def get_economic_payload(self) -> dict:
        return {
            "prepaid_id": self.id,
            "name": self.name,
            "start_date": str(self.start_date),
            "end_date": str(self.end_date),
            "total_amount": str(self.total_amount.amount),
            "currency": str(self.total_amount.currency),
            "prepaid_ledger_id": self.prepaid_ledger_id,
            "expense_ledger_id": self.expense_ledger_id,
        }


class PrepaidScheduleLine(BusinessDoc):
    prepaid_expense = models.ForeignKey(
        PrepaidExpense,
        on_delete=models.CASCADE,
        related_name="schedule_lines",
    )
    period = models.ForeignKey(
        "dea.AccountingPeriod",
        on_delete=models.CASCADE,
        related_name="prepaid_schedule_lines",
    )
    amount = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    posted_voucher = models.ForeignKey(
        "dea.Voucher",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="prepaid_schedule_lines",
    )
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "dea"
        constraints = [
            models.UniqueConstraint(
                fields=["prepaid_expense", "period"],
                name="unique_prepaid_schedule_expense_period",
            )
        ]

    def __str__(self):
        return f"{self.prepaid_expense.name} / {self.period.name} / {self.amount}"

    def _auto_post_to_accounting(self):
        return None

    @property
    def voucher_date(self):
        return self.period.end_date

    def get_voucher_type(self) -> str:
        return "PREPAID_EXPENSE"

    def get_economic_payload(self) -> dict:
        return {
            "schedule_id": self.id,
            "prepaid_id": self.prepaid_expense_id,
            "prepaid_name": self.prepaid_expense.name,
            "period_id": self.period_id,
            "period_start": str(self.period.start_date),
            "period_end": str(self.period.end_date),
            "amount": str(self.amount.amount),
            "currency": str(self.amount.currency),
        }
