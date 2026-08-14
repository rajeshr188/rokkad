from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.selectors import (
    build_given_loan_action_readiness,
    build_loan_settlement_balance,
    build_repayment_preview,
    build_given_loan_detail_display,
    build_given_loan_detail_read_model,
    build_given_loan_release_action,
)
from apps.tenant_apps.girvi.views.loan import loan_detail


class InterestAccrualReadModelTests(SimpleTestCase):
    def test_build_loan_settlement_balance_uses_component_split(self):
        loan = SimpleNamespace(
            pk=None,
            get_loan_amount=Decimal("1000.00"),
            outstanding_interest=Decimal("125.00"),
            get_total_principal_payments=lambda: Decimal("300.00"),
            get_total_interest_payments=lambda: Decimal("25.00"),
            get_total_payments=lambda: Decimal("325.00"),
        )

        settlement = build_loan_settlement_balance(loan)

        self.assertEqual(settlement.principal_due, Decimal("700.00"))
        self.assertEqual(settlement.interest_due, Decimal("125.00"))
        self.assertEqual(settlement.total_outstanding, Decimal("825.00"))
        self.assertEqual(settlement.total_paid, Decimal("325.00"))
        self.assertEqual(settlement.overpayment, Decimal("0.00"))

    def test_build_repayment_preview_suggests_exact_split(self):
        loan = SimpleNamespace(
            pk=None,
            get_loan_amount=Decimal("1000.00"),
            outstanding_interest=Decimal("125.00"),
            get_total_principal_payments=lambda: Decimal("300.00"),
            get_total_interest_payments=lambda: Decimal("25.00"),
            get_total_payments=lambda: Decimal("325.00"),
        )

        preview = build_repayment_preview(loan)

        self.assertEqual(preview.suggested_total_amount, Decimal("825.00"))
        self.assertEqual(preview.suggested_interest_amount, Decimal("125.00"))
        self.assertEqual(preview.suggested_principal_amount, Decimal("700.00"))
        self.assertFalse(preview.is_settled)

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
        loan.status = "ActiveCurrent"
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
        self.assertEqual(display["dvratio"], 55.00000000000001)
        self.assertEqual(display["location"], storage_box)
        self.assertEqual(display["position"], "A-02")
        self.assertEqual(display["interest_reporting"]["outstanding"], Decimal("90.00"))

    def test_build_given_loan_release_action_collects_when_settlement_is_due(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            total_due=Decimal("1250.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )
        settlement = SimpleNamespace(
            total_due=Decimal("1250.00"),
            total_outstanding=Decimal("250.00"),
        )

        with patch(
            "apps.tenant_apps.girvi.selectors.build_loan_settlement_balance",
            return_value=settlement,
        ):
            action = build_given_loan_release_action(loan)

        self.assertFalse(action["disabled"])
        self.assertEqual(action["outstanding_amount"], Decimal("250.00"))
        self.assertTrue(action["needs_final_settlement"])
        self.assertEqual(action["button_class"], "btn-success")

    def test_build_given_loan_release_action_allows_zero_balance(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            total_due=Decimal("1000.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )
        settlement = SimpleNamespace(
            total_due=Decimal("1000.00"),
            total_outstanding=Decimal("0.00"),
        )

        with patch(
            "apps.tenant_apps.girvi.selectors.build_loan_settlement_balance",
            return_value=settlement,
        ):
            action = build_given_loan_release_action(loan)

        self.assertFalse(action["disabled"])
        self.assertEqual(action["outstanding_amount"], Decimal("0.00"))
        self.assertEqual(action["button_class"], "btn-success")

    def test_build_given_loan_action_readiness_prefers_enabled_release(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            current_value=Decimal("2000.00"),
            total_due=Decimal("1000.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )
        release_action = build_given_loan_release_action(loan)

        with patch(
            "apps.tenant_apps.girvi.selectors.get_given_loan_journal_entries"
        ) as journal_entries:
            journal_entries.return_value.count.return_value = 1
            readiness = build_given_loan_action_readiness(
                loan,
                transition_actions=[{"title": "Renew Loan", "disabled": False}],
                release_action=release_action,
                changelog=[SimpleNamespace()],
            )

        self.assertEqual(readiness["primary_action"]["title"], "Start Release Workflow")
        self.assertEqual(readiness["settlement"]["label"], "Clear")
        self.assertEqual(readiness["collateral"]["label"], "Adequate")
        self.assertEqual(readiness["accounting"]["label"], "Posted")
        self.assertEqual(readiness["timeline"]["event_count"], 1)

    def test_build_given_loan_action_readiness_explains_collectable_settlement(self):
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            current_value=Decimal("2000.00"),
            total_due=Decimal("1250.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
        )
        settlement = SimpleNamespace(
            total_due=Decimal("1250.00"),
            total_outstanding=Decimal("250.00"),
        )

        with patch(
            "apps.tenant_apps.girvi.selectors.build_loan_settlement_balance",
            return_value=settlement,
        ), patch(
            "apps.tenant_apps.girvi.selectors.get_given_loan_journal_entries"
        ) as journal_entries:
            release_action = build_given_loan_release_action(loan)
            journal_entries.return_value.count.return_value = 0
            readiness = build_given_loan_action_readiness(
                loan,
                transition_actions=[],
                release_action=release_action,
                changelog=[],
            )

        self.assertFalse(readiness["primary_action"]["disabled"])
        self.assertTrue(readiness["primary_action"]["needs_final_settlement"])
        self.assertEqual(readiness["settlement"]["label"], "Outstanding")
        self.assertEqual(readiness["accounting"]["label"], "No posted journal")

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.get_source_posting_status")
    def test_build_given_loan_action_readiness_uses_adapter_posting_status(self, mock_status):
        mock_status.return_value = {
            "label": "Pending",
            "badge_class": "bg-warning text-dark",
            "posted_payment_count": 0,
            "pending_payment_count": 1,
            "failed_outbox_count": 0,
            "pending_outbox_count": 0,
        }
        loan = SimpleNamespace(
            id=1,
            status="ActiveCurrent",
            release=None,
            current_value=Decimal("2000.00"),
            total_due=Decimal("1000.00"),
            get_total_payments=lambda: Decimal("1000.00"),
            closure_exception_approved=False,
            _meta=SimpleNamespace(app_label="girvi", model_name="givenloan"),
            pk=1,
        )

        readiness = build_given_loan_action_readiness(
            loan,
            transition_actions=[],
            release_action=None,
            changelog=[],
        )

        self.assertEqual(readiness["accounting"]["label"], "Pending")
        self.assertEqual(readiness["accounting"]["pending_payment_count"], 1)


class InterestAccrualReportingViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loan.render", return_value=HttpResponse("ok"))
    @patch("apps.tenant_apps.girvi.views.loan.build_given_loan_action_readiness")
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
        mock_action_readiness,
        mock_render,
    ):
        mock_changelog_filter.return_value.select_related.return_value.order_by.return_value = []
        mock_build_runtime_flow.return_value = SimpleNamespace(
            status="ActiveCurrent",
            get_outgoing_transitions=lambda: [],
        )
        mock_action_readiness.return_value = {
            "primary_action": None,
            "primary_reason": "No action available",
        }

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
        self.assertEqual(context["action_readiness"]["primary_reason"], "No action available")
