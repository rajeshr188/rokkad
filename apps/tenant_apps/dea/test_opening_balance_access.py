from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection
from django.test import RequestFactory
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase

from .models import AccountingPeriod, AccountType, Ledger
from .views.opening_balance import opening_balance_wizard


User = get_user_model()


class OpeningBalanceWizardAccessTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_opening_balance"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="dea-ob-owner",
            email="dea-ob-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-ob-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-ob-user",
            email="dea-ob-user@example.com",
            password="testpass123",
        )
        self.factory = RequestFactory()
        self.period = AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        self.cash = Ledger.objects.create(
            AccountType=asset_type,
            name="Opening Balance Cash",
            code="1.TEST.OB.CASH",
        )

    def test_opening_balance_wizard_page_is_available(self):
        request = self.factory.get(reverse("dea_opening_balance_wizard"))
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = opening_balance_wizard(request)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Opening Balance Wizard", response.content)

    def test_step1_post_redirects_to_step2_with_query_string(self):
        request = self.factory.post(
            reverse("dea_opening_balance_wizard"),
            data={"period_id": str(self.period.pk)},
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = opening_balance_wizard(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            f"{reverse('dea_opening_balance_wizard')}?step=2",
        )

    def test_step2_post_preserves_numeric_amounts_for_step3_review(self):
        request = self.factory.post(
            f"{reverse('dea_opening_balance_wizard')}?step=2",
            data={
                f"ledger_{self.cash.pk}": "100.00",
                f"ledger_{self.cash.pk}_currency": "INR",
            },
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session["ob_period_id"] = str(self.period.pk)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = opening_balance_wizard(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            request.session["ob_balances"][f"ledger_{self.cash.pk}"]["amount"],
            "100.00",
        )

        review_request = self.factory.get(
            f"{reverse('dea_opening_balance_wizard')}?step=3"
        )
        review_request.user = self.user
        session_middleware.process_request(review_request)
        review_request.session = request.session
        setattr(review_request, "_messages", FallbackStorage(review_request))

        review_response = opening_balance_wizard(review_request)

        self.assertEqual(review_response.status_code, 200)
        self.assertIn(b"100.00", review_response.content)
