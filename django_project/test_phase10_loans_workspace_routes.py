from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import resolve

from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.models import Plan, Subscription
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class LoansWorkspaceRouteContractTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="phase10-loans-owner", password="test"
        )
        self.role, _ = Role.objects.get_or_create(name="Owner")
        self.plan = Plan.objects.create(
            name="Phase 10 trial",
            tier=Plan.PlanTierChoices.STARTER,
            price=0,
            description="Route contract trial",
        )
        self.workspace_a = self._workspace("phase10-a")
        self.workspace_b = self._workspace("phase10-b")
        self.loan_a = self._loan(self.workspace_a, "P10-A")
        self.loan_b = self._loan(self.workspace_b, "P10-B")
        self.client = Client()
        self.client.force_login(self.user)

    def _workspace(self, slug):
        workspace = Company.objects.create(
            schema_name=slug,
            name=slug,
            owner=self.user,
            creator=self.user,
        )
        Membership.objects.create(
            user=self.user, company=workspace, role=self.role
        )
        Subscription.objects.create(company=workspace, plan=self.plan)
        return workspace

    def _loan(self, workspace, number):
        with workspace_context(workspace.pk):
            party = Party.objects.create(display_name=f"Borrower {number}")
            license = LoanLicense.objects.create(
                workspace=workspace,
                name=f"License {number}",
                license_number=number,
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
            )
            series = LoanSeries.objects.create(
                license=license, code=number[-1], name=number
            )
            return PawnLoan.objects.create(
                workspace=workspace,
                product_version=ensure_test_product_version(workspace),
                license=license,
                series=series,
                borrower=party,
                loan_number=number,
                principal_amount=Decimal("1000.00"),
                monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 8, 17),
                created_by=self.user,
            )

    def _detail_url(self, workspace, loan):
        return f"/w/{workspace.schema_name}/loans/internal/{loan.pk}/"

    def test_explicit_path_controls_workspace_and_rls_visibility(self):
        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.workspace, self.workspace_a)
        self.assertContains(response, "P10-A")

    def test_named_workspace_loan_aliases_precede_the_deep_route_dispatcher(self):
        match = resolve(f"/w/{self.workspace_a.schema_name}/loans/list/")

        self.assertEqual(match.url_name, "workspace_slug_loan_list")

    def test_wrong_workspace_cannot_read_known_loan_id(self):
        response = self.client.get(self._detail_url(self.workspace_b, self.loan_a))

        self.assertEqual(response.status_code, 404)

    def test_profile_preference_cannot_override_explicit_path(self):
        self.user.profile.workspace = self.workspace_b
        self.user.profile.save(update_fields=["workspace"])

        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.wsgi_request.workspace, self.workspace_a)

    def test_removed_membership_denies_explicit_workspace_path(self):
        Membership.objects.filter(
            user=self.user, company=self.workspace_a
        ).delete()

        response = self.client.get(self._detail_url(self.workspace_a, self.loan_a))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/orgs/workspace/")

    def test_subscription_contract_allows_and_denies_without_bypass(self):
        allowed = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        self.assertEqual(allowed.status_code, 200)

        self.workspace_a.subscription.delete()
        denied = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        self.assertEqual(denied.status_code, 302)
        self.assertIn("/settings/billing/plans/", denied.url)

    def test_two_workspace_paths_remain_independent(self):
        response_a = self.client.get(self._detail_url(self.workspace_a, self.loan_a))
        response_b = self.client.get(self._detail_url(self.workspace_b, self.loan_b))

        self.assertContains(response_a, "P10-A")
        self.assertNotContains(response_a, "P10-B")
        self.assertContains(response_b, "P10-B")
        self.assertNotContains(response_b, "P10-A")

    def test_legacy_route_does_not_use_profile_preference_as_authority(self):
        self.user.profile.workspace = self.workspace_a
        self.user.profile.save(update_fields=["workspace"])

        response = self.client.get(f"/loans/internal/{self.loan_a.pk}/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/orgs/workspace/")
