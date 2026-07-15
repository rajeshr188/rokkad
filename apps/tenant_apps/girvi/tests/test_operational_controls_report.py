from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.selectors import (
    SettlementDataUnavailableError,
    build_operational_controls_report,
)
from apps.tenant_apps.girvi.views.reports import loan_operational_controls_report


class _FakeLoanItems:
    def __init__(self, items):
        self._items = list(items)

    def filter(self, **kwargs):
        key, value = next(iter(kwargs.items()))
        if key != "custody_status":
            return _FakeLoanItems([])
        return _FakeLoanItems([item for item in self._items if getattr(item, "custody_status", None) == value])

    def count(self):
        return len(self._items)

    def all(self):
        return list(self._items)


class OperationalControlsSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.services.RateCacheService.get_rate_or_none")
    @patch("apps.tenant_apps.girvi.service_modules.overdue_policy.evaluate_overdue_policy")
    @patch("apps.tenant_apps.girvi.selectors.build_loan_settlement_balance")
    @patch("apps.tenant_apps.girvi.selectors.reverse", return_value="/girvi/loan/1/")
    def test_report_includes_all_required_categories(
        self,
        _mock_reverse,
        mock_settlement,
        mock_policy,
        mock_rate,
    ):
        item1 = SimpleNamespace(pk=11, custody_status="in_vault", itemtype="Gold", itemdesc="Ring", interestrate=Decimal("2.00"))
        item2 = SimpleNamespace(pk=12, custody_status="with_lender", itemtype="Bronze", itemdesc="Chain", interestrate=Decimal("0.00"))
        loan = SimpleNamespace(pk=1, loan_id="GL-001", borrower=SimpleNamespace(name="Asha"), is_released=False, loanitems=_FakeLoanItems([item1, item2]))

        mock_settlement.return_value = SimpleNamespace(total_outstanding=Decimal("1200.00"))
        mock_policy.return_value = SimpleNamespace(maturity_date=__import__("datetime").date(2026, 5, 1))
        mock_rate.side_effect = [Decimal("9500.00"), None]

        report = build_operational_controls_report(loans=[loan], as_of_date=__import__("datetime").date(2026, 6, 22))

        self.assertIn("aging", report)
        self.assertIn("custody", report)
        self.assertIn("release_ready", report)
        self.assertIn("rate_exceptions", report)
        self.assertEqual(len(report["aging"]["rows"]), 1)
        self.assertEqual(len(report["custody"]["rows"]), 1)
        self.assertEqual(len(report["release_ready"]["rows"]), 1)
        self.assertEqual(report["rate_exceptions"]["total"], 1)

    @patch("apps.tenant_apps.girvi.selectors.reverse", return_value="/girvi/loan/1/")
    def test_report_adds_data_unavailable_row_when_settlement_fails(
        self,
        _mock_reverse,
    ):
        loan = SimpleNamespace(
            pk=1,
            loan_id="GL-001",
            borrower=SimpleNamespace(name="Asha"),
            is_released=False,
            loanitems=_FakeLoanItems([]),
        )

        with patch(
            "apps.tenant_apps.girvi.selectors.build_loan_settlement_balance",
            side_effect=SettlementDataUnavailableError(
                "settlement_down",
                "Loan settlement balance could not be calculated safely.",
                loan_id="GL-001",
                section="settlement",
            ),
        ):
            report = build_operational_controls_report(loans=[loan])

        self.assertEqual(report["data_unavailable_count"], 1)
        self.assertEqual(len(report["data_unavailable_rows"]), 1)
        self.assertEqual(report["data_unavailable_rows"][0]["issue_code"], "data_unavailable")
        self.assertEqual(report["data_unavailable_rows"][0]["section"], "settlement")
        self.assertEqual(len(report["aging"]["rows"]), 0)


class OperationalControlsViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.reports.render")
    @patch("apps.tenant_apps.girvi.views.reports.build_operational_controls_report_context")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_view_renders_selector_payload(
        self,
        _role_name,
        _effective_permissions,
        mock_selector,
        mock_render,
    ):
        request = self.factory.get("/girvi/reports/operational-controls/")
        request.user = self.user
        request.tenant = SimpleNamespace(schema_name="tenant-1", owner=SimpleNamespace(), theme="default", logo="")
        mock_selector.return_value = {
            "report": {
                "aging": {
                    "rows": [{"loan_id": "GL-001"}],
                    "bucket_counts": {
                        "current": 1,
                        "b1_30": 0,
                        "b31_60": 0,
                        "b61_90": 0,
                        "b90_plus": 0,
                    },
                },
                "custody": {"rows": [{"loan_id": "GL-001"}]},
                "release_ready": {"rows": [{"loan_id": "GL-001"}], "ready_count": 0},
                "rate_exceptions": {"rows": [], "total": 0},
                "warnings": [],
                "data_unavailable_rows": [],
                "data_unavailable_count": 0,
                "generated_at": "2026-06-22T10:00:00",
                "scanned_loans": 1,
            },
            "aging_rows": [{"loan_id": "GL-001"}],
            "aging_bucket_counts": {"current": 1, "b1_30": 0, "b31_60": 0, "b61_90": 0, "b90_plus": 0},
            "custody_rows": [{"loan_id": "GL-001"}],
            "release_ready_rows": [{"loan_id": "GL-001"}],
            "release_ready_count": 0,
            "rate_exception_rows": [],
            "rate_exception_total": 0,
            "selector_warnings": [],
            "data_unavailable_rows": [],
            "data_unavailable_count": 0,
        }
        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = loan_operational_controls_report(request)

        self.assertEqual(result, response)
        context = mock_render.call_args.args[2]
        self.assertIn("aging_rows", context)
        self.assertIn("custody_rows", context)
        self.assertIn("release_ready_rows", context)
        self.assertIn("rate_exception_rows", context)
        self.assertIn("data_unavailable_rows", context)
        self.assertIn("data_unavailable_count", context)
