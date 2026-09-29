import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.test import TestCase, override_settings

from apps.orgs.audit import AuditLog
from .models import Plan, Invoice, Payment, Subscription, RecurringAgreement


@override_settings(BILLING_ALLOW_TRIAL_START=False, BILLING_CHECKOUT_ENABLED=False, BILLING_RECURRING_ENABLED=False)
class PublicTrialCatalogTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(username="trial-catalog", email="operator@example.com", password=None)
        self.private = Plan.objects.create(name="Private monthly", tier="starter", price=1499, trial_days=0, max_users=6)

    def prepare(self, **options):
        out = StringIO()
        call_command("prepare_public_trial", actor_id=self.admin.pk, reason="Reviewed free offer", stdout=out, **options)
        return json.loads(out.getvalue())

    def test_preview_then_idempotent_apply_preserves_private_catalog_and_creates_no_access(self):
        before = Plan.objects.values().get(pk=self.private.pk)
        preview = self.prepare()
        self.assertIsNone(preview["plan_id"])
        self.assertEqual(Plan.objects.count(), 1)
        saved = self.prepare(apply=True)
        repeated = self.prepare(apply=True)
        self.assertEqual(saved["plan_id"], repeated["plan_id"])
        self.assertFalse(repeated["created"])
        self.assertFalse(saved["published"])
        self.assertEqual(saved["plan"]["max_users"], 6)
        self.assertEqual(saved["plan"]["trial_days"], 30)
        self.assertEqual(saved["plan"]["price"], "0.00")
        self.assertEqual(Plan.objects.values().get(pk=self.private.pk), before)
        self.assertEqual(AuditLog.objects.filter(action="BILLING_UPDATE").count(), 1)
        for model in (Invoice, Payment, Subscription, RecurringAgreement):
            self.assertFalse(model.objects.exists())

    def test_non_admin_and_active_publication_or_payment_flags_are_rejected(self):
        for flag in ("BILLING_ALLOW_TRIAL_START", "BILLING_CHECKOUT_ENABLED", "BILLING_RECURRING_ENABLED"):
            with override_settings(**{flag: True}), self.assertRaises(CommandError):
                self.prepare(apply=True)
        self.admin.is_superuser = False
        self.admin.save()
        with self.assertRaises(CommandError):
            self.prepare(apply=True)
        self.assertEqual(Plan.objects.count(), 1)

    def test_changed_plan_is_never_reconciled_over_existing_terms(self):
        saved = self.prepare(apply=True)
        Plan.objects.filter(pk=saved["plan_id"]).update(max_users=7)
        with self.assertRaises(CommandError):
            self.prepare(apply=True)
        self.assertEqual(Plan.objects.get(pk=saved["plan_id"]).max_users, 7)
