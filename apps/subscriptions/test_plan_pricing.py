from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.template import Context, Engine
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from .models import Plan, Subscription, Invoice, Payment


class PlanPricingTests(SimpleTestCase):
    def plan(self, **changes):
        return Plan(pk=1, name="Rokkad", tier="starter", price=Decimal("1499.00"),
                    yearly_price=changes.pop("yearly_price", Decimal("14990.00")),
                    max_users=6, **changes)

    def render_plans(self, plan, **context):
        # Render the real offer template without unrelated Workspace shell queries.
        engine = Engine(
            dirs=[settings.BASE_DIR / "templates"],
            loaders=[("django.template.loaders.locmem.Loader", {
                "base_workspace_settings.html": "{% block mgmt_content %}{% endblock %}",
                "subscriptions/_navigation.html": "",
            }), "django.template.loaders.filesystem.Loader"],
            libraries={"static": "django.templatetags.static"},
        )
        return engine.get_template("subscriptions/plan_list.html").render(Context({
            "plans": [plan], "request": SimpleNamespace(workspace=SimpleNamespace(slug="pricing")),
            "billing_checkout_enabled": False, "trial_start_enabled": False, **context,
        }, use_l10n=False))

    def test_working_offer_shows_actual_saving_and_owner_included_seats(self):
        plan = self.plan()
        self.assertEqual(plan.annual_savings, Decimal("2998.00"))
        html = self.render_plans(plan, billing_checkout_enabled=True)
        self.assertIn("Save ₹2998.00 compared with 12 monthly payments", html)
        self.assertIn("6 members including the owner", html)
        self.assertNotIn("20%", html)
        self.assertNotIn("₹999", html)
        self.assertIn("before applicable tax", html)

    def test_unavailable_or_more_expensive_annual_offer_never_advertises_saving(self):
        for annual in (None, Decimal("0"), Decimal("17988"), Decimal("18000")):
            with self.subTest(annual=annual):
                plan = self.plan(yearly_price=annual)
                self.assertEqual(plan.annual_savings, Decimal("0.00"))
                self.assertNotIn("Save ₹", self.render_plans(plan, billing_checkout_enabled=True))

    def test_disabled_checkout_and_trial_make_no_purchase_or_trial_promise(self):
        html = self.render_plans(self.plan(trial_days=14))
        self.assertIn("Review recurring payments", html)
        self.assertNotIn("1499", html)
        self.assertNotIn("/year", html)
        self.assertNotIn("plan-card", html)
        self.assertNotIn("start-trial", html)
        self.assertNotIn("All plans come with", html)
        self.assertNotIn("/checkout/", html)

    def test_unselected_trial_is_not_published(self):
        html = self.render_plans(self.plan(trial_days=7), trial_start_enabled=True)
        self.assertNotIn("Start 7-day free trial", html)
        self.assertNotIn("14-day", html)
        self.assertNotIn("/year", html)

    def test_catalog_does_not_invent_legacy_feature_or_support_promises(self):
        html = self.render_plans(self.plan(has_api_access=True, has_advanced_reporting=True,
            has_approvals_workflow=True, has_custom_fields=True), billing_checkout_enabled=True)
        self.assertIn("6 members including the owner", html)
        for text in ("Monthly Operations", "Advanced Reporting", "Approval Workflow",
                     "API Access", "Custom Fields", "Priority Support", "Detailed Feature Comparison"):
            self.assertNotIn(text, html)


@override_settings(BILLING_CHECKOUT_ENABLED=False, BILLING_ALLOW_TRIAL_START=False,
    BILLING_RECURRING_ENABLED=True,
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CatalogPublicationTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="catalog-owner")
        self.workspace = Company.all_objects.create(name="Catalog workspace", schema_name="catalog",
            owner=self.owner, creator=self.owner)
        Membership.objects.create(company=self.workspace, user=self.owner,
            role=Role.objects.get_or_create(name="Owner")[0])
        self.plan = Plan.objects.create(name="Unpublished monthly pilot", tier="starter",
            price=Decimal("1499.00"), max_users=6, description="Private offer")
        self.subscription = Subscription.objects.create(company=self.workspace, plan=self.plan)
        self.client.force_login(self.owner)

    def url(self, name):
        return reverse("workspace_subscriptions:"+name, kwargs={"workspace_slug":self.workspace.slug})

    def test_preparing_active_plan_does_not_publish_it_or_change_existing_trial(self):
        before = Subscription.objects.values().get(pk=self.subscription.pk)
        price = Plan.objects.get(pk=self.plan.pk).yearly_price
        self.assertGreater(price, 0)  # Includes the existing automatic annual default.
        response = self.client.get(self.url("plan-list"))
        self.assertContains(response, "Review recurring payments")
        self.assertEqual(list(response.context["plans"]), [])
        self.assertNotContains(response, "Unpublished monthly pilot")
        self.assertNotContains(response, "1499")
        self.assertNotContains(response, "/year")
        self.assertEqual(Subscription.objects.values().get(pk=self.subscription.pk), before)
        self.assertEqual(Plan.objects.get(pk=self.plan.pk).yearly_price, price)
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    @override_settings(BILLING_CHECKOUT_ENABLED=True)
    def test_explicit_self_service_checkout_retains_catalog(self):
        response = self.client.get(self.url("plan-list"))
        self.assertContains(response, "Unpublished monthly pilot")
        self.assertContains(response, "6 members including the owner")
        self.assertContains(response, "/year")

    @override_settings(BILLING_ALLOW_TRIAL_START=True)
    def test_trial_flag_alone_cannot_publish_private_catalog(self):
        response = self.client.get(self.url("plan-list"))
        self.assertNotContains(response, "Unpublished monthly pilot")
        self.assertNotContains(response, "/year")
        self.assertNotContains(response, "/checkout/")

    def test_dashboard_capacity_is_not_an_automatic_charge_or_legacy_feature_offer(self):
        Plan.objects.filter(pk=self.plan.pk).update(max_users=0, extra_user_price=999)
        response = self.client.get(self.url("dashboard"))
        self.assertContains(response, "Member capacity:")
        for text in ("Current overage charge", "Warehouses", "Multi-Warehouse Support",
                     "Advanced Reporting", "Approval Workflow", "API Access", "Custom Fields"):
            self.assertNotContains(response, text)
        self.assertFalse(Invoice.objects.exists())

    def test_other_workspace_member_cannot_read_owner_catalog(self):
        staff = get_user_model().objects.create_user(username="catalog-staff")
        Membership.objects.create(company=self.workspace, user=staff,
            role=Role.objects.get_or_create(name="Viewer")[0])
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url("plan-list")).status_code, 403)
