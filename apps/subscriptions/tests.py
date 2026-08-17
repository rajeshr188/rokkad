from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import RequestFactory, TestCase, override_settings
from django.template.loader import render_to_string
from django.urls import resolve

from apps.subscriptions.services import (
    SubscriptionAccessService,
    build_billing_account_defaults,
    build_entitlement_defaults,
)


class SubscriptionAccessServiceTests(TestCase):
    def setUp(self):
        self.service = SubscriptionAccessService()

    def test_allows_access_for_active_workspace_subscription(self):
        workspace = SimpleNamespace(id=1, schema_name="tenant_a")
        membership = SimpleNamespace(user=SimpleNamespace(id=7), role=SimpleNamespace(name="Admin"))
        subscription = SimpleNamespace(status="active", is_active=True)

        decision = self.service.evaluate_access(
            user=SimpleNamespace(id=7),
            workspace=workspace,
            membership=membership,
            subscription=subscription,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "AUTHORIZED")

    def test_blocks_access_when_subscription_is_not_active(self):
        workspace = SimpleNamespace(id=1, schema_name="tenant_a")
        membership = SimpleNamespace(user=SimpleNamespace(id=7), role=SimpleNamespace(name="Admin"))
        subscription = SimpleNamespace(status="past_due", is_active=False)

        decision = self.service.evaluate_access(
            user=SimpleNamespace(id=7),
            workspace=workspace,
            membership=membership,
            subscription=subscription,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "SUBSCRIPTION_INACTIVE")

    def test_blocks_feature_access_when_entitlement_is_disabled(self):
        workspace = SimpleNamespace(id=1, schema_name="tenant_a")
        membership = SimpleNamespace(user=SimpleNamespace(id=7), role=SimpleNamespace(name="Admin"))
        subscription = SimpleNamespace(status="active", is_active=True)
        entitlement = SimpleNamespace(feature_code="advanced_reporting", enabled=False)

        decision = self.service.evaluate_access(
            user=SimpleNamespace(id=7),
            workspace=workspace,
            membership=membership,
            subscription=subscription,
            entitlement=entitlement,
            feature_code="advanced_reporting",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "FEATURE_BLOCKED")

    def test_build_billing_account_defaults_use_workspace_context(self):
        company = SimpleNamespace(name="Acme", owner=SimpleNamespace(email="ops@acme.example"))
        subscription = SimpleNamespace(company=company)

        defaults = build_billing_account_defaults(subscription)

        self.assertEqual(defaults["company"], company)
        self.assertEqual(defaults["billing_email"], "ops@acme.example")
        self.assertEqual(defaults["contact_name"], "Acme")

    def test_build_entitlement_defaults_include_plan_limits(self):
        plan = SimpleNamespace(
            has_advanced_reporting=True,
            has_multi_warehouse=False,
            max_users=7,
            max_products=250,
            max_warehouses=3,
            max_transactions_per_month=1000,
            max_invoices_per_month=900,
        )
        subscription = SimpleNamespace(plan=plan)

        entitlements = build_entitlement_defaults(subscription)
        feature_codes = {entry["feature_code"] for entry in entitlements}

        self.assertIn("reporting.advanced", feature_codes)
        self.assertIn("workspace.max_members", feature_codes)
        self.assertIn("inventory.max_products", feature_codes)
        self.assertTrue(any(entry["feature_code"] == "reporting.advanced" and entry["enabled"] is True for entry in entitlements))
        self.assertTrue(any(entry["feature_code"] == "workspace.max_members" and entry["value"] == "7" for entry in entitlements))

    def test_backfill_command_supports_dry_run(self):
        out = StringIO()
        call_command("backfill_subscription_billing", dry_run=True, stdout=out)
        output = out.getvalue()

        self.assertIn("Backfill complete", output)

    @override_settings(
        STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
            },
        }
    )
    def test_workspace_plan_page_shell_reverses_billing_with_workspace_slug(self):
        class EmptyPlans:
            def __iter__(self):
                return iter(())

            def count(self):
                return 0

        workspace = SimpleNamespace(
            id=9, schema_name="jcl", name="JCL", theme="#ff0000", logo=None
        )
        user = SimpleNamespace(
            id=1,
            pk=1,
            is_authenticated=True,
            username="owner",
            get_full_name=lambda: "Owner",
            profile=SimpleNamespace(id=1, pk=1, workspace=workspace),
        )
        request = RequestFactory().get("/w/jcl/settings/billing/plans/")
        request.user = user
        request.workspace = workspace
        request.resolver_match = resolve(request.path)

        with patch(
            "django_project.context_processors.get_effective_permissions",
            return_value=set(),
        ), patch(
            "django_project.context_processors.get_workspace_role_name",
            return_value="Owner",
        ):
            html = render_to_string(
                "subscriptions/plan_list.html",
                {
                    "plans": EmptyPlans(),
                    "workspace": workspace,
                    "user_workspace": workspace,
                    "user_role": "Owner",
                },
                request=request,
            )

        self.assertIn("/w/jcl/settings/billing/dashboard/", html)
