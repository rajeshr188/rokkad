import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.http import HttpResponse
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.configuration.models import PreferenceAuditLog, WorkspacePreferenceModel
from apps.orgs.models import Membership, Role
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import GivenLoan, License, LoanItem, Series
from apps.tenant_apps.loans.feature_flags import (
    LOANS_NEW_MODULE_ENABLED_KEY,
    is_new_loans_enabled,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan
from apps.tenant_apps.party.models import Party


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class LoansFeatureGateTests(TenantTestCase):
    test_schema_name = f"loans_gate_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-gate-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-gate-owner",
            defaults={"email": "loans-gate-owner@example.com"},
        )
        tenant.name = f"Loans Gate {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        self.owner = self.tenant.owner
        WorkspacePreferenceModel.objects.filter(
            instance=self.tenant,
            section="loan",
            name="new_module_enabled",
        ).delete()
        PreferenceAuditLog.objects.filter(
            workspace=self.tenant,
            key=LOANS_NEW_MODULE_ENABLED_KEY,
        ).delete()
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.owner)
        User = get_user_model()
        self.staff, _ = User.objects.get_or_create(
            username=f"loans-gate-staff-{self.tenant.pk}",
            defaults={"email": f"loans-gate-staff-{self.tenant.pk}@example.com"},
        )
        staff_role = Role.objects.get(name="Member")
        Membership.objects.get_or_create(
            user=self.staff,
            company=self.tenant,
            defaults={"role": staff_role},
        )
        self.party = Party.objects.create(display_name="Pilot Borrower")
        self.customer = Customer.objects.create(
            firstname="Pilot Borrower",
            party=self.party,
        )
        self.girvi_loan = self._create_girvi_loan()
        self.pawn_loan = self._create_pawn_loan()

    def test_default_preserves_girvi_and_owner_can_auditably_enable_then_disable(self):
        self.assertFalse(is_new_loans_enabled(self.tenant))

        enable = self.client.post(
            reverse("loans:loan_module_feature_gate"),
            {"enabled": "on"},
        )

        self.assertRedirects(
            enable,
            reverse("loans:loan_module_feature_gate"),
            fetch_redirect_response=False,
        )
        self.assertTrue(is_new_loans_enabled(self.tenant))
        audit = PreferenceAuditLog.objects.filter(
            workspace=self.tenant,
            key=LOANS_NEW_MODULE_ENABLED_KEY,
        ).latest("created_at")
        self.assertEqual(audit.changed_by, self.owner)
        self.assertEqual(audit.new_value, "True")

        self.client.post(reverse("loans:loan_module_feature_gate"), {})

        self.assertFalse(is_new_loans_enabled(self.tenant))
        self.assertTrue(PawnLoan.objects.filter(pk=self.pawn_loan.pk).exists())

    def test_enabled_gate_blocks_direct_girvi_get_post_and_preserves_customer_party(self):
        self._enable()
        create_url = reverse("girvi:girvi_loan_create")

        with patch(
            "apps.tenant_apps.girvi.views.loan._handle_loan_create_post"
        ) as legacy_create:
            get_response = self.client.get(create_url)
            post_response = self.client.post(create_url, {"loan_id": "BLOCKED"})

        self.assertRedirects(
            get_response,
            reverse("loans:pawn_loan_create"),
            fetch_redirect_response=False,
        )
        self.assertRedirects(
            post_response,
            reverse("loans:pawn_loan_create"),
            fetch_redirect_response=False,
        )
        legacy_create.assert_not_called()
        self.assertFalse(GivenLoan.objects.filter(loan_id="BLOCKED").exists())

        customer_response = self.client.get(
            reverse(
                "girvi:girvi_loan_create_for_customer",
                args=[self.customer.pk],
            )
        )
        self.assertEqual(
            customer_response.url,
            f"{reverse('loans:pawn_loan_create')}?party={self.party.pk}",
        )

    def test_canonical_route_switches_and_legacy_girvi_remains_reachable(self):
        canonical = reverse(
            "workspace_slug_loans",
            kwargs={"workspace_slug": self.tenant.schema_name},
        )
        with patch(
            "apps.tenant_apps.girvi.views.dashboard.girvi_dashboard",
            return_value=HttpResponse("girvi-primary"),
        ):
            response = self.client.get(canonical)
        self.assertContains(response, "girvi-primary")

        self._enable()
        with patch(
            "apps.tenant_apps.loans.views.pawn_loan_list",
            return_value=HttpResponse("loans-primary"),
        ):
            response = self.client.get(canonical)
        self.assertContains(response, "loans-primary")

        legacy_list = self.client.get(reverse("girvi:girvi_loan_list"))
        self.assertEqual(legacy_list.status_code, 200)
        self.assertContains(legacy_list, "New Loan in Loans")

    def test_enabled_sidebar_labels_primary_and_legacy_owners(self):
        self._enable()

        response = self.client.get(reverse("loans:pawn_loan_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Legacy Girvi")
        self.assertContains(response, 'bi bi-cash-coin"></i> Loans')

    def test_non_admin_cannot_change_cutover_by_direct_url(self):
        staff_client = TenantClient(self.tenant)
        staff_client.force_login(self.staff)
        cutover_url = reverse("loans:loan_module_feature_gate")

        self.assertEqual(staff_client.get(cutover_url).status_code, 403)
        self.assertEqual(
            staff_client.post(cutover_url, {"enabled": "on"}).status_code,
            403,
        )
        self.assertFalse(is_new_loans_enabled(self.tenant))

    def _enable(self):
        response = self.client.post(
            reverse("loans:loan_module_feature_gate"),
            {"enabled": "on"},
        )
        self.assertEqual(response.status_code, 302)

    def _create_girvi_loan(self):
        license = License.objects.create(
            name="Legacy License",
            license_number=f"GL-{uuid.uuid4().hex[:8]}",
        )
        series = Series.objects.create(
            license=license,
            name="Legacy",
            prefix="G",
            max_limit=5,
            loan_type="Given",
        )
        loan = GivenLoan.objects.create(
            loan_id="G-PILOT-00001",
            series=series,
            borrower=self.customer,
            borrower_party=self.party,
            loan_date=timezone.now(),
            status="Draft",
        )
        LoanItem.objects.create(
            loan=loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("91.60"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Legacy ring",
        )
        GivenLoan.objects.filter(pk=loan.pk).update(status="ActiveCurrent")
        loan.refresh_from_db()
        return loan

    def _create_pawn_loan(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Pilot License",
            license_number=f"PL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(
            license=license,
            name="Pilot",
            code="P",
        )
        return PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            borrower=self.party,
            loan_number="PL-P-00001",
            principal_amount=Decimal("800.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 4),
            tenure_months=3,
            created_by=self.owner,
        )
