from contextlib import nullcontext
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models import Series, TakenLoan
from apps.tenant_apps.girvi.service_modules.custody import (
    create_repledge_from_items,
    _resolve_repledge_series,
)
from apps.tenant_apps.girvi.service_modules.id_generation import LoanIDGenerator


class FakeQuerySet:
    def __init__(self, items=None):
        self.items = items or []
        self.filters = []
        self.ordering = []

    def filter(self, **kwargs):
        self.filters.append(kwargs)
        return self

    def order_by(self, *fields):
        self.ordering.append(fields)
        return self

    def first(self):
        return self.items[0] if self.items else None


class CustodyRepledgeServiceTests(SimpleTestCase):
    def test_create_repledge_uses_resolved_series_for_taken_loan(self):
        series = MagicMock(spec=Series)
        item = MagicMock()
        item.is_available_for_repledge = True
        item.itemdesc = "Ring"
        item.current_value.return_value = Decimal("1000.00")
        taken_loan = MagicMock()
        user = MagicMock()

        with (
            patch(
                "apps.tenant_apps.girvi.service_modules.custody.transaction.atomic",
                return_value=nullcontext(),
            ),
            patch(
                "apps.tenant_apps.girvi.service_modules.custody._resolve_repledge_series",
                return_value=series,
            ) as resolve_series,
            patch(
                "apps.tenant_apps.girvi.service_modules.custody.LoanItem.objects.filter",
                return_value=[item],
            ),
            patch(
                "apps.tenant_apps.girvi.service_modules.custody.TakenLoan.objects.create",
                return_value=taken_loan,
            ) as create_taken_loan,
        ):
            result = create_repledge_from_items(
                item_ids=[1],
                lender_id=42,
                loan_amount=Decimal("800.00"),
                loan_date=date(2026, 6, 20),
                notes="Bundle pledge",
                user=user,
                series_id=7,
            )

        self.assertIs(result, taken_loan)
        resolve_series.assert_called_once_with(7)
        create_taken_loan.assert_called_once_with(
            series=series,
            lender_id=42,
            loan_date=date(2026, 6, 20),
        )
        taken_loan.add_collateral.assert_called_once_with(
            loan_items=[item],
            user=user,
            notes="Bundle pledge",
        )

    def test_resolve_repledge_series_raises_when_no_active_series_exists(self):
        with patch(
            "apps.tenant_apps.girvi.service_modules.custody.Series.objects.active_for_loans",
            return_value=FakeQuerySet(),
        ):
            with self.assertRaisesMessage(
                ValidationError,
                "No active loan series is available for repledge creation",
            ):
                _resolve_repledge_series()

    def test_resolve_repledge_series_filters_selected_series_to_taken_loans(self):
        series = MagicMock(spec=Series)
        series_qs = FakeQuerySet([series])

        with patch(
            "apps.tenant_apps.girvi.service_modules.custody.Series.objects.active_for_loans",
            return_value=series_qs,
        ):
            resolved = _resolve_repledge_series(series_id=7)

        self.assertIs(resolved, series)
        self.assertEqual(
            series_qs.filters,
            [{"loan_type": Series.LoanType.TAKEN}, {"pk": 7}],
        )

    def test_loan_id_generator_can_use_taken_loan_table_for_sequence(self):
        series = MagicMock(spec=Series)
        series.id = 5
        with patch(
            "apps.tenant_apps.girvi.service_modules.id_generation.GirviNumberSequenceService.allocate",
            return_value="T00008",
        ) as allocate:
            loan_id = LoanIDGenerator.generate(series, loan_model=TakenLoan)

        self.assertEqual(loan_id, "T00008")
        allocate.assert_called_once_with(series, "TAKEN_LOAN")
