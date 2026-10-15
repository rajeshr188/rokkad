"""Owner HTTP creation with real transaction boundaries and mocked provider I/O."""
from datetime import timedelta
from io import StringIO
from unittest.mock import patch
from uuid import uuid4

from allauth.account.models import EmailAddress
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import connection, transaction
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.platform_mail.models import Delivery
from apps.platform_mail.tests import MAIL_SETTINGS
from apps.tenancy.context import current_workspace_id, workspace_context
from . import public_recurring as public
from .models import Invoice, Payment, Plan, RecurringAgreement, Subscription
from .razorpay_service import BillingProviderError, RazorpayService
from . import test_live_recurring as live_tests
from .test_live_recurring import LIVE_SETTINGS


@override_settings(**{**LIVE_SETTINGS, "BILLING_RECURRING_ENABLED": True, "BILLING_TAX_RATE": "0",
    "BILLING_SELLER_NAME": "Fictional Seller", "BILLING_SELLER_ADDRESS": "1 Example Street",
    "BILLING_SELLER_TAX_STATUS": "unregistered", "BILLING_RECURRING_WORKSPACE_IDS": []})
class PublicRecurringTests(TransactionTestCase):
    created_entity = live_tests.LiveCreationTests.created_entity

    def setUp(self):
        live_tests.LiveCreationTests.setUp(self)
        self.owner.email = "fictional-owner@example.com"
        self.owner.save(update_fields=["email"])
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True, primary=True)
        selected = override_settings(BILLING_PUBLIC_RECURRING_BINDING_ID=self.binding.pk)
        selected.enable()
        self.addCleanup(selected.disable)
        self.client.force_login(self.owner)
        self.url = reverse("workspace_subscriptions:recurring", kwargs={"workspace_slug": self.workspace.slug})
        self.start_url = reverse("public-recurring-start")

    def token(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        return page.context["monthly_consent"]

    def submit(self, token=None, **changes):
        data = {"offer_token": token or self.token(), "accepted_terms": public.TERMS}
        data.update(changes)
        return self.client.post(self.start_url, data)

    def test_http_creation_commits_consent_before_provider_and_reuses_original(self):
        token = self.token()
        original = self.created_entity

        def provider(payload):
            self.assertIsNone(current_workspace_id())
            saved = RecurringAgreement.objects.get()
            terms = saved.events.get(event_type="creation.requested").detail["accepted_terms"]
            self.assertEqual(terms["version"], public.TERMS)
            self.assertEqual(terms["snapshot"], self.binding.snapshot)
            self.assertEqual(terms["actor_id"], self.owner.pk)
            return original(payload)

        self.provider_create.side_effect = provider
        self.assertRedirects(self.submit(token), self.url, fetch_redirect_response=False)
        self.assertRedirects(self.submit(token), self.url, fetch_redirect_response=False)
        self.assertEqual(RecurringAgreement.objects.count(), 1)
        self.provider_create.assert_called_once()
        self.assertFalse(Subscription.objects.exists())
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())
        page = self.client.get(self.url)
        self.assertContains(page, 'id="recurring-authorize"')
        self.assertNotContains(page, 'name="offer_token"')

    def test_second_browser_review_and_timeout_cannot_create_another_agreement(self):
        token, second = self.token(), self.token()
        self.provider_create.side_effect = BillingProviderError("Outcome unknown; contact support.")
        for consent in (token, token, second):
            self.assertEqual(self.submit(consent).status_code, 302)
        self.provider_create.assert_called_once()
        self.assertEqual(RecurringAgreement.objects.get().state, "unknown")
        self.assertContains(self.client.get(self.url), "Creation needs provider reconciliation")

    def test_paused_publication_or_recurring_blocks_saved_offer_without_provider_calls(self):
        token = self.token()
        for config in ({"BILLING_PUBLIC_RECURRING_BINDING_ID": 0}, {"BILLING_RECURRING_ENABLED": False}):
            with self.subTest(config=config), override_settings(**config):
                self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
                self.assertIn(self.submit(token).status_code, (302, 403))
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_consent_missing_tampered_expired_and_changed_terms_are_rejected(self):
        token = self.token()
        self.assertEqual(self.submit(token, accepted_terms="").status_code, 400)
        self.assertEqual(self.submit(token + "tampered").status_code, 400)
        with patch("django.core.signing.time.time", return_value=timezone.now().timestamp() + 1801):
            self.assertEqual(self.submit(token).status_code, 400)
        data = signing.loads(token, salt=public.SALT)
        for field, value in (("total_count", 24), ("terms", "old"), ("binding_id", 999999)):
            changed = signing.dumps({**data, field: value}, salt=public.SALT)
            self.assertEqual(self.submit(changed).status_code, 302)
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_changed_price_seats_seller_and_mode_require_new_review(self):
        token = self.token()
        for field, value in (("price", 1599), ("max_users", 7), ("is_active", False)):
            old = getattr(self.plan, field)
            Plan.objects.filter(pk=self.plan.pk).update(**{field: value})
            self.assertEqual(self.submit(token).status_code, 302)
            Plan.objects.filter(pk=self.plan.pk).update(**{field: old})
        for config in ({"BILLING_SELLER_NAME": "Changed Seller"}, {"RAZORPAY_KEY_ID": "rzp_test_fixture"}):
            with override_settings(**config):
                self.assertIn(self.submit(token).status_code, (302, 403))
        self.provider_create.assert_not_called()

    def test_platform_admin_and_other_owner_cannot_accept_someone_elses_offer(self):
        token = self.token()
        self.client.force_login(self.admin)
        self.assertEqual(self.submit(token).status_code, 403)
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        self.provider_create.assert_not_called()

    def test_cross_workspace_and_owner_transfer_recheck_canonical_ownership(self):
        token = self.token()
        data = signing.loads(token, salt=public.SALT)
        other = Company.all_objects.create(name="Other", schema_name="other-monthly",
            owner=self.admin, creator=self.admin)
        # Even a correctly signed stale/wrong-Workspace review is not authority.
        wrong = signing.dumps({**data, "workspace_id": other.pk}, salt=public.SALT)
        self.assertEqual(self.submit(wrong).status_code, 403)
        Company.all_objects.filter(pk=self.workspace.pk).update(owner=self.admin)
        self.assertEqual(self.submit(token).status_code, 403)
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_capacity_and_lifecycle_are_rechecked_after_review(self):
        token = self.token()
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state="SUSPENDED")
        self.assertEqual(self.submit(token).status_code, 302)
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state="ACTIVE")
        from django.contrib.auth import get_user_model
        for number in range(6):
            user = get_user_model().objects.create_user(username=f"staff-{number}")
            Membership.objects.create(company=self.workspace, user=user,
                role=Role.objects.get_or_create(name="Member")[0])
        self.assertEqual(self.submit(token).status_code, 302)
        self.provider_create.assert_not_called()

    def test_lost_membership_unverified_email_and_changed_owner_block_before_provider(self):
        token = self.token()
        EmailAddress.objects.filter(user=self.owner).update(verified=False)
        self.assertEqual(self.submit(token).status_code, 302)
        EmailAddress.objects.filter(user=self.owner).update(verified=True)
        Membership.objects.filter(company=self.workspace, user=self.owner).delete()
        self.assertEqual(self.submit(token).status_code, 403)
        self.provider_create.assert_not_called()

    def test_csrf_and_post_only_boundary(self):
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.owner)
        self.assertEqual(browser.post(self.start_url, {"offer_token": self.token(),
            "accepted_terms": public.TERMS}).status_code, 403)
        self.provider_create.assert_not_called()

    def test_trial_must_expire_naturally_and_is_not_modified_by_creation(self):
        token = self.token()
        with workspace_context(self.workspace.pk):
            subscription = Subscription.objects.create(company=self.workspace, plan=self.plan,
                status="trial", trial_end_date=timezone.now() + timedelta(days=1))
            Subscription.objects.filter(pk=subscription.pk).update(trial_end_date=timezone.now() + timedelta(days=1))
        self.assertEqual(self.submit(token).status_code, 302)
        self.provider_create.assert_not_called()
        self.assertContains(self.client.get(self.url), "Your free trial is still active")
        with workspace_context(self.workspace.pk):
            subscription.trial_end_date = timezone.now() - timedelta(seconds=1)
            subscription.save(update_fields=["trial_end_date"])
        self.assertEqual(self.submit().status_code, 302)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "trial")
        self.assertFalse(Invoice.objects.exists())

    def test_selected_offer_does_not_expose_private_annual_or_one_off_checkout(self):
        page = self.client.get(reverse("workspace_subscriptions:plan-list",
            kwargs={"workspace_slug": self.workspace.slug}))
        self.assertContains(page, "Review monthly subscription")
        self.assertNotContains(page, "/year")
        self.assertNotContains(page, "/checkout/")
        self.provider_create.assert_not_called()

    def test_named_pilot_controls_offer_and_saved_consent_without_exposing_other_plans(self):
        token = self.token()
        plans_url = reverse("workspace_subscriptions:plan-list", kwargs={"workspace_slug": self.workspace.slug})
        with override_settings(BILLING_RECURRING_WORKSPACE_IDS=[str(self.workspace.pk)]):
            self.assertContains(self.client.get(plans_url), "Review monthly subscription")
            self.assertContains(self.client.get(self.url), 'name="offer_token"')
        with override_settings(BILLING_RECURRING_WORKSPACE_IDS=[str(self.workspace.pk + 1)]):
            self.assertNotContains(self.client.get(plans_url), "Review monthly subscription")
            self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
            self.assertEqual(self.submit(token).status_code, 403)
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_public_pricing_opens_only_after_pilot_scope_is_removed(self):
        self.client.logout()
        for scope, available in (([str(self.workspace.pk)], False), ([], True), (["invalid"], False)):
            with override_settings(BILLING_RECURRING_WORKSPACE_IDS=scope):
                for url in ("/", reverse("pricing"), reverse("faq")):
                    page = self.client.get(url)
                    if available:
                        self.assertContains(page, "Paid subscriptions are available")
                        self.assertNotContains(page, "Paid subscriptions are not available yet")
                    else:
                        self.assertContains(page, "Paid subscriptions are not available yet")
        with override_settings(BILLING_RECURRING_ENABLED=False):
            self.assertContains(self.client.get(reverse("pricing")), "Paid subscriptions are not available yet")
        self.provider_create.assert_not_called()

    def test_pilot_gate_also_blocks_operator_creation_and_malformed_scope(self):
        from .recurring import create_agreement
        for scope in (["not-an-id"], ["0"], [True], "2", [str(self.workspace.pk + 1)]):
            with self.subTest(scope=scope), override_settings(BILLING_RECURRING_WORKSPACE_IDS=scope):
                with self.assertRaises(PermissionDenied):
                    create_agreement(workspace_id=self.workspace.pk, actor=self.admin,
                        binding_id=self.binding.pk, request_key=uuid4(), total_count=12)
        self.provider_create.assert_not_called()
        self.assertFalse(RecurringAgreement.objects.exists())

    def test_scope_removal_blocks_new_authorization_but_preserves_status_recovery(self):
        from .recurring_owner import authorization_options, refresh_agreement
        self.submit()
        agreement = RecurringAgreement.objects.get()
        provider = {**agreement.request_snapshot, "id": agreement.provider_subscription_id,
            "entity": "subscription", "status": "created", "has_scheduled_changes": False}
        args = dict(workspace=self.workspace, actor=self.owner, agreement_id=agreement.pk)
        with override_settings(BILLING_RECURRING_WORKSPACE_IDS=[str(self.workspace.pk + 1)]), \
                patch.object(RazorpayService, "get_subscription", return_value=provider) as fetch:
            with self.assertRaises(PermissionDenied):
                authorization_options(**args)
            fetch.assert_not_called()
            self.assertNotContains(self.client.get(self.url), 'id="recurring-authorize"')
            self.assertEqual(refresh_agreement(**args).pk, agreement.pk)
            fetch.assert_called_once()

    def test_trial_offer_visible_now_but_payment_only_after_natural_expiry(self):
        expiry = timezone.now() + timedelta(hours=1)
        with workspace_context(self.workspace.pk):
            subscription = Subscription.objects.create(company=self.workspace, plan=self.plan, status="trial")
            Subscription.objects.filter(pk=subscription.pk).update(trial_end_date=expiry)
        with override_settings(BILLING_RECURRING_WORKSPACE_IDS=[str(self.workspace.pk)]):
            page = self.client.get(self.url)
            self.assertContains(page, "Your trial ends")
            self.assertEqual(page.context["monthly_trial_end"], expiry)
            self.assertNotContains(page, 'name="offer_token"')
            with patch("apps.subscriptions.public_recurring.timezone.now", return_value=expiry + timedelta(seconds=1)):
                token = self.token()
                self.assertEqual(self.submit(token).status_code, 302)
        self.provider_create.assert_called_once()
        subscription.refresh_from_db()
        self.assertEqual(subscription.trial_end_date, expiry)
        self.assertEqual(subscription.status, "trial")
        self.assertFalse(Invoice.objects.exists())

    @override_settings(**MAIL_SETTINGS)
    def test_new_owner_creation_capture_receipt_and_duplicate_dispatch(self):
        self.submit()
        agreement = RecurringAgreement.objects.get()
        self.assert_captured_cycle_and_receipt(agreement)

    def assert_captured_cycle_and_receipt(self, agreement):
        from .recurring_cycles import record_paid_cycle
        start = timezone.now().replace(microsecond=0)
        end = start + timedelta(days=30)
        provider = {**agreement.request_snapshot, "id": agreement.provider_subscription_id,
            "entity": "subscription", "status": "active", "has_scheduled_changes": False}
        invoice = {"id": "inv_public", "entity": "invoice", "subscription_id": provider["id"],
            "order_id": "order_public", "payment_id": "pay_public", "status": "paid", "amount": 149900,
            "amount_paid": 149900, "amount_due": 0, "currency": "INR", "billing_start": int(start.timestamp()),
            "billing_end": int(end.timestamp()), "paid_at": int(start.timestamp()),
            "line_items": [{"type": "plan", "quantity": 1, "amount": 149900, "currency": "INR"}]}
        payment = {"id": "pay_public", "entity": "payment", "invoice_id": "inv_public",
            "order_id": "order_public", "amount": 149900, "currency": "INR", "status": "captured",
            "amount_refunded": 0, "method": "card"}
        with patch.object(RazorpayService, "get_subscription", return_value=provider), \
                patch.object(RazorpayService, "get_invoice", return_value=invoice), \
                patch.object(RazorpayService, "get_payment_status", return_value=payment):
            for _ in range(2):
                cycle = record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id="inv_public")
        self.assertEqual(cycle.access_action, "applied")
        self.assertEqual(Subscription.objects.get().end_date, end)
        receipt = Delivery.objects.get()
        self.assertEqual(receipt.recipient, self.owner.email)
        # Reuse the existing monitored batch command; no new worker framework.
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-fictional-receipt") as send, \
                patch("apps.platform_mail.management.commands.dispatch_platform_mail.time.sleep"):
            for _ in range(2):
                call_command("dispatch_platform_mail", send=True, limit=10, stdout=StringIO())
        send.assert_called_once()
        receipt.refresh_from_db()
        self.assertEqual(receipt.status, "accepted")
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

    def test_global_adapter_works_under_restricted_role_and_clears_workspace_context(self):
        role = connection.ops.quote_name("public_recurring_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {role}")
            token = self.token()
            self.assertEqual(self.submit(token).status_code, 302)
            self.provider_create.assert_called_once()
            self.assertIsNone(current_workspace_id())
            self.assertFalse(connection.in_atomic_block)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def release_unused_attempt(self):
        from .unpaid_agreement import release_unused_agreement
        token = self.token()
        self.submit(token)
        agreement = RecurringAgreement.objects.get()
        provider = {**agreement.request_snapshot, "id": agreement.provider_subscription_id,
            "entity": "subscription", "status": "cancelled", "has_scheduled_changes": False,
            "paid_count": 0, "auth_attempts": 0, "charge_at": None, "start_at": None,
            "current_start": None, "current_end": None}
        with patch.object(RazorpayService, "get_subscription", return_value=provider), \
                patch.object(RazorpayService, "get_subscription_invoices", return_value={
                    "entity": "collection", "count": 0, "items": []}):
            release_unused_agreement(workspace_id=self.workspace.pk, actor=self.owner,
                agreement_id=agreement.pk, reason="Owner reviewing monthly and annual options")
        agreement.refresh_from_db()
        self.provider_create.reset_mock()
        self.provider_create.side_effect = lambda payload: {
            **self.created_entity(payload), "id": "sub_freshMonthly"}
        return agreement, token

    @override_settings(**MAIL_SETTINGS)
    def test_released_unused_attempt_allows_both_choices_and_fresh_monthly_capture(self):
        with workspace_context(self.workspace.pk):
            subscription = Subscription.objects.create(company=self.workspace, plan=self.plan, status="trial")
            Subscription.objects.filter(pk=subscription.pk).update(trial_end_date=timezone.now() - timedelta(days=1))
        old, old_token = self.release_unused_attempt()
        from .access_policy import record_access_decision, workspace_activity
        from .models import WorkspaceAccessDecision
        grant = record_access_decision(workspace=self.workspace, actor=self.admin,
            mode="full", expires_at=timezone.now() + timedelta(days=7), reason="Temporary grace extension")
        grant_before = WorkspaceAccessDecision.objects.values().get(pk=grant.pk)
        before = RecurringAgreement.objects.values().get(pk=old.pk)
        with override_settings(BILLING_PUBLIC_PREPAID_PLAN_ID=self.plan.pk, BILLING_PREPAID_WORKSPACE_IDS=[]):
            page = self.client.get(self.url)
            self.assertContains(page, "Continue with monthly subscription")
            self.assertContains(page, "Review annual prepayment")
            self.assertContains(page, "Previous agreement:")
            self.assertNotContains(page, 'id="recurring-authorize"')
            annual_url = reverse("workspace_subscriptions:annual-prepaid",
                kwargs={"workspace_slug": self.workspace.slug})
            self.assertTrue(self.client.get(annual_url).context["annual_consent"])
            token = page.context["monthly_consent"]
        self.provider_create.assert_not_called()
        # Replaying the original review returns its immutable, closed agreement.
        self.submit(old_token)
        self.provider_create.assert_not_called()
        self.submit(token)
        self.submit(token)
        self.provider_create.assert_called_once()
        fresh = RecurringAgreement.objects.exclude(pk=old.pk).get()
        self.assertIsNone(fresh.closed_at)
        self.assertNotEqual(fresh.provider_subscription_id, old.provider_subscription_id)
        self.assertEqual(RecurringAgreement.objects.values().get(pk=old.pk), before)
        self.assert_captured_cycle_and_receipt(fresh)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "active")
        self.assertEqual(WorkspaceAccessDecision.objects.values().get(pk=grant.pk), grant_before)
        self.assertEqual(workspace_activity(self.workspace, at=grant.expires_at).mode, "full")

    def test_restriction_after_review_blocks_monthly_even_after_later_grant(self):
        from .access_policy import record_access_decision
        token = self.token()
        Subscription.objects.create(company=self.workspace, plan=self.plan, status="trial")
        Subscription.objects.filter(company=self.workspace).update(trial_end_date=timezone.now() - timedelta(days=1))
        record_access_decision(workspace=self.workspace, actor=self.admin,
            mode="read_only", expires_at=timezone.now() + timedelta(days=1), reason="Review required")
        record_access_decision(workspace=self.workspace, actor=self.admin,
            mode="full", expires_at=timezone.now() + timedelta(days=7), reason="Temporary access")
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        self.submit(token)
        self.provider_create.assert_not_called()

    def test_separate_entitlement_grant_still_requires_monthly_review(self):
        from .access_policy import record_access_decision
        token = self.token()
        record_access_decision(workspace=self.workspace, actor=self.admin, mode="full", plan=self.plan,
            expires_at=timezone.now() + timedelta(days=7), reason="Provisioned with separate plan terms")
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        self.submit(token)
        self.provider_create.assert_not_called()

    def test_cancellation_and_other_release_history_do_not_allow_new_monthly_consent(self):
        from .models import RecurringAgreementEvent
        token = self.token()
        self.submit(token)
        old = RecurringAgreement.objects.get()
        # Ordinary cancellation retains the reservation until reviewed.
        RecurringAgreement.objects.filter(pk=old.pk).update(provider_status="cancelled")
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        # A closed or refunded agreement is not proof of a never-used mandate.
        RecurringAgreement.objects.filter(pk=old.pk).update(closed_at=timezone.now())
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        RecurringAgreementEvent.objects.create(agreement=old, actor=self.owner,
            event_type="reservation.released", detail={"reason": "Reviewed refunded fixture"})
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        self.provider_create.reset_mock()
        # Another browser's fresh request key still cannot create a new mandate.
        consent = signing.loads(token, salt=public.SALT)
        changed = signing.dumps({**consent, "request_key": str(uuid4())}, salt=public.SALT)
        self.submit(changed)
        self.provider_create.assert_not_called()
        self.assertEqual(RecurringAgreement.objects.count(), 1)

    def test_annual_reservation_blocks_saved_monthly_choice_after_unused_release(self):
        from . import public_prepaid as prepaid
        self.release_unused_attempt()
        monthly = self.token()
        with override_settings(BILLING_PUBLIC_PREPAID_PLAN_ID=self.plan.pk, BILLING_PREPAID_WORKSPACE_IDS=[]):
            annual_url = reverse("workspace_subscriptions:annual-prepaid",
                kwargs={"workspace_slug": self.workspace.slug})
            annual = prepaid.read_consent(self.client.get(annual_url).context["annual_consent"], self.owner)
            with patch.object(RazorpayService, "create_order", side_effect=BillingProviderError("Mock timeout")) as create:
                with self.assertRaises(BillingProviderError):
                    prepaid.prepare_purchase(workspace_id=self.workspace.pk, actor=self.owner, consent=annual)
                create.assert_called_once()
        self.submit(monthly)
        self.assertNotContains(self.client.get(self.url), 'name="offer_token"')
        self.provider_create.assert_not_called()
        self.assertEqual(RecurringAgreement.objects.count(), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertFalse(Payment.objects.exists())

    def test_new_monthly_reservation_blocks_saved_annual_choice_after_unused_release(self):
        from . import public_prepaid as prepaid
        self.release_unused_attempt()
        with override_settings(BILLING_PUBLIC_PREPAID_PLAN_ID=self.plan.pk, BILLING_PREPAID_WORKSPACE_IDS=[]):
            annual_url = reverse("workspace_subscriptions:annual-prepaid",
                kwargs={"workspace_slug": self.workspace.slug})
            annual = prepaid.read_consent(self.client.get(annual_url).context["annual_consent"], self.owner)
            self.submit()
            with patch.object(RazorpayService, "create_order") as create:
                with self.assertRaises(ValidationError):
                    prepaid.prepare_purchase(workspace_id=self.workspace.pk, actor=self.owner, consent=annual)
                create.assert_not_called()
        self.assertEqual(RecurringAgreement.objects.count(), 2)
        self.assertFalse(Invoice.objects.exists())
