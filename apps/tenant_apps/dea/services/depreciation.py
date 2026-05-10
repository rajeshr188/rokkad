from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.dea.models import DepreciationSchedule, FixedAsset, VoucherType
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.rules.depreciation import DepreciationPostingRule  # noqa: F401
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc


class DepreciationService:
    @staticmethod
    def get_unposted_for_period(period, tenant=None):
        """Return assets that should have depreciation posted for the period."""
        return FixedAsset.objects.filter(purchase_date__lte=period.end_date).exclude(
            depreciation_schedules__period=period,
            depreciation_schedules__posted_voucher__isnull=False,
        ).distinct()

    @staticmethod
    @transaction.atomic
    def post_for_period(asset, period, user=None):
        if period.end_date < asset.purchase_date:
            return None

        schedule, created = DepreciationSchedule.objects.get_or_create(
            asset=asset,
            period=period,
            defaults={
                "amount": asset.get_depreciation_amount_for_period(period),
                "created_by": user or asset.created_by,
                "updated_by": user or asset.updated_by or asset.created_by,
            },
        )

        if schedule.posted_voucher_id:
            return schedule

        amount = schedule.amount or asset.get_depreciation_amount_for_period(period)
        if amount.amount <= 0:
            return schedule

        voucher_type, _ = VoucherType.objects.get_or_create(
            name="DEPRECIATION",
            defaults={"description": "Fixed asset depreciation"},
        )

        voucher, _journal_entry = create_and_post_voucher_for_doc(
            doc=schedule,
            user=user or asset.updated_by or asset.created_by,
            voucher_type_input=voucher_type,
            engine=DjangoPostingEngine(),
        )

        schedule.amount = amount
        schedule.posted_voucher = voucher
        schedule.save(update_fields=["amount", "posted_voucher"])
        return schedule
