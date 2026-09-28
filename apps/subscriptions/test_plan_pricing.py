from decimal import Decimal
from types import SimpleNamespace

from django.conf import settings
from django.template import Context, Engine
from django.test import SimpleTestCase

from .models import Plan


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
        html = self.render_plans(plan)
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
                self.assertNotIn("Save ₹", self.render_plans(plan))

    def test_disabled_checkout_and_trial_make_no_purchase_or_trial_promise(self):
        html = self.render_plans(self.plan(trial_days=14))
        self.assertIn("Online subscription payment is not yet available", html)
        self.assertNotIn("start-trial", html)
        self.assertNotIn("All plans come with", html)
        self.assertNotIn("/checkout/", html)

    def test_enabled_trial_uses_its_own_duration(self):
        html = self.render_plans(self.plan(trial_days=7), trial_start_enabled=True)
        self.assertIn("Start 7-day free trial", html)
        self.assertNotIn("14-day", html)
