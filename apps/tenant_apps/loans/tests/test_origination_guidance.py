from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, RequestFactory, override_settings
from django.conf import settings
from apps.tenant_apps.loans.web.appraisal import collateral_appraisal_suggestion
from apps.tenant_apps.loans.web.origination import borrower_outstanding


@override_settings(TEMPLATES=[{"BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": settings.TEMPLATES[0]["DIRS"], "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]}}])
class OriginationGuidanceTests(SimpleTestCase):
    def setUp(self):
        mock_khata = patch("apps.tenant_apps.loans.web.origination.portfolio_summary", return_value=dict(
            active_count=0, unavailable=0, principal=Decimal(0), interest=Decimal(0)))
        mock_khata.start()
        self.addCleanup(mock_khata.stop)
        self.workspace = SimpleNamespace(pk=7, slug="alpha")
        self.access = SimpleNamespace(can=lambda name: True, require=lambda name: None)

    def request(self, **values):
        request = RequestFactory().get("/", values)
        request.user = SimpleNamespace(is_authenticated=True)
        request.workspace = self.workspace
        request.loans_workspace_access = self.access
        return request

    @patch("apps.tenant_apps.loans.access._resolve_loans_access")
    @patch("apps.tenant_apps.loans.web.appraisal.get_object_or_404")
    @patch("apps.tenant_apps.loans.web.appraisal.resolve_pawn_loan_economic_policy")
    @patch("apps.tenant_apps.loans.web.appraisal.get_latest_commodity_valuation_rate")
    def test_ltv_follows_entered_appraisal_scope_and_reports_excess(self, lookup, resolve, series, access):
        access.return_value = self.workspace, self.access
        series.return_value = SimpleNamespace(pk=3, license_id=9)
        resolve.return_value = SimpleNamespace(maximum_ltv_ratio=Decimal("0.8"),
            valuation_method="LOWER_OF_CALCULATED_AND_APPRAISAL", currency_quantum=Decimal("0.01"))
        lookup.return_value = SimpleNamespace(status="FOUND", rate=SimpleNamespace(buying_rate=Decimal("10000"), effective_at=datetime(2026,9,28,tzinfo=timezone.utc)))
        values = dict(metal="GOLD",gross_weight="2",net_weight="1",purity="75",as_of="2026-09-28",request_key=1,series=3,appraisal="5000",principal="4001")
        response = collateral_appraisal_suggestion(self.request(**values))
        self.assertContains(response, "LTV limit: 80%")
        self.assertContains(response, "4,000")
        self.assertContains(response, "exceeds this limit")
        self.assertEqual(resolve.call_args.kwargs["license_id"], 9)
        self.assertEqual(resolve.call_args.kwargs["series_id"], 3)
        self.assertEqual(resolve.call_args.kwargs["workspace_id"], 7)
        values.update(appraisal="10000", principal="5000")
        response = collateral_appraisal_suggestion(self.request(**values))
        self.assertContains(response, "6,000")
        self.assertNotContains(response, "exceeds this limit")
        lookup.return_value.rate.effective_at = datetime(2026,9,27,tzinfo=timezone.utc)
        response = collateral_appraisal_suggestion(self.request(**values))
        self.assertContains(response, "same-day metal price")
        self.assertNotContains(response, "Maximum loan for this item")

    @patch("apps.tenant_apps.loans.access._resolve_loans_access")
    @patch("apps.tenant_apps.loans.web.origination.get_object_or_404")
    @patch("apps.tenant_apps.loans.web.origination.PawnLoan.objects.filter")
    @patch("apps.tenant_apps.loans.web.origination._optional_policy_snapshot", return_value=None)
    @patch("apps.tenant_apps.loans.web.origination.calculate_pawn_loan_balance")
    def test_borrower_card_covers_all_loans_and_never_treats_missing_as_zero(self, balance, policy, loans, party, access):
        access.return_value = self.workspace, self.access
        party.return_value = SimpleNamespace(pk=33)
        relation = SimpleNamespace(all=lambda: ())
        loans.return_value.select_related.return_value.prefetch_related.return_value = [
            SimpleNamespace(loan_events=relation, collateral_items=relation) for _ in range(25)]
        balance.return_value = SimpleNamespace(principal_outstanding=Decimal(100),interest_outstanding=Decimal(20),fees_outstanding=Decimal(5),total_due=Decimal(125))
        response = borrower_outstanding(self.request(borrower=33))
        self.assertContains(response, "25 active loans")
        self.assertContains(response, "3,125")
        self.assertEqual(response["Cache-Control"].find("no-store") >= 0, True)
        loans.assert_called_once_with(workspace=self.workspace,borrower=party.return_value,state="ACTIVE")
        balance.side_effect = ValueError("Unavailable source")
        response = borrower_outstanding(self.request(borrower=33))
        self.assertContains(response, "complete total cannot be shown")
        self.assertNotContains(response, "₹0")
