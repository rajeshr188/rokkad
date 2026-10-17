from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.access_policy import record_access_decision, workspace_activity
from apps.subscriptions.models import (
    Invoice,
    Payment,
    Plan,
    Subscription,
    SubscriptionEvent,
)
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import (
    PawnLoanEconomicPolicy,
    PawnMetalInterestRatePolicy,
    PawnLoanEvent,
)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class InitialBusinessSetupAccessTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="initial-setup-owner"
        )
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse("app_workspace_create"),
            {"name": "Initial setup business", "theme": ""},
            follow=True,
        )
        self.workspace = Company.objects.get(owner=self.owner)
        self.created_response = response

    def url(self, name, **kwargs):
        return reverse(name, kwargs={"workspace_slug": self.workspace.slug, **kwargs})

    def test_creation_follows_through_to_setup_without_starting_billing(self):
        setup = self.url("workspace_slug_settings_setup")
        self.assertEqual(self.created_response.status_code, 200)
        self.assertEqual(self.created_response.redirect_chain, [(setup, 302)])
        self.assertContains(self.created_response, "setup-stepper")
        self.assertContains(
            self.created_response,
            "Start an available trial or activate a plan before recording loans.",
        )
        self.assertEqual(workspace_activity(self.workspace).mode, "recovery")
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_all_journey_steps_and_configuration_forms_are_available_to_owner(self):
        for step in ("business", "starting", "license", "lending", "terms", "review"):
            with self.subTest(step=step):
                response = self.client.get(
                    self.url("workspace_slug_settings_setup"), {"step": step}
                )
                self.assertContains(response, "setup-stepper")
                if step == "review":
                    self.assertContains(response, "Review free trial and access")
                    self.assertNotContains(response, "Create your first loan")
        for route in (
            "workspace_loans:license_create",
            "workspace_loans:loan_product_list",
            "workspace_loans:pawn_economics_setup",
            "workspace_loans:origination_settings",
            "workspace_loans:loan_workflow_settings",
            "workspace_loans:document_layout_list",
            "workspace_rates:rate_create",
            "workspace_rates:ratesource_create",
        ):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(self.url(route)).status_code, 200)

    def test_owner_can_save_terms_and_resume_without_creating_a_subscription(self):
        data = {
            "action": "configuration",
            "setup_step": "terms",
            "setup_path": "new",
            "configuration-metals_to_configure": "GOLD",
            "configuration-gold_monthly_interest_rate": "2",
            "configuration-silver_monthly_interest_rate": "",
            "configuration-effective_from": timezone.localdate().isoformat(),
            "configuration-valuation_method": "LATEST_APPRAISAL",
            "configuration-maximum_ltv_ratio": ".8",
            "configuration-advance_interest_periods": "1",
            "configuration-interest_method": "SIMPLE",
            "configuration-partial_month_method": "FULL_MONTH",
            "configuration-partial_month_cutoff_days": "15",
            "configuration-partial_month_lower_fraction": ".5",
            "configuration-capitalization_interval_periods": "12",
            "configuration-rounding_method": "PER_ACCRUAL_PERIOD",
            "configuration-currency_quantum": ".01",
        }
        response = self.client.post(
            self.url("workspace_loans:pawn_economics_setup"), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(response.context["configuration_review"])
        with workspace_context(self.workspace.pk):
            self.assertFalse(
                PawnLoanEconomicPolicy.objects.filter(workspace=self.workspace).exists()
            )
        data.update(
            economic_confirm="1",
            economic_acknowledged="on",
            economic_review_token=response.context["configuration_review_token"],
        )
        response = self.client.post(
            self.url("workspace_loans:pawn_economics_setup"), data, follow=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.redirect_chain,
            [(self.url("workspace_slug_settings_setup") + "?step=terms&path=new", 302)],
        )
        with workspace_context(self.workspace.pk):
            self.assertEqual(
                PawnLoanEconomicPolicy.objects.filter(workspace=self.workspace).count(),
                1,
            )
            self.assertEqual(
                PawnMetalInterestRatePolicy.objects.filter(
                    workspace=self.workspace
                ).count(),
                1,
            )
            self.assertFalse(PawnLoanEvent.objects.exists())
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(SubscriptionEvent.objects.exists())

    def test_lending_imports_funding_and_customer_entry_still_require_activation(self):
        plans = self.url("workspace_subscriptions:plan-list")
        for route in (
            "workspace_slug_loan_create",
            "workspace_slug_party_create",
            "workspace_portability:guided_upload",
            "workspace_loans:funding_loan_draft_create",
        ):
            with self.subTest(route=route):
                for method in ("get", "post"):
                    response = getattr(self.client, method)(
                        self.url(route), {"setup_step": "terms"}
                    )
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response.url, plans)
        self.assertFalse(Subscription.objects.exists())

    def test_no_subscription_setup_does_not_grant_admin_staff_or_outsider_access(self):
        for role_name in ("Admin", "Member"):
            actor = get_user_model().objects.create_user(
                username="initial-" + role_name.lower()
            )
            Membership.objects.create(
                user=actor,
                company=self.workspace,
                role=Role.objects.get_or_create(name=role_name)[0],
            )
            self.client.force_login(actor)
            self.assertEqual(
                self.client.get(self.url("workspace_slug_settings_setup")).status_code,
                403,
            )
            self.assertEqual(
                self.client.post(
                    self.url("workspace_loans:loan_workflow_settings"),
                    {"mode": "SIMPLE", "setup_step": "lending"},
                ).status_code,
                403,
            )
        actor = get_user_model().objects.create_user(username="initial-outsider")
        self.client.force_login(actor)
        response = self.client.get(self.url("workspace_slug_settings_setup"))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, self.url("workspace_subscriptions:plan-list"))

    def test_expired_cancelled_and_restricted_workspaces_do_not_get_setup_writes(self):
        plan = Plan.objects.create(name="Initial test trial", tier="starter", price=0)
        subscription = Subscription.objects.create(
            company=self.workspace,
            plan=plan,
            trial_end_date=timezone.now() - timedelta(days=8),
        )
        Subscription.objects.filter(pk=subscription.pk).update(
            trial_end_date=timezone.now() - timedelta(days=8)
        )
        for status in ("trial", "cancelled", "past_due", "expired"):
            Subscription.objects.filter(pk=subscription.pk).update(status=status)
            for method in ("get", "post"):
                response = getattr(self.client, method)(
                    self.url("workspace_loans:loan_workflow_settings"),
                    {"mode": "SIMPLE", "setup_step": "lending"},
                )
                self.assertEqual(response.status_code, 403)
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.loan_workflow, "EXTENDED")

    def test_platform_readonly_decision_and_lifecycle_remain_stronger(self):
        admin = get_user_model().objects.create_superuser(
            username="initial-platform",
            email="initial-platform@example.test",
            password="test",
        )
        record_access_decision(
            workspace=self.workspace,
            actor=admin,
            mode="read_only",
            expires_at=timezone.now() + timedelta(days=1),
            reason="Restricted review",
        )
        self.assertEqual(
            self.client.get(self.url("workspace_slug_settings_setup")).status_code, 403
        )
        self.workspace.lifecycle_state = "SUSPENDED"
        self.workspace.save(update_fields=["lifecycle_state"])
        self.assertEqual(
            self.client.get(self.url("workspace_slug_settings_setup")).status_code, 403
        )

    def test_navigation_marker_and_non_form_methods_do_not_bypass_route_policy(self):
        response = self.client.delete(
            self.url("workspace_loans:loan_workflow_settings"),
            {"setup_step": "lending"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url("workspace_subscriptions:plan-list"))
