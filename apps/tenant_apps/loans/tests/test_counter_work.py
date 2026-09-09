from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work


class Rows(list):
    def order_by(self, *args):
        return self

    def filter(self, **kwargs):
        return self


class CounterWorkTests(SimpleTestCase):
    today = date(2026, 9, 8)

    def obligation(self, pk, due, principal, allocations=()):
        return SimpleNamespace(pk=pk, due_date=due, principal_due=Decimal(principal), interest_due=Decimal("0"),
            allocations=Rows(SimpleNamespace(component="PRINCIPAL", amount=Decimal(value)) for value in allocations))

    def result(self, obligations=None):
        loan = SimpleNamespace(pk=7, state="ACTIVE", loan_date=date(2026, 1, 1))
        schedule = None if obligations is None else SimpleNamespace(pk=1, fingerprint="test", maturity_date=date(2027, 1, 1), obligations=Rows(obligations))
        with patch("apps.tenant_apps.loans.selectors.counter_work.current_tenant_workspace_id", return_value=3), patch(
            "apps.tenant_apps.loans.selectors.counter_work.PawnLoan.objects.filter",
        ) as query, patch("apps.tenant_apps.loans.selectors.counter_work.get_active_repayment_schedule_as_of", return_value=schedule):
            query.return_value.select_related.return_value.order_by.return_value = [loan]
            result = get_workspace_counter_work(workspace=SimpleNamespace(pk=3), as_of_date=self.today)
            self.assertEqual(query.call_args.kwargs["workspace"].pk, 3)
            return result["queues"]

    def test_partial_payments_and_reversals_use_schedule_dates_not_maturity(self):
        result = self.result([
            self.obligation(1, date(2026, 9, 7), "100", ("40", "-10")),
            self.obligation(2, self.today, "200", ("50",)),
            self.obligation(3, date(2026, 9, 9), "300"),
            self.obligation(4, date(2026, 9, 6), "100", ("100",)),
        ])
        self.assertEqual(result["due"]["rows"][0]["amount"], Decimal("150"))
        self.assertEqual(result["overdue"]["rows"][0]["amount"], Decimal("70"))
        self.assertEqual(result["overdue"]["rows"][0]["date"], date(2026, 9, 7))
        self.assertEqual(result["review"]["count"], 0)

    def test_missing_or_inconsistent_schedule_is_visible_for_review(self):
        for obligations in (None, [], [self.obligation(1, self.today, "100", ("101",))]):
            with self.subTest(obligations=obligations):
                result = self.result(obligations)
                self.assertEqual(result["review"]["count"], 1)
                self.assertEqual(result["due"]["count"], 0)
                self.assertEqual(result["overdue"]["count"], 0)

    def test_foreign_or_global_context_cannot_read_queue(self):
        for current in (None, 4):
            with patch("apps.tenant_apps.loans.selectors.counter_work.current_tenant_workspace_id", return_value=current), patch(
                "apps.tenant_apps.loans.selectors.counter_work.PawnLoan.objects.filter",
            ) as query:
                with self.assertRaises(ValueError):
                    get_workspace_counter_work(workspace=SimpleNamespace(pk=3))
                query.assert_not_called()
