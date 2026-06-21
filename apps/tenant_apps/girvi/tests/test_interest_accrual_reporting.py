from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.selectors import (
    build_given_loan_detail_display,
    build_given_loan_detail_read_model,
    build_given_loan_release_action,
)
from apps.tenant_apps.girvi.views.loan import loan_detail


class InterestAccrualReadModelTests(SimpleTestCase):
    def test_build_given_loan_detail_read_model_includes_accrual_metrics(self):
        loan = MagicMock()
        payments = MagicMock()
        payments.count.return_value = 2
        journal_entries = MagicMock()
        journal_entries.count.return_value = 1

        loan.payments.order_by.return_value = payments
        loan.statementitem_set.select_related.return_value.all.return_value = []
        loan.notifications.all.return_value = []
        loan.loanitems.all.return_value = []
        loan.renewals_as_source.all.return_value = []
        loan.renewal_record.first.return_value = None
        loan.status = "Disbursed"
        loan.current_value = Decimal("1500.00")
        loan.get_loan_amount = Decimal("1000.00")
        loan.get_weight_summary = []
        loan.is_released = False
        loan.is_overdue = False
        loan.interest_due.return_value = Decimal("125.00")
        loan.total_due = Decimal("1125.00")
        loan.outstanding_principal = Decimal("1000.00")
        loan.gross_accrued_interest = Decimal("150.00")
        loan.interest_paid_total.return_value = Decimal("60.00")
        loan.outstanding_interest = Decimal("90.00")
        loan.interest_receivable_balance.return_value = Decimal("70.00")
        loan.last_accrual_date = date(2026, 3, 31)

        with patch(
            "apps.tenant_apps.girvi.selectors.get_given_loan_journal_entries",
            return_value=journal_entries,
        ):
            read_model = build_given_loan_detail_read_model(loan)

        summary = read_model["summary"]
        self.assertEqual(summary["gross_accrued_interest"], Decimal("150.00"))
        self.assertEqual(summary["interest_paid_total"], Decimal("60.00"))
        self.assertEqual(summary["interest_outstanding"], Decimal("90.00"))
        self.assertEqual(summary["interest_receivable_balance"], Decimal("70.00"))
        self.assertEqual(summary["last_accrual_date"], date(2026, 3, 31))

    def test_build_given_loan_detail_display_formats_metrics(self):
        storage_box = SimpleNamespace(position_for_item=lambda _loan_id: "A-02")
        loan = SimpleNamespace(
            id=1,
            get_weight_summary=[
                {
                    "itemtype": "Gold",
                    "total_weight": Decimal("12.50"),
                    "pure_weight": Decimal("11.8754"),
                },
                {
                    "itemtype": "Silver",
                    "total_weight": Decimal("5.00"),
                    "pure_weight": Decimal("4.25"),
                },
            ],
            current_value=Decimal("2000.00"),
            get_loan_amount=Decimal("1000.00"),
            total_due=Decimal("1250.00"),
            get_storage_box=lambda: storage_box,
            gross_accrued_interest=Decimal("150.00"),
            interest_paid_total=lambda: Decimal("60.00"),
            outstanding_interest=Decimal("90.00"),
            interest_receivable_balance=lambda: Decimal("70.00"),
            last_accrual_date=date(2026, 3, 31),
        )

        display = build_given_loan_detail_display(loan)

        self.assertEqual(display["weight"], "G:12.50 gms S:5.00 gms")
        self.assertEqual(display["pure"], "G:11.875 gms S:4.250 gms")
        self.assertEqual(display["lvratio"], 50.0)
        self.assertEqual(display["dvratio"], 62.0)
        self.assertEqual(display["location"], storage_box)
        self.assertEqual(display["position"], "A-02")
        self.assertEqual(display["interest_reporting"]["outstanding"], Decimal("90.00"))

    def test_build_given_loan_release_action_blocks_when_settlement_is_due(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            total_due=Decimal("1250.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )

        action = build_given_loan_release_action(loan)

        self.assertTrue(action["disabled"])
        self.assertEqual(action["outstanding_amount"], Decimal("250.00"))
        self.assertEqual(action["button_class"], "btn-outline-secondary")

    def test_build_given_loan_release_action_allows_zero_balance(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            total_due=Decimal("1000.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )

        action = build_given_loan_release_action(loan)

        self.assertFalse(action["disabled"])
        self.assertEqual(action["outstanding_amount"], Decimal("0.00"))
        self.assertEqual(action["button_class"], "btn-success")


class InterestAccrualReportingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loan.render", return_value=HttpResponse("ok"))
    @patch("apps.tenant_apps.girvi.views.loan.build_transition_actions", return_value=[])
    @patch("apps.tenant_apps.girvi.views.loan.build_runtime_loan_flow")
    @patch("apps.tenant_apps.girvi.views.loan.get_given_loan_detail_read_model")
    @patch("apps.tenant_apps.girvi.views.loan.ContentType.objects.get_for_model")
    @patch("apps.tenant_apps.girvi.views.loan.LoanChangeLog.objects.filter")
    def test_loan_detail_context_includes_interest_reporting_summary(
        self,
        mock_changelog_filter,
        _mock_content_type,
        mock_get_read_model,
        mock_build_runtime_flow,
        _mock_actions,
        mock_render,
    ):
        mock_changelog_filter.return_value.select_related.return_value.order_by.return_value = []
        mock_build_runtime_flow.return_value = SimpleNamespace(
            status="Disbursed",
            get_outgoing_transitions=lambda: [],
        )

        loan = MagicMock()
        loan.id = 1
        loan.pk = 1
        loan.loan_id = "GL-001"
        loan.get_weight_summary = []
        loan.current_value = Decimal("1500.00")
        loan.get_loan_amount = Decimal("1000.00")
        loan.total_due = Decimal("1125.00")
        loan.calculate_months_to_exceed_value.return_value = 3
        loan.renewals_as_source.all.return_value = []
        loan.renewal_record.first.return_value = None
        loan.borrower = SimpleNamespace(name="Test Customer")
        loan.gross_accrued_interest = Decimal("150.00")
        loan.interest_paid_total.return_value = Decimal("60.00")
        loan.outstanding_interest = Decimal("90.00")
        loan.interest_receivable_balance.return_value = Decimal("70.00")
        loan.last_accrual_date = date(2026, 3, 31)
        mock_get_read_model.return_value = {
            "loan": loan,
            "display": build_given_loan_detail_display(loan),
            "release_action": None,
            "renewals_as_source": [],
            "origin_renewal": None,
        }

        request = self.factory.get("/girvi/loan/detail/1/")
        request.user = self.user
        request.tenant = SimpleNamespace()
        request.htmx = False

        response = loan_detail.__wrapped__(request, pk=1)

        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args.args[2]
        self.assertEqual(context["interest_reporting"]["gross_accrued"], Decimal("150.00"))
        self.assertEqual(context["interest_reporting"]["paid"], Decimal("60.00"))
        self.assertEqual(context["interest_reporting"]["outstanding"], Decimal("90.00"))
        self.assertEqual(context["interest_reporting"]["receivable_balance"], Decimal("70.00"))
        self.assertEqual(context["interest_reporting"]["last_accrual_date"], date(2026, 3, 31))
