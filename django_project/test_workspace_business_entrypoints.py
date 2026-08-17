from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.models import Plan, Subscription


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class WorkspaceBusinessEntrypointTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="workspace-entry-owner", password="test"
        )
        self.workspace = Company.all_objects.create(
            name="Workspace Entry",
            schema_name="workspace-entry",
            owner=self.owner,
            creator=self.owner,
        )
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(
            user=self.owner,
            company=self.workspace,
            role=owner_role,
        )
        plan = Plan.objects.create(
            name="Workspace entry plan",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="Business entrypoint regression plan",
        )
        subscription = Subscription.objects.create(
            company=self.workspace,
            plan=plan,
            end_date=timezone.now() + timedelta(days=30),
        )
        subscription.status = Subscription.StatusChoices.ACTIVE
        subscription.save(update_fields=["status"])
        self.client.force_login(self.owner)

    def test_primary_business_entrypoints_keep_explicit_workspace_identity(self):
        route_names = (
            "workspace_slug_parties",
            "workspace_slug_loan_list",
            "workspace_slug_notifications",
            "workspace_slug_rates",
        )

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(
                    reverse(
                        route_name,
                        kwargs={"workspace_slug": self.workspace.schema_name},
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.wsgi_request.workspace)
                self.assertEqual(response.wsgi_request.workspace.pk, self.workspace.pk)
                self.assertNotContains(
                    response,
                    "Select a workspace before accessing this feature.",
                )
