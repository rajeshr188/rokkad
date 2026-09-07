from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import DatabaseError, IntegrityError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.subscriptions import entitlements
from apps.subscriptions.billing import effective_billing_state, transition_subscription
from apps.subscriptions.models import (
    Plan,
    ProviderWebhookEvent,
    Subscription,
    SubscriptionEntitlement,
    SubscriptionEvent,
)
from apps.subscriptions.services import ensure_entitlements_for_subscription
from apps.subscriptions import views


class Phase4BillingTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="billing-owner")
        self.workspace = Company.all_objects.create(
            name="Billing Workspace",
            schema_name="billing-workspace",
            owner=self.owner,
            creator=self.owner,
        )
        self.plan = Plan.objects.create(
            name="Pilot",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("1000.00"),
            description="Pilot plan",
            max_users=7,
            has_api_access=True,
        )
        self.subscription = Subscription.objects.create(
            company=self.workspace,
            plan=self.plan,
            end_date=timezone.now() + timedelta(days=30),
        )

    def test_expired_trial_is_derived_without_mutating_stored_status(self):
        self.subscription.trial_end_date = timezone.now() - timedelta(seconds=1)
        self.subscription.save(update_fields=["trial_end_date"])

        decision = effective_billing_state(self.subscription)
        self.subscription.refresh_from_db()

        self.assertEqual(decision.status, Subscription.StatusChoices.PAST_DUE)
        self.assertFalse(decision.commercially_available)
        self.assertEqual(self.subscription.status, Subscription.StatusChoices.TRIAL)

    def test_transition_is_locked_event_backed_and_idempotent(self):
        activated, changed = transition_subscription(
            subscription=self.subscription,
            target_status=Subscription.StatusChoices.ACTIVE,
            event_type="payment.captured",
            payload={"provider_event_id": "evt-1"},
        )
        repeated, repeated_changed = transition_subscription(
            subscription=activated,
            target_status=Subscription.StatusChoices.ACTIVE,
            event_type="payment.captured",
            payload={"provider_event_id": "evt-1"},
        )

        self.assertTrue(changed)
        self.assertFalse(repeated_changed)
        self.assertEqual(repeated.status, Subscription.StatusChoices.ACTIVE)
        self.assertEqual(SubscriptionEvent.objects.count(), 1)

    def test_invalid_transition_fails_closed(self):
        with self.assertRaises(ValidationError):
            transition_subscription(
                subscription=self.subscription,
                target_status=Subscription.StatusChoices.EXPIRED,
                event_type="invalid",
            )

    def test_entitlements_are_namespaced_typed_and_missing_fails_closed(self):
        transition_subscription(
            subscription=self.subscription,
            target_status=Subscription.StatusChoices.ACTIVE,
            event_type="payment.captured",
        )
        ensure_entitlements_for_subscription(self.subscription)

        self.assertTrue(entitlements.enabled(self.workspace, "api.access"))
        self.assertEqual(entitlements.limit(self.workspace, "workspace.max_members"), 7)
        self.assertFalse(entitlements.enabled(self.workspace, "unknown.feature"))
        self.assertIsNone(entitlements.limit(self.workspace, "unknown.limit"))

    def test_plan_projection_preserves_explicit_override(self):
        row = SubscriptionEntitlement.objects.create(
            subscription=self.subscription,
            feature_code="workspace.max_members",
            enabled=True,
            value="99",
            source="override",
            override_actor=self.owner,
            override_reason="Contracted pilot capacity",
        )

        ensure_entitlements_for_subscription(self.subscription)
        row.refresh_from_db()

        self.assertEqual(row.value, "99")
        self.assertEqual(row.source, "override")

    def test_provider_event_identity_is_unique_per_provider(self):
        ProviderWebhookEvent.objects.create(
            provider="razorpay", provider_event_id="evt-1"
        )
        with self.assertRaises(IntegrityError):
            ProviderWebhookEvent.objects.create(
                provider="razorpay", provider_event_id="evt-1"
            )

    def test_default_plan_catalog_is_idempotent_and_contains_no_retired_capacity(self):
        Plan.objects.all().delete()

        call_command("create_default_plans", verbosity=0)
        call_command("create_default_plans", verbosity=0)

        self.assertEqual(Plan.objects.count(), 3)
        self.assertEqual(
            set(Plan.objects.values_list("tier", flat=True)),
            set(Plan.PlanTierChoices.values),
        )
        self.assertFalse(
            Plan.objects.filter(
                max_products__gt=0,
            ).exists()
        )
        self.assertFalse(Plan.objects.filter(max_warehouses__gt=0).exists())
        self.assertFalse(Plan.objects.filter(has_multi_warehouse=True).exists())

    @override_settings(RAZORPAY_WEBHOOK_SECRET="phase4-secret")
    def test_webhook_replay_is_acknowledged_without_reprocessing(self):
        body = json.dumps({"event": "payment.authorized", "payload": {}}).encode()
        signature = hmac.new(
            b"phase4-secret", body, hashlib.sha256
        ).hexdigest()
        factory = RequestFactory()

        with patch.object(
            views.RazorpayService, "handle_payment_webhook", return_value=True
        ) as handler:
            first = views.razorpay_webhook(
                factory.post(
                    "/subscriptions/webhook/razorpay/",
                    data=body,
                    content_type="application/json",
                    HTTP_X_RAZORPAY_SIGNATURE=signature,
                    HTTP_X_RAZORPAY_EVENT_ID="evt-replay",
                )
            )
            second = views.razorpay_webhook(
                factory.post(
                    "/subscriptions/webhook/razorpay/",
                    data=body,
                    content_type="application/json",
                    HTTP_X_RAZORPAY_SIGNATURE=signature,
                    HTTP_X_RAZORPAY_EVENT_ID="evt-replay",
                )
            )

        self.assertEqual((first.status_code, second.status_code), (200, 200))
        handler.assert_called_once()
        self.assertEqual(ProviderWebhookEvent.objects.count(), 1)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class BillingMiddlewareAcceptanceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="no-billing-owner", password="test"
        )
        self.workspace = Company.all_objects.create(
            name="No Billing Workspace",
            schema_name="no-billing-workspace",
            owner=self.owner,
            creator=self.owner,
        )
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(
            user=self.owner,
            company=self.workspace,
            role=owner_role,
        )
        self.client.force_login(self.owner)

    def create_subscription(self, *, status, trial_end_date=None):
        plan = Plan.objects.create(
            name=f"{status} plan",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="Middleware acceptance plan",
        )
        subscription = Subscription.objects.create(
            company=self.workspace,
            plan=plan,
            end_date=timezone.now() + timedelta(days=30),
        )
        subscription.status = status
        subscription.trial_end_date = trial_end_date
        subscription.save(update_fields=["status", "trial_end_date"])
        return subscription

    def test_business_app_is_blocked_when_workspace_has_no_subscription(self):
        response = self.client.get("/w/no-billing-workspace/parties/")

        self.assertRedirects(
            response,
            "/w/no-billing-workspace/settings/billing/plans/",
            fetch_redirect_response=False,
        )

    def test_billing_evaluation_error_fails_closed(self):
        with patch(
            "django_project.middleware.Subscription.objects.filter",
            side_effect=DatabaseError("billing unavailable"),
        ):
            response = self.client.get("/w/no-billing-workspace/parties/")

        self.assertEqual(response.status_code, 503)

    def test_active_subscription_allows_business_app(self):
        self.create_subscription(status=Subscription.StatusChoices.ACTIVE)

        response = self.client.get("/w/no-billing-workspace/parties/")

        self.assertEqual(response.status_code, 200)

    def test_current_trial_allows_business_app(self):
        self.create_subscription(
            status=Subscription.StatusChoices.TRIAL,
            trial_end_date=timezone.now() + timedelta(days=1),
        )

        response = self.client.get("/w/no-billing-workspace/parties/")

        self.assertEqual(response.status_code, 200)

    def test_billing_dashboard_uses_workspace_member_count(self):
        self.create_subscription(status=Subscription.StatusChoices.ACTIVE)

        response = self.client.get(
            "/w/no-billing-workspace/settings/billing/dashboard/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_user_count"], 1)
        self.assertEqual(response.context["user_overage"], 0)
        self.assertContains(response, "1/5")

    def test_expired_trial_is_limited_to_billing_recovery(self):
        self.create_subscription(
            status=Subscription.StatusChoices.TRIAL,
            trial_end_date=timezone.now() - timedelta(seconds=1),
        )

        response = self.client.get("/w/no-billing-workspace/parties/")

        self.assertRedirects(
            response,
            "/w/no-billing-workspace/settings/billing/dashboard/",
            fetch_redirect_response=False,
        )

    @override_settings(BILLING_ALLOW_TRIAL_START=True)
    def test_owner_can_explicitly_start_trial_with_projected_entitlements(self):
        plan = Plan.objects.create(
            name="Trial Starter",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="Trial plan",
            max_users=4,
            trial_days=14,
        )

        response = self.client.post(
            f"/w/no-billing-workspace/settings/billing/plans/{plan.pk}/start-trial/"
        )

        self.assertEqual(response.status_code, 302)
        subscription = Subscription.objects.get(company=self.workspace)
        self.assertEqual(subscription.status, Subscription.StatusChoices.TRIAL)
        self.assertGreater(subscription.trial_end_date, timezone.now())
        self.assertTrue(subscription.events.filter(event_type="trial.started").exists())
        self.assertEqual(
            entitlements.limit(self.workspace, "workspace.max_members"), 4
        )

    @override_settings(BILLING_ALLOW_TRIAL_START=True)
    def test_trial_start_is_post_only_and_duplicate_safe(self):
        plan = Plan.objects.create(
            name="Trial Starter",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="Trial plan",
        )
        url = f"/w/no-billing-workspace/settings/billing/plans/{plan.pk}/start-trial/"

        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(Subscription.objects.filter(company=self.workspace).count(), 1)

    @override_settings(BILLING_ALLOW_TRIAL_START=True)
    def test_non_owner_cannot_start_trial(self):
        member = get_user_model().objects.create_user(
            username="trial-member", password="test"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(
            user=member,
            company=self.workspace,
            role=member_role,
        )
        plan = Plan.objects.create(
            name="Trial Starter",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="Trial plan",
        )
        self.client.force_login(member)

        response = self.client.post(
            f"/w/no-billing-workspace/settings/billing/plans/{plan.pk}/start-trial/"
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Subscription.objects.filter(company=self.workspace).exists())
