import json
from copy import deepcopy
from decimal import Decimal
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company
from apps.platform_mail.models import Delivery
from . import recurring
from .models import (Invoice, Payment, Plan, RecurringAgreement, RecurringAgreementEvent,
                     RecurringPlanBinding, Subscription)
from .razorpay_service import BillingProviderError, RazorpayService


@override_settings(BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_fixture",
                   RAZORPAY_KEY_SECRET="private-fixture", BILLING_TAX_RATE="0",
                   BILLING_SELLER_NAME="Fictional Seller", BILLING_SELLER_ADDRESS="1 Example Street",
                   BILLING_SELLER_TAX_STATUS="unregistered",
                   BILLING_CHECKOUT_ENABLED=False, BILLING_RECURRING_ENABLED=False,
                   BILLING_ALLOW_TRIAL_START=False)
class LiveCatalogTests(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="catalog-admin", is_superuser=True)
        self.plan = Plan.objects.create(name="Reviewed offer", tier="starter", price=Decimal("1499"),
                                       yearly_price=Decimal("14990"), max_users=6)
        self.entity = {"id": "plan_livefixture", "entity": "plan", "period": "monthly", "interval": 1,
                       "item": {"amount": 149900, "currency": "INR"}, "notes": {"private": "omit-remote-notes"}}
        self.fetch = patch.object(RazorpayService, "get_plan", side_effect=lambda _: deepcopy(self.entity)).start()
        self.create = patch.object(RazorpayService, "create_subscription").start()
        self.addCleanup(patch.stopall)
        self.args = dict(actor=self.actor, plan_id=self.plan.pk, cycle="monthly",
                         provider_plan_id=self.entity["id"], reason="Reviewed live catalog only", mode="live")

    def assert_no_financial_effect(self):
        for model in (RecurringAgreement, RecurringAgreementEvent, Subscription, Invoice, Payment, Delivery):
            self.assertFalse(model.objects.exists(), model.__name__)
        self.create.assert_not_called()

    def test_missing_seller_and_nonzero_tax_block_live_catalog_before_provider_read(self):
        for changes in ({"BILLING_SELLER_NAME": ""}, {"BILLING_SELLER_TAX_STATUS": "registered"},
                        {"BILLING_TAX_RATE": "18"}):
            with self.subTest(changes=changes), override_settings(**changes):
                with self.assertRaises(ValidationError):
                    recurring.review_plan_binding(**self.args)
        self.fetch.assert_not_called()
        self.assertFalse(RecurringPlanBinding.objects.exists())

    @override_settings(BILLING_ALLOW_TRIAL_START=True)
    def test_trial_publication_must_be_paused_before_live_catalog_review_or_binding(self):
        for action in (recurring.review_plan_binding, recurring.bind_plan):
            with self.subTest(action=action.__name__), self.assertRaisesMessage(PermissionDenied, "trial signup"):
                action(**self.args)
        self.fetch.assert_not_called()
        self.assertFalse(RecurringPlanBinding.objects.exists())
        self.assert_no_financial_effect()

    def test_preview_reports_verified_terms_without_saving_or_exposing_provider_payload(self):
        output = StringIO()
        call_command("prepare_recurring_agreement", "--actor-id", str(self.actor.pk), "bind",
                     "--plan-id", str(self.plan.pk), "--cycle", "monthly", "--provider-plan-id",
                     self.entity["id"], "--reason", "Launch review", "--mode", "live", "--preview", stdout=output)
        report = json.loads(output.getvalue())
        self.assertEqual(report["mode"], "live")
        self.assertTrue(report["preview"])
        self.assertFalse(report["binding_saved"])
        self.assertTrue(report["live_recurring_supported"])
        self.assertEqual(report["snapshot"]["amount"], 149900)
        self.assertEqual(next(x["value"] for x in report["snapshot"]["entitlements"]
                              if x["feature_code"] == "workspace.max_members"), "6")
        self.assertNotIn("private-fixture", output.getvalue())
        self.assertNotIn("omit-remote-notes", output.getvalue())
        self.assertFalse(RecurringPlanBinding.objects.exists())
        self.assert_no_financial_effect()

    def test_live_registration_is_idempotent_and_does_not_enable_creation(self):
        binding = recurring.bind_plan(**self.args)
        self.assertEqual(binding.mode, "live")
        self.assertEqual(recurring.bind_plan(**self.args).pk, binding.pk)
        self.assertEqual(RecurringPlanBinding.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            recurring.create_agreement(workspace_id=999, actor=self.actor, binding_id=binding.pk,
                                       total_count=12, request_key=uuid4())
        self.assert_no_financial_effect()

    def test_annual_terms_use_separate_exact_provider_amount(self):
        self.entity.update(period="yearly")
        self.entity["item"]["amount"] = 1499000
        binding = recurring.bind_plan(**{**self.args, "cycle": "yearly"})
        self.assertEqual(binding.snapshot["amount"], 1499000)
        self.assertEqual(binding.snapshot["base_amount"], "14990.00")
        self.assert_no_financial_effect()

    def test_authority_and_explicit_matching_mode_are_required_before_provider_read(self):
        for field, value in (("is_superuser", False), ("is_active", False)):
            original = getattr(self.actor, field)
            setattr(self.actor, field, value)
            with self.assertRaises(PermissionDenied):
                recurring.bind_plan(**self.args)
            setattr(self.actor, field, original)
        for changes in ({"mode": "test"}, {"mode": "bad"}):
            with self.assertRaises((PermissionDenied, ValidationError)):
                recurring.bind_plan(**{**self.args, **changes})
        for settings in ({"RAZORPAY_KEY_ID": "rzp_test_fixture"}, {"BILLING_PROVIDER_MODE": "disabled"},
                         {"BILLING_CHECKOUT_ENABLED": True}, {"BILLING_RECURRING_ENABLED": True}):
            with override_settings(**settings), self.assertRaises((PermissionDenied, ValidationError)):
                recurring.bind_plan(**self.args)
        self.fetch.assert_not_called()
        self.assertFalse(RecurringPlanBinding.objects.exists())

    def test_test_binding_blocks_live_catalog_before_provider_read(self):
        RecurringPlanBinding.objects.create(plan=self.plan, mode="test", provider_plan_id="plan_oldtest",
            snapshot=recurring._offer(self.plan, "monthly"), actor=self.actor, reason="Historical fixture")
        for action in (recurring.review_plan_binding, recurring.bind_plan):
            with self.assertRaisesMessage(ValidationError, "another provider mode"):
                action(**self.args)
        self.fetch.assert_not_called()
        self.assertEqual(RecurringPlanBinding.objects.count(), 1)

    def historical_invoice(self, snapshot):
        workspace = Company.all_objects.create(name="Legacy", schema_name="legacy", owner=self.actor, creator=self.actor)
        subscription = Subscription.objects.create(company=workspace, plan=self.plan, start_date=timezone.now(),
                                                     end_date=timezone.now())
        Invoice.objects.create(subscription=subscription, invoice_number="legacy-unknown", base_amount=1,
                               gst_rate=0, invoice_date=timezone.now().date(), due_date=timezone.now().date(),
                               checkout_snapshot=snapshot)

    def test_unclassified_one_off_evidence_blocks_live_catalog(self):
        self.historical_invoice({})
        with self.assertRaisesMessage(ValidationError, "no verified mode"):
            recurring.bind_plan(**self.args)
        self.fetch.assert_not_called()
        self.assertFalse(RecurringPlanBinding.objects.exists())

    def test_test_one_off_evidence_blocks_live_catalog_without_a_recurring_binding(self):
        self.historical_invoice({"provider_mode": "test"})
        with self.assertRaisesMessage(ValidationError, "another provider mode"):
            recurring.bind_plan(**self.args)
        self.fetch.assert_not_called()
        self.assertFalse(RecurringPlanBinding.objects.exists())

    def test_mode_conflict_appearing_during_fetch_blocks_registration(self):
        def changed(_):
            RecurringPlanBinding.objects.create(plan=self.plan, mode="test", provider_plan_id="plan_oldtest",
                snapshot=recurring._offer(self.plan, "monthly"), actor=self.actor, reason="Conflicting fixture")
            return deepcopy(self.entity)
        self.fetch.side_effect = changed
        with self.assertRaisesMessage(ValidationError, "another provider mode"):
            recurring.bind_plan(**self.args)
        self.assertFalse(RecurringPlanBinding.objects.filter(mode="live").exists())

    def test_wrong_provider_terms_or_unavailable_provider_never_save(self):
        for path, value in (("amount", 1), ("currency", "USD")):
            original = self.entity["item"][path]
            self.entity["item"][path] = value
            with self.assertRaises(ValidationError):
                recurring.bind_plan(**self.args)
            self.entity["item"][path] = original
        self.fetch.side_effect = BillingProviderError("Unavailable")
        with self.assertRaises(BillingProviderError):
            recurring.bind_plan(**self.args)
        self.assertFalse(RecurringPlanBinding.objects.exists())
        self.assert_no_financial_effect()

    def test_offer_change_during_fetch_is_rejected(self):
        def changed(_):
            Plan.objects.filter(pk=self.plan.pk).update(max_users=7)
            return deepcopy(self.entity)
        self.fetch.side_effect = changed
        with self.assertRaisesMessage(ValidationError, "offer changed"):
            recurring.bind_plan(**self.args)
        self.assertFalse(RecurringPlanBinding.objects.exists())

    def test_conflicting_existing_terms_rejected_even_in_preview(self):
        recurring.bind_plan(**self.args)
        Plan.objects.filter(pk=self.plan.pk).update(max_users=7)
        with self.assertRaisesMessage(ValidationError, "different terms"):
            recurring.review_plan_binding(**self.args)
        self.assertEqual(RecurringPlanBinding.objects.count(), 1)

    def test_test_registration_cannot_mix_into_existing_live_catalog(self):
        recurring.bind_plan(**self.args)
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture",
                               BILLING_RECURRING_ENABLED=True):
            with self.assertRaisesMessage(ValidationError, "another provider mode"):
                recurring.bind_plan(**{**self.args, "mode": "test", "provider_plan_id": "plan_testfixture"})
        self.assertEqual(RecurringPlanBinding.objects.count(), 1)

    def test_paused_test_preview_does_not_enable_test_registration(self):
        with override_settings(BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_ID="rzp_test_fixture"):
            args = {**self.args, "mode": "test"}
            self.assertEqual(recurring.review_plan_binding(**args)["mode"], "test")
            with self.assertRaisesMessage(PermissionDenied, "preparation is disabled"):
                recurring.bind_plan(**args)
        self.fetch.assert_called_once()
        self.assertFalse(RecurringPlanBinding.objects.exists())
        self.assert_no_financial_effect()
