from django.db import transaction

from apps.tenant_apps.dea.models import PrepaidExpense, PrepaidScheduleLine, VoucherType
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.rules.prepaid import PrepaidExpensePostingRule  # noqa: F401
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc


class PrepaidService:
    @staticmethod
    def get_unposted_for_period(period, tenant=None):
        """Return prepaid expenses that should have amortization posted for the period."""
        return PrepaidExpense.objects.filter(
            start_date__lte=period.end_date,
            end_date__gte=period.start_date,
        ).exclude(
            schedule_lines__period=period,
            schedule_lines__posted_voucher__isnull=False,
        ).distinct()

    @staticmethod
    @transaction.atomic
    def post_for_period(prepaid, period, user=None):
        if period.end_date < prepaid.start_date or period.start_date > prepaid.end_date:
            return None

        amount = prepaid.get_amount_for_period(period)
        schedule, _created = PrepaidScheduleLine.objects.get_or_create(
            prepaid_expense=prepaid,
            period=period,
            defaults={
                "amount": amount,
                "created_by": user or prepaid.created_by,
                "updated_by": user or prepaid.updated_by or prepaid.created_by,
            },
        )

        if schedule.posted_voucher_id:
            return schedule

        if schedule.amount.amount <= 0:
            return schedule

        voucher_type, _ = VoucherType.objects.get_or_create(
            name="PREPAID_EXPENSE",
            defaults={"description": "Prepaid expense amortization"},
        )

        voucher, _journal_entry = create_and_post_voucher_for_doc(
            doc=schedule,
            user=user or prepaid.updated_by or prepaid.created_by,
            voucher_type_input=voucher_type,
            engine=DjangoPostingEngine(),
        )

        schedule.amount = amount
        schedule.posted_voucher = voucher
        schedule.save(update_fields=["amount", "posted_voucher"])
        return schedule
