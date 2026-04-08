from contextlib import nullcontext
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.girvi.service_modules.accrual import (
    InterestAccrualCommand,
    InterestAccrualService,
)


class _FakeAccrualRelation:
    def __init__(self, periods=None):
        self._periods = periods or []

    def values_list(self, *args, **kwargs):
        return list(self._periods)


class InterestAccrualServiceTests(SimpleTestCase):
    def _build_loan(self, *, periods=None):
        base_date = timezone.localdate() - relativedelta(months=3)
        return SimpleNamespace(
            pk=42,
            loan_id="GL00042",
            loan_date=timezone.make_aware(datetime.combine(base_date, datetime.min.time()).replace(hour=10)),
            get_interest_amount=Decimal("125.00"),
            interest_accruals=_FakeAccrualRelation(periods=periods),
        )

    def test_preview_identifies_missing_completed_periods(self):
        first_period_start = timezone.localdate() - relativedelta(months=3)
        loan = self._build_loan(
            periods=[(first_period_start, first_period_start + relativedelta(months=1))]
        )
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=timezone.localdate(),
            trigger_source="MANUAL",
        )

        preview = InterestAccrualService.preview(command)

        self.assertTrue(preview.is_valid)
        self.assertEqual(preview.completed_periods, 3)
        self.assertEqual(preview.existing_periods, 1)
        self.assertEqual(preview.pending_periods, 2)
        self.assertEqual(preview.newly_accrued_amount, Decimal("250.00"))
        self.assertEqual(len(preview.periods_to_create), 2)

    def test_preview_rejects_future_as_of_date(self):
        loan = self._build_loan()
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=timezone.localdate() + timedelta(days=1),
            trigger_source="MANUAL",
        )

        preview = InterestAccrualService.preview(command)

        self.assertFalse(preview.is_valid)
        self.assertIn("future", " ".join(preview.errors).lower())

    def test_execute_creates_rows_for_each_missing_period(self):
        loan = self._build_loan()
        expected_start = timezone.localdate() - relativedelta(months=3)
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=expected_start + relativedelta(months=2),
            trigger_source="SCHEDULED",
        )
        created_payloads = []

        def _capture_create(**kwargs):
            created_payloads.append(kwargs)
            return SimpleNamespace(**kwargs)

        with patch(
            "apps.tenant_apps.girvi.service_modules.accrual.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.accrual.LoanInterestAccrual.objects.create",
            side_effect=_capture_create,
        ):
            result = InterestAccrualService.execute(command)

        self.assertTrue(result.success)
        self.assertEqual(result.created_count, 2)
        self.assertEqual(result.total_created_amount, Decimal("250.00"))
        self.assertEqual(len(created_payloads), 2)
        self.assertEqual(created_payloads[0]["period_start"], expected_start)
        self.assertEqual(created_payloads[1]["period_end"], expected_start + relativedelta(months=2))

    def test_preview_does_not_accrue_before_first_full_month_boundary(self):
        base_date = timezone.localdate() - timedelta(days=20)
        loan = SimpleNamespace(
            pk=43,
            loan_id="GL00043",
            loan_date=timezone.make_aware(
                datetime.combine(base_date, datetime.min.time()).replace(hour=10)
            ),
            get_interest_amount=Decimal("125.00"),
            interest_accruals=_FakeAccrualRelation(),
        )
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=timezone.localdate(),
            trigger_source="MANUAL",
        )

        preview = InterestAccrualService.preview(command)

        self.assertTrue(preview.is_valid)
        self.assertEqual(preview.completed_periods, 0)
        self.assertEqual(preview.pending_periods, 0)
        self.assertEqual(preview.newly_accrued_amount, Decimal("0.00"))

    def test_execute_is_idempotent_when_all_completed_periods_exist(self):
        expected_start = timezone.localdate() - relativedelta(months=3)
        loan = self._build_loan(
            periods=[
                (expected_start, expected_start + relativedelta(months=1)),
                (
                    expected_start + relativedelta(months=1),
                    expected_start + relativedelta(months=2),
                ),
            ]
        )
        command = InterestAccrualCommand(
            loan=loan,
            as_of_date=expected_start + relativedelta(months=2),
            trigger_source="SCHEDULED",
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.accrual.LoanInterestAccrual.objects.create"
        ) as mock_create:
            result = InterestAccrualService.execute(command)

        self.assertTrue(result.success)
        self.assertEqual(result.created_count, 0)
        self.assertIn("No new interest accrual periods", result.message)
        mock_create.assert_not_called()
