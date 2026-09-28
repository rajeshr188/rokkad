import json
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from botocore.exceptions import ClientError, ReadTimeoutError
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.test import TestCase, SimpleTestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.tenancy.context import workspace_context
from .events import reconcile_sqs_envelope
from .models import Attempt, Delivery, ProviderEvent, Suppression
from .services import dispatch_one, enqueue_invitation, recover_stale_sends, render_delivery, retry_delivery
from .transport import TransportFailure, aws_client, send_ses


MAIL_SETTINGS = dict(
    PLATFORM_EMAIL_ENABLED=True, PLATFORM_EMAIL_BASE_URL="https://rokkad.example",
    PLATFORM_EMAIL_SENDER_DOMAIN="notify.rokkad.com",
    PLATFORM_EMAIL_REPLY_TO="support@rokkad.com", BILLING_EMAIL_REPLY_TO="billing@rokkad.com",
    DEFAULT_FROM_EMAIL="Rokkad <notifications@notify.rokkad.com>",
    BILLING_EMAIL_SENDER="Rokkad Billing <billing@notify.rokkad.com>",
    PLATFORM_SES_REGION="ap-south-1", PLATFORM_SES_ACCOUNT_ID="123456789012",
    PLATFORM_SES_CONFIGURATION_SET="platform-test",
    PLATFORM_SES_TOPIC_ARN="arn:aws:sns:ap-south-1:123456789012:platform-test",
    PLATFORM_SES_EVENTS_QUEUE_URL="https://sqs.ap-south-1.amazonaws.com/123456789012/platform-test",
    PLATFORM_SES_ACCESS_KEY_ID="test-key", PLATFORM_SES_SECRET_ACCESS_KEY="test-secret",
)


@override_settings(**MAIL_SETTINGS,
    STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class DeliveryTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="mail-owner")
        self.other = get_user_model().objects.create_user(username="mail-other")
        self.workspace = Company.all_objects.create(name="Mail <Workspace>", schema_name="mail", owner=self.owner, creator=self.owner)
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(company=self.workspace, user=self.owner, role=owner_role)
        self.invitation = CompanyInvitation.create(email="invitee@example.test", company=self.workspace,
                                                   role=self.member_role, inviter=self.owner)
        self.row = enqueue_invitation(self.invitation)

    def envelope(self, kind="Delivery", attempt=None):
        attempt = attempt or Attempt.objects.create(delivery=self.row)
        event = {"eventType": kind, "mail": {
            "messageId": "ses-message-1", "sendingAccountId": "123456789012",
            "sourceArn": "arn:aws:ses:ap-south-1:123456789012:identity/notify.rokkad.com",
            "destination": [self.row.recipient], "tags": {
                "ses:configuration-set": ["platform-test"], "rokkad_delivery": [str(self.row.pk)],
                "rokkad_attempt": [str(attempt.pk)],
            },
        }}
        if kind == "Bounce":
            event["bounce"] = {"bounceType": "Permanent", "bouncedRecipients": [{"emailAddress": self.row.recipient}]}
        if kind == "Complaint":
            event["complaint"] = {"complainedRecipients": [{"emailAddress": self.row.recipient}]}
        return {"Type": "Notification", "TopicArn": MAIL_SETTINGS["PLATFORM_SES_TOPIC_ARN"],
                "MessageId": str(uuid4()), "Message": json.dumps(event)}

    def test_enqueue_is_idempotent_and_rollback_atomic(self):
        self.assertEqual(enqueue_invitation(self.invitation).pk, self.row.pk)
        self.assertEqual(Delivery.objects.count(), 1)
        with self.assertRaises(RuntimeError), transaction.atomic():
            inv = CompanyInvitation.create(email="rollback@example.test", company=self.workspace,
                                             role=self.member_role, inviter=self.owner)
            inv.send_invitation(None)
            raise RuntimeError("rollback")
        self.assertEqual(CompanyInvitation.objects.count(), 1)
        self.assertEqual(Delivery.objects.count(), 1)


    def test_onboarding_queue_failure_rolls_back_only_that_invitation(self):
        from apps.orgs.services.control_plane import send_onboarding_team_invitations
        def enqueue(invitation):
            if invitation.email == "fail@example.test":
                raise RuntimeError("Queue unavailable for fixture")
            return enqueue_invitation(invitation)
        with patch("apps.platform_mail.services.enqueue_invitation", side_effect=enqueue), \
                patch("apps.orgs.services.control_plane.ensure_workspace_has_member_capacity"):
            result = send_onboarding_team_invitations(email_addresses=["fail@example.test", "ok@example.test"],
                actor=self.owner, company=self.workspace, request=None)
        self.assertEqual((result["invited_count"], result["failed_count"]), (1, 1))
        self.assertFalse(CompanyInvitation.objects.filter(email="fail@example.test").exists())
        self.assertEqual(Delivery.objects.filter(recipient="ok@example.test").count(), 1)

    def test_canonical_link_escaped_content_and_reply_to(self):
        message = render_delivery(self.row)
        self.assertIn("https://rokkad.example" + reverse("team_accept_invitation", kwargs={"key": self.invitation.key}), message["html"])
        self.assertIn("Mail &lt;Workspace&gt;", message["html"])
        self.assertEqual(message["reply_to"], "support@rokkad.com")
        self.assertNotIn(self.invitation.key, self.row.source_fingerprint)
        with override_settings(PLATFORM_EMAIL_REPLY_TO="support@rokkad.com\r\nBcc: leak@example.test"):
            with self.assertRaises(ValidationError):
                render_delivery(self.row)

    def test_capture_and_disabled_send_never_call_provider(self):
        with override_settings(PLATFORM_EMAIL_ENABLED=False), patch("apps.platform_mail.transport.send_ses") as send:
            with self.assertRaises(ValidationError):
                dispatch_one(self.row.pk)
            self.assertEqual(dispatch_one(self.row.pk, capture=True), Delivery.Status.CAPTURED)
        send.assert_not_called()
        self.assertFalse(Attempt.objects.exists())

    def test_duplicate_dispatch_sends_once_and_records_real_id(self):
        with patch("apps.platform_mail.transport.send_ses", return_value="real-provider-id") as send:
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.ACCEPTED)
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.ACCEPTED)
        send.assert_called_once()
        self.assertEqual(Attempt.objects.get().provider_message_id, "real-provider-id")

    def test_uncertain_send_never_automatically_retries(self):
        with patch("apps.platform_mail.transport.send_ses", side_effect=TransportFailure("timeout", outcome=Delivery.Status.UNKNOWN)) as send:
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.UNKNOWN)
            dispatch_one(self.row.pk)
        send.assert_called_once()
        with self.assertRaises(ValidationError):
            retry_delivery(self.row.pk, actor=self.owner)

    def test_throttle_backoff_and_authorized_retry(self):
        with patch("apps.platform_mail.transport.send_ses", side_effect=TransportFailure("ses_throttled", retryable=True)) as send:
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.QUEUED)
            dispatch_one(self.row.pk)
        send.assert_called_once()
        self.row.refresh_from_db()
        self.assertGreater(self.row.available_at, timezone.now())
        Delivery.objects.filter(pk=self.row.pk).update(status=Delivery.Status.FAILED)
        with self.assertRaises((PermissionDenied, ValidationError)):
            retry_delivery(self.row.pk, actor=self.other)
        retry_delivery(self.row.pk, actor=self.owner)

    def test_stale_worker_becomes_uncertain(self):
        Delivery.objects.filter(pk=self.row.pk).update(status=Delivery.Status.SENDING, updated_at=timezone.now()-timedelta(minutes=11))
        Attempt.objects.create(delivery=self.row)
        self.assertEqual(recover_stale_sends(), 1)
        self.assertEqual(Attempt.objects.get().status, Delivery.Status.UNKNOWN)

    def assert_cancelled(self):
        with patch("apps.platform_mail.transport.send_ses") as send:
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.CANCELLED)
        send.assert_not_called()

    def test_expired_invitation_cancels(self):
        Delivery.objects.filter(pk=self.row.pk).update(expires_at=timezone.now()-timedelta(seconds=1))
        self.assert_cancelled()

    def test_revoked_invitation_cancels(self):
        CompanyInvitation.objects.filter(pk=self.invitation.pk).update(status="revoked")
        self.assert_cancelled()

    def test_removed_inviter_cancels(self):
        Membership.objects.filter(user=self.owner, company=self.workspace).delete()
        self.assert_cancelled()

    def test_changed_role_cancels(self):
        from apps.tenancy.testing import workspace_role_permissions
        workspace_role_permissions(self.member_role, self.workspace).clear()
        self.assert_cancelled()

    def test_nested_transaction_cannot_send_uncommitted_data(self):
        with transaction.atomic(), patch("apps.platform_mail.transport.send_ses") as send:
            with self.assertRaises(RuntimeError):
                dispatch_one(self.row.pk)
        send.assert_not_called()

    def test_event_deduplication_and_out_of_order_proof(self):
        envelope = self.envelope()
        self.assertTrue(reconcile_sqs_envelope(envelope))
        self.assertFalse(reconcile_sqs_envelope(envelope))
        reconcile_sqs_envelope(self.envelope("Send", Attempt.objects.get()))
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, Delivery.Status.DELIVERED)
        self.assertEqual(ProviderEvent.objects.count(), 2)

    def test_feedback_before_send_response_preserves_delivery(self):
        def send(*args, **kwargs):
            reconcile_sqs_envelope(self.envelope(attempt=Attempt.objects.get(pk=kwargs["attempt_id"])))
            return "ses-message-1"
        with patch("apps.platform_mail.transport.send_ses", side_effect=send):
            self.assertEqual(dispatch_one(self.row.pk), Delivery.Status.DELIVERED)

    def test_bad_event_boundaries_never_change_state(self):
        envelope = self.envelope()
        mutations = [("sendingAccountId", "000000000000"), ("sourceArn", "arn:evil"),
                     ("destination", ["other@example.test"])]
        for key, value in mutations:
            bad = deepcopy(envelope)
            event = json.loads(bad["Message"])
            event["mail"][key] = value
            bad["Message"] = json.dumps(event)
            with self.subTest(key=key), self.assertRaises(ValidationError):
                reconcile_sqs_envelope(bad)
        for key, value in [("TopicArn", "arn:evil"), ("Type", "SubscriptionConfirmation")]:
            with self.assertRaises(ValidationError):
                reconcile_sqs_envelope({**envelope, key: value})
        self.assertFalse(ProviderEvent.objects.exists())
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, Delivery.Status.QUEUED)

    def test_hard_bounce_and_complaint_suppress_subsequent_mail(self):
        reconcile_sqs_envelope(self.envelope("Bounce"))
        self.assertEqual(Suppression.objects.count(), 1)
        workspace = Company.all_objects.create(name="Another", schema_name="mail-another", owner=self.owner, creator=self.owner)
        Membership.objects.create(company=workspace, user=self.owner, role=Role.objects.get(name="Owner"))
        inv = CompanyInvitation.create(email=self.row.recipient, company=workspace,
                                         role=self.member_role, inviter=self.owner)
        row = enqueue_invitation(inv)
        with patch("apps.platform_mail.transport.send_ses") as send:
            self.assertEqual(dispatch_one(row.pk), Delivery.Status.SUPPRESSED)
        send.assert_not_called()
        reconcile_sqs_envelope(self.envelope("Complaint", Attempt.objects.get()))
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, Delivery.Status.COMPLAINT)

    def test_retry_http_is_scoped_and_post_only(self):
        from apps.tenancy.testing import start_workspace_trial
        start_workspace_trial(self.workspace)
        Delivery.objects.filter(pk=self.row.pk).update(status=Delivery.Status.CAPTURED)
        url = reverse("retry_platform_mail", kwargs={"workspace_id": self.workspace.pk, "delivery_id": self.row.pk})
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.client.force_login(self.other)
        Delivery.objects.filter(pk=self.row.pk).update(status=Delivery.Status.CAPTURED)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.url, reverse("workspace_slug_settings_invitations", kwargs={"workspace_slug": self.workspace.slug}))
        self.row.refresh_from_db()
        self.assertEqual(self.row.status, Delivery.Status.CAPTURED)

    def test_workspace_owner_cannot_retry_another_workspaces_delivery(self):
        from apps.tenancy.testing import start_workspace_trial
        other_workspace = Company.all_objects.create(name="Other", schema_name="mail-other", owner=self.owner, creator=self.owner)
        Membership.objects.create(company=other_workspace, user=self.owner, role=Role.objects.get(name="Owner"))
        start_workspace_trial(other_workspace)
        self.client.force_login(self.owner)
        url = reverse("retry_platform_mail", kwargs={"workspace_id": other_workspace.pk, "delivery_id": self.row.pk})
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_status_is_visible_on_invitation_page(self):
        from apps.tenancy.testing import start_workspace_trial
        start_workspace_trial(self.workspace)
        self.client.force_login(self.owner)
        response = self.client.get(reverse("workspace_slug_settings_invitations", kwargs={"workspace_slug": self.workspace.slug}))
        self.assertContains(response, "Email delivery:")
        self.assertContains(response, "Queued")

    def test_soft_bounce_does_not_globally_suppress(self):
        envelope = self.envelope("Bounce")
        event = json.loads(envelope["Message"])
        event["bounce"]["bounceType"] = "Transient"
        envelope["Message"] = json.dumps(event)
        reconcile_sqs_envelope(envelope)
        self.assertFalse(Suppression.objects.exists())

    def test_malformed_or_uncorrelated_events_rejected(self):
        envelope = self.envelope("Bounce")
        event = json.loads(envelope["Message"])
        for change in ("bad_tags", "unknown_attempt", "wrong_set", "bad_feedback"):
            bad = deepcopy(event)
            if change == "bad_tags":
                bad["mail"]["tags"]["rokkad_attempt"] = [42]
            elif change == "unknown_attempt":
                bad["mail"]["tags"]["rokkad_attempt"] = [str(uuid4())]
            elif change == "wrong_set":
                bad["mail"]["tags"]["ses:configuration-set"] = ["wrong-set"]
            else:
                bad["bounce"] = None
            with self.subTest(change=change), self.assertRaises(ValidationError):
                reconcile_sqs_envelope({**envelope, "Message": json.dumps(bad)})
        self.assertFalse(ProviderEvent.objects.exists())

    def test_feedback_consumer_acknowledges_only_valid_committed_events(self):
        from django.core.management.base import CommandError
        from django.core.management import call_command
        from io import StringIO
        envelope = self.envelope()
        with patch("apps.platform_mail.management.commands.receive_platform_mail_events.aws_client") as client:
            client.return_value.receive_message.return_value = {"Messages": [
                {"Body": json.dumps(envelope), "ReceiptHandle": "valid"},
                {"Body": "{}", "ReceiptHandle": "invalid"},
            ]}
            with self.assertRaises(CommandError):
                call_command("receive_platform_mail_events", stdout=StringIO(), stderr=StringIO())
            client.return_value.delete_message.assert_called_once_with(
                QueueUrl=MAIL_SETTINGS["PLATFORM_SES_EVENTS_QUEUE_URL"], ReceiptHandle="valid")
        self.assertEqual(ProviderEvent.objects.count(), 1)


@override_settings(**MAIL_SETTINGS)
class TransportTests(SimpleTestCase):
    def test_readiness_is_offline_and_never_discloses_keys(self):
        from .readiness import assess_platform_mail
        with patch("boto3.client") as client:
            report = assess_platform_mail()
        client.assert_not_called()
        self.assertTrue(report["configuration_ready"])
        self.assertFalse(report["delivery_verified"])
        self.assertNotIn("test-secret", json.dumps(report))
        with override_settings(PLATFORM_SES_TOPIC_ARN="arn:aws:sns:ap-south-1:000000000000:wrong"):
            self.assertFalse(assess_platform_mail()["configuration_ready"])

    def test_requires_dedicated_credentials(self):
        with override_settings(PLATFORM_SES_ACCESS_KEY_ID="", PLATFORM_SES_SECRET_ACCESS_KEY=""), patch("boto3.client") as client:
            with self.assertRaises(TransportFailure):
                aws_client("sesv2")
        client.assert_not_called()

    def test_sdk_retries_disabled(self):
        with override_settings(PLATFORM_SES_ACCESS_KEY_ID="test-key", PLATFORM_SES_SECRET_ACCESS_KEY="test-secret"), patch("boto3.client") as client:
            aws_client("sesv2")
        self.assertEqual(client.call_args.kwargs["config"].retries, {"total_max_attempts": 1})

    def test_acceptance_and_sanitized_failures(self):
        message = dict(sender="notifications@notify.rokkad.com", reply_to="support@rokkad.com",
                       recipient="recipient@example.test", subject="Test", text="private body", html="private body")
        with patch("apps.platform_mail.transport.aws_client") as client:
            client.return_value.send_email.return_value = {"MessageId": "provider-id"}
            self.assertEqual(send_ses(message, delivery_id=uuid4(), attempt_id=uuid4()), "provider-id")
            kwargs = client.return_value.send_email.call_args.kwargs
            self.assertEqual(kwargs["ConfigurationSetName"], "platform-test")
            for error, outcome, retryable in [
                (ReadTimeoutError(endpoint_url="secret-host"), Delivery.Status.UNKNOWN, False),
                (ClientError({"Error": {"Code": "MessageRejected", "Message": "secret"}}, "SendEmail"), Delivery.Status.FAILED, False),
                (ClientError({"Error": {"Code": "TooManyRequestsException", "Message": "secret"}}, "SendEmail"), Delivery.Status.FAILED, True),
            ]:
                client.return_value.send_email.side_effect = error
                with self.assertRaises(TransportFailure) as caught:
                    send_ses(message, delivery_id=uuid4(), attempt_id=uuid4())
                self.assertEqual(caught.exception.outcome, outcome)
                self.assertEqual(caught.exception.retryable, retryable)
                self.assertNotIn("secret", str(caught.exception))


@override_settings(**MAIL_SETTINGS)
class RestrictedWorkerConcurrencyTests(TransactionTestCase):
    def test_competing_workers_claim_once_under_restricted_database_role(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connection, connections
        owner = get_user_model().objects.create_user(username="concurrent-mail")
        workspace = Company.all_objects.create(name="Concurrent mail", schema_name="concurrent-mail", owner=owner, creator=owner)
        Membership.objects.create(company=workspace, user=owner, role=Role.objects.get_or_create(name="Owner")[0])
        invitation = CompanyInvitation.create(company=workspace, inviter=owner,
            role=Role.objects.get_or_create(name="Member")[0], email="concurrent@example.test")
        row = enqueue_invitation(invitation)
        role = connection.ops.quote_name("mail_test_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        barrier = Barrier(2)
        def run():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {role}")
                barrier.wait(timeout=10)
                return dispatch_one(row.pk)
            finally:
                connections.close_all()
        try:
            with patch("apps.platform_mail.transport.send_ses", return_value="concurrent-provider-id") as send:
                with ThreadPoolExecutor(max_workers=2) as pool:
                    results = list(pool.map(lambda _: run(), range(2)))
                send.assert_called_once()
                self.assertTrue(set(results) <= {Delivery.Status.SENDING, Delivery.Status.ACCEPTED})
            row.refresh_from_db()
            self.assertEqual(row.status, Delivery.Status.ACCEPTED)
            self.assertEqual(Attempt.objects.count(), 1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
