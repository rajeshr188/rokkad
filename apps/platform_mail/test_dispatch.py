from io import StringIO
from datetime import timedelta
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.orgs.models import CompanyInvitation
from apps.subscriptions import test_checkout as checkout_tests
from . import tests as mail_tests
from .models import Attempt, Delivery
from .services import enqueue_invitation


@override_settings(**mail_tests.MAIL_SETTINGS, BILLING_CHECKOUT_ENABLED=True,
                   BILLING_PROVIDER_MODE="test", RAZORPAY_KEY_SECRET="test-secret",
                   RAZORPAY_WEBHOOK_SECRET="webhook-secret")
class InvitationDispatchTests(TestCase):
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm

    def setUp(self):
        checkout_tests.CheckoutTests.setUp(self)
        self.invoice = self.order()
        self.confirm(self.invoice)
        self.receipt = Delivery.objects.get(invoice=self.invoice)
        from apps.orgs.models import Role
        role, _ = Role.objects.get_or_create(name="Member")
        invitation = CompanyInvitation.create(email="invitee@example.test", company=self.workspace,
                                               role=role, inviter=self.owner)
        self.invitation = enqueue_invitation(invitation)

    def test_invitation_batch_skips_older_receipt_before_limit_and_keeps_normal_evidence(self):
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-invitation") as send, \
                patch("apps.platform_mail.management.commands.dispatch_platform_mail.time.sleep"):
            call_command("dispatch_platform_mail", send=True, invitations_only=True,
                         limit=1, stdout=StringIO())
        self.invitation.refresh_from_db()
        self.receipt.refresh_from_db()
        self.assertEqual(self.invitation.status, "accepted")
        self.assertEqual(self.receipt.status, "queued")
        self.assertEqual(self.receipt.attempt_count, 0)
        self.assertEqual(Attempt.objects.get().delivery_id, self.invitation.pk)
        send.assert_called_once()

    def test_explicit_receipt_is_refused_without_attempt_or_capture(self):
        for action in ("send", "capture"):
            with self.subTest(action=action), patch("apps.platform_mail.transport.send_ses") as send:
                with self.assertRaisesMessage(CommandError, "outside invitation-only scope"):
                    call_command("dispatch_platform_mail", **{action:True}, invitations_only=True,
                                 delivery=str(self.receipt.pk), stdout=StringIO())
                send.assert_not_called()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "queued")
        self.assertFalse(Attempt.objects.exists())

    def test_invitation_scope_cannot_silently_apply_to_global_recovery(self):
        with patch("apps.platform_mail.management.commands.dispatch_platform_mail.recover_stale_sends") as recover:
            with self.assertRaisesMessage(CommandError, "not stale-claim recovery"):
                call_command("dispatch_platform_mail", recover_stale=True, invitations_only=True)
            recover.assert_not_called()


@override_settings(**mail_tests.MAIL_SETTINGS, BILLING_CHECKOUT_ENABLED=True,
                   BILLING_PROVIDER_MODE="live", RAZORPAY_KEY_ID="rzp_live_mockfixture",
                   RAZORPAY_KEY_SECRET="test-secret", RAZORPAY_WEBHOOK_SECRET="webhook-secret",
                   BILLING_TAX_RATE="0", BILLING_SELLER_NAME="Fictional Seller",
                   BILLING_SELLER_ADDRESS="1 Example Street", BILLING_SELLER_TAX_STATUS="unregistered")
class ReceiptDispatchTests(TestCase):
    setUp = InvitationDispatchTests.setUp
    order = checkout_tests.CheckoutTests.order
    payment = checkout_tests.CheckoutTests.payment
    confirm = checkout_tests.CheckoutTests.confirm

    def test_receipt_batch_skips_older_invitation_before_limit_and_replay_does_not_send(self):
        Delivery.objects.filter(pk=self.invitation.pk).update(created_at=timezone.now()-timedelta(days=1))
        with patch("apps.platform_mail.transport.send_ses", return_value="ses-receipt") as send, \
                patch("apps.platform_mail.management.commands.dispatch_platform_mail.time.sleep"):
            for _ in range(2):
                call_command("dispatch_platform_mail", send=True, receipts_only=True,
                             limit=1, stdout=StringIO())
        self.receipt.refresh_from_db()
        self.invitation.refresh_from_db()
        self.assertEqual(self.receipt.status, "accepted")
        self.assertEqual(self.invitation.status, "queued")
        self.assertEqual(self.invitation.attempt_count, 0)
        self.assertEqual(Attempt.objects.get().delivery_id, self.receipt.pk)
        send.assert_called_once()

    def test_explicit_invitation_is_refused_without_attempt_or_capture(self):
        for action in ("send", "capture"):
            with self.subTest(action=action), patch("apps.platform_mail.transport.send_ses") as send:
                with self.assertRaisesMessage(CommandError, "outside receipt-only scope"):
                    call_command("dispatch_platform_mail", **{action: True}, receipts_only=True,
                                 delivery=str(self.invitation.pk), stdout=StringIO())
                send.assert_not_called()
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "queued")
        self.assertFalse(Attempt.objects.exists())

    def test_explicit_receipt_capture_never_sends_or_touches_invitation(self):
        with patch("apps.platform_mail.transport.send_ses") as send:
            call_command("dispatch_platform_mail", capture=True, receipts_only=True,
                         delivery=str(self.receipt.pk), limit=1, stdout=StringIO())
        self.receipt.refresh_from_db()
        self.invitation.refresh_from_db()
        self.assertEqual(self.receipt.status, "captured")
        self.assertEqual(self.invitation.status, "queued")
        self.assertFalse(Attempt.objects.exists())
        send.assert_not_called()

    def test_receipt_scope_preserves_disabled_sending_and_mode_guards(self):
        for overrides, message in (({"PLATFORM_EMAIL_ENABLED": False}, "disabled"),
                                   ({"BILLING_PROVIDER_MODE": "test"}, "controlled delivery rehearsal")):
            with self.subTest(overrides=overrides), override_settings(**overrides), \
                    patch("apps.platform_mail.transport.send_ses") as send:
                with self.assertRaisesMessage(CommandError, message):
                    call_command("dispatch_platform_mail", send=True, receipts_only=True,
                                 delivery=str(self.receipt.pk), stdout=StringIO())
                send.assert_not_called()
        self.receipt.refresh_from_db()
        self.assertEqual(self.receipt.status, "queued")
        self.assertEqual(self.receipt.attempt_count, 0)
        self.assertFalse(Attempt.objects.exists())

    def test_receipt_scope_cannot_silently_apply_to_global_recovery(self):
        with patch("apps.platform_mail.management.commands.dispatch_platform_mail.recover_stale_sends") as recover:
            with self.assertRaisesMessage(CommandError, "not stale-claim recovery"):
                call_command("dispatch_platform_mail", recover_stale=True, receipts_only=True)
            recover.assert_not_called()

    def test_conflicting_scopes_are_rejected_before_dispatch(self):
        with patch("apps.platform_mail.management.commands.dispatch_platform_mail.dispatch_one") as dispatch:
            with self.assertRaises(CommandError):
                call_command("dispatch_platform_mail", send=True, receipts_only=True, invitations_only=True)
            dispatch.assert_not_called()
