from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

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

    def test_rates_crud_and_valuation_lookup_work_during_default_cache_outage(self):
        from django.core.cache import cache
        from apps.tenancy.context import workspace_context
        from apps.tenant_apps.rates.facade import (
            RATE_FOUND, RATE_MISSING, get_latest_commodity_valuation_rate,
        )
        from apps.tenant_apps.rates.models import Rate, RateSource

        with workspace_context(self.workspace.pk):
            source = RateSource.objects.create(name="Counter source", location="Local")
        outage = Mock(side_effect=ConnectionError("Simulated default-cache outage"))
        scope = {"workspace_slug": self.workspace.slug}
        data = {
            "rate_source": source.pk, "metal": "Gold", "currency": "INR",
            "purity": "24k", "buying_rate": "7000.00", "selling_rate": "7100.00",
        }
        with patch.multiple(cache, get=outage, set=outage, delete=outage):
            response = self.client.get(reverse("workspace_rates:rate_list", kwargs=scope))
            self.assertEqual(response.status_code, 200)
            response = self.client.post(reverse("workspace_rates:rate_create", kwargs=scope), data)
            self.assertEqual(response.status_code, 302)
            with workspace_context(self.workspace.pk):
                lookup = get_latest_commodity_valuation_rate(
                    commodity_code="GOLD", as_of=timezone.localdate(),
                )
                self.assertEqual(lookup.status, RATE_FOUND)
                self.assertEqual(lookup.rate.buying_rate, Decimal("7000.00"))
                rate_id = lookup.rate.pk
            detail_scope = {**scope, "pk": rate_id}
            response = self.client.get(reverse("workspace_rates:rate_detail", kwargs=detail_scope))
            self.assertEqual(response.status_code, 200)
            data["buying_rate"] = "7200.00"
            response = self.client.post(reverse("workspace_rates:rate_update", kwargs=detail_scope), data)
            self.assertEqual(response.status_code, 302)
            with workspace_context(self.workspace.pk):
                lookup = get_latest_commodity_valuation_rate(commodity_code="GOLD")
                self.assertEqual(lookup.rate.buying_rate, Decimal("7200.00"))
            response = self.client.post(reverse("workspace_rates:rate_delete", kwargs=detail_scope))
            self.assertEqual(response.status_code, 302)
            with workspace_context(self.workspace.pk):
                self.assertFalse(Rate.objects.filter(pk=rate_id).exists())
                self.assertEqual(
                    get_latest_commodity_valuation_rate(commodity_code="GOLD").status,
                    RATE_MISSING,
                )
            outage.assert_not_called()

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
                        kwargs={"workspace_slug": self.workspace.slug},
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.assertIsNotNone(response.wsgi_request.workspace)
                self.assertEqual(response.wsgi_request.workspace.pk, self.workspace.pk)
                self.assertNotContains(
                    response,
                    "Select a workspace before accessing this feature.",
                )
