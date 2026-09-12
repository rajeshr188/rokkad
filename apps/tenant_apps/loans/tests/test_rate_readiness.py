import uuid
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from apps.orgs.models import Membership, Role
from apps.onboarding.services.setup_checklist import _usable_rate_count
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.domain import (
    CollateralEconomicsError, CollateralTrancheInput, ValuationMethod,
    calculate_pawn_disbursal_economics,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries
from apps.tenant_apps.loans.selectors.rate_readiness import get_metal_rate_readiness
from apps.tenant_apps.loans.selectors.setup import get_pawn_setup_checklist
from apps.tenant_apps.loans.web.rate_readiness import pawn_valuation_readiness
from apps.tenant_apps.rates.models import Rate, RateSource


class RateReadinessTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "quote-readiness"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.owner = get_user_model().objects.create_user(username="quote-readiness-owner")
        tenant.name = "Quote readiness"
        tenant.owner = cls.owner
        tenant.creator = cls.owner
        tenant.save()
        Membership.objects.create(user=cls.owner, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        self.today = timezone.localdate()
        self.source = RateSource.objects.create(name="Market", location="Local")
        self.license = LoanLicense.objects.create(
            workspace=self.tenant, name="License", license_number=uuid.uuid4().hex,
            issued_on=self.today - timedelta(days=1), expires_on=self.today + timedelta(days=365),
        )
        self.series = LoanSeries.objects.create(license=self.license, name="Main", code="A")

    def quote(self, **kwargs):
        values = dict(rate_source=self.source, metal="Gold", purity="24k", currency="INR", buying_rate="7000", selling_rate="7100")
        values.update(kwargs)
        return Rate.objects.create(**values)

    def request(self, **changes):
        data = dict(series=self.series.pk, as_of=self.today, metals="GOLD", request_key=1)
        data.update(changes)
        request = RequestFactory().get("/readiness/", data)
        request.workspace = self.tenant
        request.user = self.owner
        return request

    def test_source_alone_is_not_ready_and_gold_does_not_require_silver(self):
        self.assertEqual(_usable_rate_count(self.tenant), 0)
        with patch("apps.tenant_apps.loans.selectors.setup.preview_number"), patch(
            "apps.tenant_apps.loans.selectors.setup.resolve_pawn_metal_interest_rate_policy"
        ), patch("apps.tenant_apps.loans.selectors.setup.resolve_pawn_loan_economic_policy", return_value=SimpleNamespace(valuation_method="LOWER_OF_CALCULATED_AND_APPRAISAL")):
            step = next(row for row in get_pawn_setup_checklist(self.tenant)["steps"] if row["key"] == "metal_rates")
            self.assertFalse(step["complete"])
            self.quote()
            step = next(row for row in get_pawn_setup_checklist(self.tenant)["steps"] if row["key"] == "metal_rates")
            self.assertTrue(step["complete"])
            self.assertIn("Silver: no usable", step["description"])
        self.assertEqual(_usable_rate_count(self.tenant), 1)

    def test_appraisal_only_setup_does_not_require_quotes(self):
        with patch("apps.tenant_apps.loans.selectors.setup.preview_number"), patch(
            "apps.tenant_apps.loans.selectors.setup.resolve_pawn_metal_interest_rate_policy"
        ), patch("apps.tenant_apps.loans.selectors.setup.resolve_pawn_loan_economic_policy", return_value=SimpleNamespace(valuation_method="LATEST_APPRAISAL")):
            step = next(row for row in get_pawn_setup_checklist(self.tenant)["steps"] if row["key"] == "metal_rates")
            self.assertTrue(step["complete"])

    def test_lookup_respects_currency_purity_date_and_positive_latest_price(self):
        self.quote(currency="USD")
        self.quote(purity="22k")
        self.quote(effective_at=timezone.now() + timedelta(days=2))
        self.assertFalse(get_metal_rate_readiness(workspace=self.tenant, as_of_date=self.today, metals=("GOLD",))[0]["usable"])
        self.quote(effective_at=timezone.now() - timedelta(days=3))
        row = get_metal_rate_readiness(workspace=self.tenant, as_of_date=self.today, metals=("GOLD",))[0]
        self.assertTrue(row["usable"])
        self.assertEqual(row["age_days"], 3)
        with self.assertRaises(ValidationError):
            self.quote(buying_rate="0")

    @patch("apps.tenant_apps.loans.web.rate_readiness.resolve_pawn_loan_economic_policy")
    def test_preflight_checks_selected_metals_date_and_policy(self, policy):
        policy.return_value = SimpleNamespace(valuation_method="LOWER_OF_CALCULATED_AND_APPRAISAL")
        response = pawn_valuation_readiness(self.request())
        self.assertContains(response, 'data-ready="false"')
        self.assertContains(response, 'target="_blank"')
        self.assertEqual(response["Cache-Control"], "no-store")
        self.quote()
        self.assertContains(pawn_valuation_readiness(self.request()), 'data-ready="true"')
        self.assertContains(pawn_valuation_readiness(self.request(metals="GOLD,SILVER")), 'data-ready="false"')
        self.assertContains(pawn_valuation_readiness(self.request(as_of=self.today - timedelta(days=1))), 'data-ready="false"')
        policy.return_value = SimpleNamespace(valuation_method="LATEST_APPRAISAL")
        self.assertContains(pawn_valuation_readiness(self.request(metals="SILVER")), 'data-ready="true"')

    def test_invalid_selection_scope_and_read_only_access(self):
        self.assertContains(pawn_valuation_readiness(self.request(as_of="bad")), 'data-ready="false"')
        with self.assertRaises(Http404):
            pawn_valuation_readiness(self.request(series=self.series.pk + 10000))
        with self.assertRaises(ValueError):
            get_metal_rate_readiness(workspace=SimpleNamespace(pk=self.tenant.pk + 1), as_of_date=self.today)
        request = self.request()
        request.user = get_user_model().objects.create_user(username="quote-outsider")
        with self.assertRaises(PermissionDenied):
            pawn_valuation_readiness(request)
        request = self.request()
        request.method = "POST"
        self.assertEqual(pawn_valuation_readiness(request).status_code, 405)

    @patch("apps.tenant_apps.loans.web.rate_readiness.resolve_pawn_loan_economic_policy")
    def test_stale_quote_allows_draft_but_explains_approval_requirement(self, policy):
        policy.return_value = SimpleNamespace(valuation_method="CALCULATED_METAL_VALUE")
        self.quote(effective_at=timezone.now() - timedelta(days=1))
        response = pawn_valuation_readiness(self.request())
        self.assertContains(response, 'data-ready="true"')
        self.assertContains(response, "approval needs today's loan date and quotes")


class MissingValuationInputTests(SimpleTestCase):
    def test_error_names_only_missing_inputs_and_targets_the_collateral_row(self):
        for price, appraisal, field, message in (
            (None, Decimal("1000"), "metal", "a usable metal valuation rate"),
            (Decimal("1000"), None, "latest_appraised_value", "a staff appraisal"),
            (None, None, "metal", "a usable metal valuation rate and a staff appraisal"),
        ):
            with self.subTest(price=price, appraisal=appraisal), self.assertRaises(CollateralEconomicsError) as caught:
                calculate_pawn_disbursal_economics(
                    [CollateralTrancheInput("2", "GOLD", Decimal("1"), Decimal("100"), Decimal("100"), Decimal("2"), price, appraisal)],
                    valuation_method=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
                    maximum_ltv_ratio=Decimal("0.8"),
                )
            self.assertEqual(str(caught.exception), f"Collateral 2 requires {message} for the configured valuation method.")
            self.assertEqual(caught.exception.reference, "2")
            self.assertEqual(caught.exception.field, field)
