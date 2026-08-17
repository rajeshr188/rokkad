import json
import hashlib
import hmac
from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings

from django_project.navigation import get_navigation_for_user

from apps.tenant_apps.notify_v2.models import (
    NotificationBatch,
    NotificationEvent,
    NotificationEventType,
    NotificationJob,
    NotificationRecipient,
    NotificationTemplate,
    WhatsAppCloudWebhookReceipt,
)
from apps.tenant_apps.notify_v2.services.delivery_service import dispatch_batch_jobs, process_whatsapp_cloud_webhook
from apps.tenant_apps.notify_v2.services.event_service import emit_event
from apps.tenant_apps.notify_v2.services.whatsapp_readiness import assess_whatsapp_cloud_readiness
from apps.tenant_apps.notify_v2.views import (
    batch_detail,
    batch_download_artifacts,
    batch_list,
    batch_mark_posted,
    batch_mark_printed,
    batch_send_digital,
    settings_overview,
    whatsapp_cloud_webhook,
)


class NotifyV2FoundationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model()(username="notifyv2")
        self.event_type = NotificationEventType(
            key="loan.first_reminder_due",
            name="Loan First Reminder Due",
            domain=NotificationEventType.Domain.LOAN,
        )

    @patch("apps.tenant_apps.notify_v2.services.event_service.NotificationEvent.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.event_service.NotificationEventType.objects.get")
    def test_emit_event_creates_event_for_batch(
        self,
        mock_get_event_type,
        mock_create_event,
    ):
        recipient = NotificationRecipient(
            name_snapshot="Asha",
            email="asha@example.com",
        )
        batch = NotificationBatch(
            name="April Reminder Batch",
            event_type=self.event_type,
            created_by=self.user,
            selection_snapshot=["GL-001", "GL-002"],
        )
        mock_get_event_type.return_value = self.event_type
        mock_create_event.return_value = NotificationEvent(
            event_type=self.event_type,
            recipient=recipient,
            batch=batch,
            payload={"loan": {"loan_id": "GL-001"}},
            source_app="girvi",
            source_model="GivenLoan",
            source_pk="1",
        )

        event = emit_event(
            event_key="loan.first_reminder_due",
            recipient=recipient,
            payload={"loan": {"loan_id": "GL-001"}},
            batch=batch,
            source_app="girvi",
            source_model="GivenLoan",
            source_pk="1",
        )

        self.assertEqual(event.event_type, self.event_type)
        self.assertEqual(event.batch, batch)
        self.assertEqual(event.payload["loan"]["loan_id"], "GL-001")
        mock_get_event_type.assert_called_once_with(
            key="loan.first_reminder_due",
            is_active=True,
        )

    def test_batch_and_job_status_helpers(self):
        recipient = NotificationRecipient(name_snapshot="Bina")
        template = NotificationTemplate(
            event_type=self.event_type,
            channel=NotificationTemplate.Channel.LETTER,
            renderer_type=NotificationTemplate.RendererType.PDF,
            name="Default Letter",
            version=1,
        )
        batch = NotificationBatch(
            name="Final Notice Batch",
            event_type=self.event_type,
            created_by=self.user,
        )
        event = NotificationEvent(
            event_type=self.event_type,
            recipient=recipient,
            batch=batch,
            payload={"loan": {"loan_id": "GL-009"}},
        )
        job = NotificationJob(
            event=event,
            batch=batch,
            channel=NotificationJob.Channel.LETTER,
            template=template,
        )

        batch.mark_rendered(save=False)
        batch.mark_printed(save=False)
        batch.mark_posted(save=False)
        log_entry = job.mark_rendered(message="PDF generated", save=False)

        self.assertEqual(batch.status, NotificationBatch.Status.POSTED)
        self.assertIsNotNone(batch.printed_at)
        self.assertIsNotNone(batch.posted_at)
        self.assertEqual(job.status, NotificationJob.Status.RENDERED)
        self.assertEqual(log_entry.status_after, NotificationJob.Status.RENDERED)
        self.assertEqual(log_entry.message, "PDF generated")

    def test_get_navigation_for_user_includes_notify_v2_for_data_users(self):
        navigation = get_navigation_for_user(self.user, permissions={"data_view"})

        self.assertIn("data", navigation)
        self.assertTrue(
            any(
                item.get("url_name") == "notify_v2_batch_list"
                for item in navigation["data"]
                if not item.get("is_header")
            )
        )

    @patch("apps.tenant_apps.notify_v2.services.delivery_service.send_mail")
    def test_dispatch_batch_jobs_sends_email_and_flags_missing_phone(self, mock_send_mail):
        email_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Asha", email="asha@example.com"),
            payload={"customer": {"name": "Asha"}, "loan_count": 1},
        )
        sms_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Bina", phone=""),
            payload={"customer": {"name": "Bina"}, "loan_count": 1},
        )
        email_job = NotificationJob(
            event=email_event,
            channel=NotificationJob.Channel.EMAIL,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.EMAIL,
                renderer_type=NotificationTemplate.RendererType.DJANGO,
                name="Email Template",
                subject_template="Reminder for {{ customer.name }}",
                body_template="Hello {{ customer.name }}",
                version=1,
            ),
        )
        sms_job = NotificationJob(
            event=sms_event,
            channel=NotificationJob.Channel.SMS,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.SMS,
                renderer_type=NotificationTemplate.RendererType.TEXT,
                name="SMS Template",
                body_template="Hi {{ customer.name }}",
                version=1,
            ),
        )
        email_job.mark_sent = MagicMock()
        sms_job.mark_failed = MagicMock()
        batch = SimpleNamespace(
            pk=15,
            jobs=SimpleNamespace(select_related=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[email_job, sms_job])))),
            mark_posted=MagicMock(),
        )

        result = dispatch_batch_jobs(batch)

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.failed_count, 1)
        mock_send_mail.assert_called_once()
        email_job.mark_sent.assert_called_once()
        sms_job.mark_failed.assert_called_once()

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="123456789",
        WHATSAPP_CLOUD_ACCESS_TOKEN="test-token",
    )
    @patch("apps.tenant_apps.notify_v2.services.delivery_service._whatsapp_cloud_settings")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.requests.post")
    def test_dispatch_batch_jobs_uses_whatsapp_cloud_when_configured(self, mock_post, mock_cloud_settings):
        mock_cloud_settings.return_value = {"api_version": "v20.0", "phone_number_id": "123456789", "access_token": "test-token"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid-123"}]}
        mock_post.return_value = mock_response

        wa_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Cloud User", phone="+918888888888"),
            payload={"customer": {"name": "Cloud User"}, "loan_count": 1},
        )
        wa_job = NotificationJob(
            event=wa_event,
            channel=NotificationJob.Channel.WHATSAPP,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.WHATSAPP,
                renderer_type=NotificationTemplate.RendererType.TEXT,
                name="WhatsApp Template",
                body_template="Hi {{ customer.name }}",
                layout_key="approved_notice_v1",
                version=1,
            ),
        )
        wa_job.mark_sent = MagicMock()
        wa_job.mark_failed = MagicMock()
        batch = SimpleNamespace(
            pk=19,
            jobs=SimpleNamespace(select_related=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[wa_job])))),
            mark_posted=MagicMock(),
        )

        result = dispatch_batch_jobs(batch)

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.failed_count, 0)
        self.assertEqual(wa_job.provider_message_id, "wamid-123")
        wa_job.mark_sent.assert_called_once()
        wa_job.mark_failed.assert_not_called()
        mock_post.assert_called_once()
        self.assertIn("graph.facebook.com", mock_post.call_args.args[0])

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="123456789",
        WHATSAPP_CLOUD_ACCESS_TOKEN="test-token",
    )
    @patch("apps.tenant_apps.notify_v2.services.delivery_service._whatsapp_cloud_settings")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.requests.post")
    def test_dispatch_batch_jobs_uses_whatsapp_cloud_template_payload_when_layout_key_present(self, mock_post, mock_cloud_settings):
        mock_cloud_settings.return_value = {"api_version": "v20.0", "phone_number_id": "123456789", "access_token": "test-token"}
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"messages": [{"id": "wamid-template-123"}]}
        mock_post.return_value = mock_response

        wa_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Cloud User", phone="+918888888888"),
            payload={"customer": {"name": "Cloud User"}, "loan_count": 2},
        )
        wa_job = NotificationJob(
            event=wa_event,
            channel=NotificationJob.Channel.WHATSAPP,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.WHATSAPP,
                renderer_type=NotificationTemplate.RendererType.TEXT,
                name="WhatsApp Template",
                body_template="Hi {{ customer.name }}",
                layout_key="loan_reminder_v1",
                sample_payload={
                    "whatsapp_template": {
                        "components": [
                            {
                                "type": "body",
                                "parameters": [
                                    {"type": "text", "text": "{{ customer.name }}"},
                                    {"type": "text", "text": "{{ loan_count }}"},
                                ],
                            }
                        ]
                    }
                },
                version=1,
            ),
        )
        wa_job.mark_sent = MagicMock()
        wa_job.mark_failed = MagicMock()
        batch = SimpleNamespace(
            pk=20,
            jobs=SimpleNamespace(select_related=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[wa_job])))),
            mark_posted=MagicMock(),
        )

        result = dispatch_batch_jobs(batch)

        self.assertEqual(result.sent_count, 1)
        self.assertEqual(result.failed_count, 0)
        request_payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(request_payload["type"], "template")
        self.assertEqual(request_payload["template"]["name"], "loan_reminder_v1")
        self.assertEqual(
            request_payload["template"]["components"][0]["parameters"][0]["text"],
            "Cloud User",
        )
        self.assertEqual(
            request_payload["template"]["components"][0]["parameters"][1]["text"],
            "2",
        )

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="",
        WHATSAPP_CLOUD_ACCESS_TOKEN="",
    )
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.requests.post")
    def test_dispatch_batch_jobs_fails_whatsapp_cloud_without_config_when_fallback_disabled(self, mock_post):
        wa_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Asha", phone="+919999999999"),
            payload={"customer": {"name": "Asha"}, "loan_count": 1},
        )
        wa_job = NotificationJob(
            event=wa_event,
            channel=NotificationJob.Channel.WHATSAPP,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.WHATSAPP,
                renderer_type=NotificationTemplate.RendererType.TEXT,
                name="WhatsApp Template",
                body_template="Hi {{ customer.name }}",
                version=1,
            ),
        )
        wa_job.mark_sent = MagicMock()
        wa_job.mark_failed = MagicMock()
        batch = SimpleNamespace(
            pk=20,
            jobs=SimpleNamespace(select_related=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[wa_job])))),
            mark_posted=MagicMock(),
        )

        result = dispatch_batch_jobs(batch)

        self.assertEqual(result.sent_count, 0)
        self.assertEqual(result.failed_count, 1)
        wa_job.mark_failed.assert_called_once()
        wa_job.mark_sent.assert_not_called()
        mock_post.assert_not_called()

    def test_dispatch_batch_jobs_fails_sms_without_a_selected_provider(self):
        sms_event = NotificationEvent(
            event_type=self.event_type,
            recipient=NotificationRecipient(name_snapshot="Asha", phone="+919999999999"),
            payload={"customer": {"name": "Asha"}, "loan_count": 1},
        )
        sms_job = NotificationJob(
            event=sms_event,
            channel=NotificationJob.Channel.SMS,
            template=NotificationTemplate(
                event_type=self.event_type,
                channel=NotificationTemplate.Channel.SMS,
                renderer_type=NotificationTemplate.RendererType.TEXT,
                name="SMS Template",
                body_template="Hi {{ customer.name }}",
                version=1,
            ),
        )
        sms_job.mark_sent = MagicMock()
        sms_job.mark_failed = MagicMock()
        batch = SimpleNamespace(
            pk=21,
            jobs=SimpleNamespace(select_related=MagicMock(return_value=SimpleNamespace(all=MagicMock(return_value=[sms_job])))),
            mark_posted=MagicMock(),
        )

        result = dispatch_batch_jobs(batch)

        self.assertEqual(result.sent_count, 0)
        self.assertEqual(result.failed_count, 1)
        sms_job.mark_failed.assert_called_once()
        sms_job.mark_sent.assert_not_called()

class NotifyV2WebhookTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.event_type = NotificationEventType(
            key="loan.whatsapp_status",
            name="Loan WhatsApp Status",
            domain=NotificationEventType.Domain.LOAN,
        )
        self.recipient = NotificationRecipient(
            name_snapshot="Webhook User",
            phone="+919999999999",
        )

    @patch("apps.tenant_apps.notify_v2.views.get_whatsapp_cloud_credentials")
    def test_whatsapp_cloud_webhook_verification_returns_challenge(self, mock_credentials):
        mock_credentials.return_value = SimpleNamespace(webhook_verify_token="verify-me")
        request = self.factory.get(
            "/notify-v2/webhooks/whatsapp/cloud/",
            {
                "hub.mode": "subscribe",
                "hub.verify_token": "verify-me",
                "hub.challenge": "challenge-123",
            },
        )

        request.workspace = SimpleNamespace(pk=1)
        response = whatsapp_cloud_webhook(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"challenge-123")

    @override_settings(
        WHATSAPP_CLOUD_APP_SECRET="app-secret",
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="phone-123",
    )
    @patch("apps.tenant_apps.notify_v2.views.process_whatsapp_cloud_webhook")
    @patch("apps.tenant_apps.notify_v2.views.get_whatsapp_cloud_credentials")
    def test_whatsapp_cloud_webhook_authenticates_and_routes_status_payload(self, mock_credentials, mock_process):
        mock_credentials.return_value = SimpleNamespace(app_secret="app-secret", phone_number_id="phone-123")
        mock_process.return_value = {"received_statuses": 1, "matched_jobs": 1}
        payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "metadata": {"phone_number_id": "phone-123"},
                                "statuses": [
                                    {
                                        "id": "wamid-delivered",
                                        "status": "delivered",
                                        "recipient_id": "919999999999",
                                    },
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        body = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(b"app-secret", body, hashlib.sha256).hexdigest()
        request = self.factory.generic(
            "POST",
            "/notify-v2/webhooks/whatsapp/cloud/",
            data=body,
            content_type="application/json",
            HTTP_X_HUB_SIGNATURE_256=signature,
        )

        request.workspace = SimpleNamespace(pk=1)
        response = whatsapp_cloud_webhook(request)
        response_payload = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response_payload["ok"])
        self.assertEqual(response_payload["matched_jobs"], 1)
        mock_process.assert_called_once_with(
            payload,
            phone_number_id="phone-123",
            signature_digest=signature.removeprefix("sha256="),
        )

    @override_settings(
        WHATSAPP_CLOUD_APP_SECRET="app-secret",
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="phone-123",
    )
    @patch("apps.tenant_apps.notify_v2.views.get_whatsapp_cloud_credentials")
    def test_whatsapp_cloud_webhook_rejects_unsigned_post(self, mock_credentials):
        mock_credentials.return_value = SimpleNamespace(app_secret="app-secret", phone_number_id="phone-123")
        request = self.factory.post(
            "/notify-v2/webhooks/whatsapp/cloud/",
            data="{}",
            content_type="application/json",
        )
        request.workspace = SimpleNamespace(pk=1)
        response = whatsapp_cloud_webhook(request)
        self.assertEqual(response.status_code, 403)


class NotifyV2WebhookProcessingTests(TestCase):
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.NotificationAttemptLog.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.NotificationJob.objects.select_for_update")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.WhatsAppCloudWebhookReceipt.objects.get_or_create")
    def test_authenticated_status_is_persisted_and_applied_once(self, mock_receipt_create, mock_job_lock, mock_log):
        receipt = MagicMock(pk=12)
        mock_receipt_create.return_value = (receipt, True)
        job = NotificationJob(channel="WHATSAPP", status="SENT", provider_message_id="wamid-1")
        job.pk = 9
        job.save = MagicMock()
        mock_job_lock.return_value.filter.return_value.first.return_value = job
        payload = {
            "entry": [{"changes": [{"value": {"statuses": [{
                "id": "wamid-1", "status": "delivered", "timestamp": "123"
            }]}}]}]
        }
        with patch(
            "apps.tenant_apps.notify_v2.services.delivery_service.current_workspace_id",
            return_value=1,
        ):
            summary = process_whatsapp_cloud_webhook(
                payload, phone_number_id="phone-1", signature_digest="a" * 64
            )
        self.assertEqual(summary["matched_jobs"], 1)
        self.assertEqual(summary["duplicate_statuses"], 0)
        receipt.save.assert_called_once()
        mock_log.assert_called_once()

    @patch("apps.tenant_apps.notify_v2.services.delivery_service.NotificationJob.objects.select_for_update")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.WhatsAppCloudWebhookReceipt.objects.filter")
    @patch("apps.tenant_apps.notify_v2.services.delivery_service.WhatsAppCloudWebhookReceipt.objects.get_or_create")
    def test_replayed_status_increments_receipt_without_reapplying_job(self, mock_receipt_create, mock_receipt_filter, mock_job_lock):
        mock_receipt_create.return_value = (MagicMock(pk=12), False)
        payload = {"entry": [{"changes": [{"value": {"statuses": [{
            "id": "wamid-1", "status": "delivered", "timestamp": "123"
        }]}}]}]}
        with patch(
            "apps.tenant_apps.notify_v2.services.delivery_service.current_workspace_id",
            return_value=1,
        ):
            summary = process_whatsapp_cloud_webhook(
                payload, phone_number_id="phone-1", signature_digest="a" * 64
            )
        self.assertEqual(summary["duplicate_statuses"], 1)
        mock_receipt_filter.return_value.update.assert_called_once()
        mock_job_lock.assert_not_called()


class WhatsAppCloudReadinessTests(SimpleTestCase):
    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="phone",
        WHATSAPP_CLOUD_ACCESS_TOKEN="token",
        WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN="verify",
        WHATSAPP_CLOUD_APP_SECRET="secret",
    )
    def test_ready_when_configuration_and_reconciliation_are_clean(self):
        receipts = MagicMock()
        receipts.filter.return_value.count.return_value = 0
        receipts.count.return_value = 3
        with patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.current_workspace_id",
            return_value=1,
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.get_whatsapp_cloud_integration",
            return_value=SimpleNamespace(is_enabled=True),
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.get_whatsapp_cloud_credentials",
            return_value=SimpleNamespace(phone_number_id="phone", access_token="token", webhook_verify_token="verify", app_secret="secret"),
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.WhatsAppCloudWebhookReceipt.objects.all",
            return_value=receipts,
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.NotificationJob.objects.filter"
        ) as jobs:
            jobs.return_value.count.return_value = 0
            report = assess_whatsapp_cloud_readiness()
        self.assertTrue(report.ready)
        self.assertEqual(report.receipt_count, 3)

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="",
        WHATSAPP_CLOUD_ACCESS_TOKEN="",
        WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN="",
        WHATSAPP_CLOUD_APP_SECRET="",
    )
    def test_missing_configuration_and_unknown_receipts_block(self):
        receipts = MagicMock()
        receipts.filter.return_value.count.return_value = 2
        receipts.count.return_value = 2
        with patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.current_workspace_id",
            return_value=1,
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.get_whatsapp_cloud_integration",
            return_value=None,
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.WhatsAppCloudWebhookReceipt.objects.all",
            return_value=receipts,
        ), patch(
            "apps.tenant_apps.notify_v2.services.whatsapp_readiness.NotificationJob.objects.filter"
        ) as jobs:
            jobs.return_value.count.return_value = 1
            report = assess_whatsapp_cloud_readiness()
        self.assertFalse(report.ready)
        self.assertEqual(report.unknown_receipt_count, 2)
        self.assertEqual(report.unreconciled_job_count, 1)


class NotifyV2BatchWorkflowTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = get_user_model()(username="notifyv2-db")
        access_patcher = patch(
            "apps.tenant_apps.notify_v2.access.assert_notify_v2_action_permission",
            side_effect=self._authorize_request,
        )
        access_patcher.start()
        self.addCleanup(access_patcher.stop)

    @staticmethod
    def _authorize_request(request, _action):
        request.notify_v2_workspace_access = SimpleNamespace(can=lambda _code: True)
        return request.workspace

    @patch(
        "apps.tenant_apps.notify_v2.services.batch_service.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.notify_v2.services.batch_service.emit_event")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.NotificationJob.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.NotificationRecipient.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.NotificationBatch.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.ensure_girvi_batch_defaults")
    def _retired_create_girvi_reminder_batch_creates_grouped_events_and_jobs(
        self,
        mock_ensure_defaults,
        mock_batch_create,
        mock_recipient_create,
        mock_job_create,
        mock_emit_event,
        _mock_atomic,
    ):
        loans = [
            self._build_loan(pk=1, loan_id="GL-001", borrower_name="Asha", amount="1000.00"),
            self._build_loan(pk=2, loan_id="GL-002", borrower_name="Asha", amount="500.00"),
            self._build_loan(pk=3, loan_id="GL-003", borrower_name="Bina", amount="800.00"),
        ]
        event_type = NotificationEventType(
            key="loan.first_reminder_due",
            name="Loan First Reminder Due",
            domain=NotificationEventType.Domain.LOAN,
        )
        template = NotificationTemplate(
            event_type=event_type,
            channel=NotificationTemplate.Channel.LETTER,
            renderer_type=NotificationTemplate.RendererType.PDF,
            name="Default Letter",
            version=1,
        )
        mock_ensure_defaults.return_value = (event_type, MagicMock(), template)
        batch = NotificationBatch(name="April Reminder Batch", event_type=event_type, created_by=self.user)
        batch.save = MagicMock()
        mock_batch_create.return_value = batch
        mock_recipient_create.side_effect = [
            NotificationRecipient(name_snapshot="Asha"),
            NotificationRecipient(name_snapshot="Bina"),
        ]
        mock_emit_event.side_effect = [MagicMock(payload={"loan_count": 2}), MagicMock(payload={"loan_count": 1})]
        mock_job_create.side_effect = [
            NotificationJob(channel=NotificationJob.Channel.LETTER, template=template),
            NotificationJob(channel=NotificationJob.Channel.LETTER, template=template),
        ]

        result = create_girvi_reminder_batch(
            loans=loans,
            created_by=self.user,
            batch_name="April Reminder Batch",
        )

        self.assertEqual(result.preview.loan_count, 3)
        self.assertEqual(result.preview.borrower_count, 2)
        self.assertEqual(result.batch.job_count, 2)
        self.assertEqual(len(result.recipients), 2)
        self.assertEqual(len(result.events), 2)
        self.assertEqual(len(result.jobs), 2)
        mock_recipient_create.assert_called()
        self.assertEqual(mock_job_create.call_count, 2)
        self.assertEqual(
            mock_batch_create.call_args.kwargs["selection_snapshot"][0]["loan_id"],
            "GL-001",
        )

    @patch(
        "apps.tenant_apps.notify_v2.services.batch_service.transaction.atomic",
        side_effect=lambda: nullcontext(),
    )
    @patch("apps.tenant_apps.notify_v2.services.batch_service.NotificationArtifact.objects.create")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.NotificationTemplate.objects.filter")
    @patch("apps.tenant_apps.notify_v2.services.batch_service.render_girvi_notice_bundle", return_value=b"%PDF-1.4 batch")
    def _retired_render_batch_pdf_marks_batch_and_jobs_rendered(
        self,
        mock_render_bundle,
        mock_template_filter,
        mock_artifact_create,
        _mock_atomic,
    ):
        loans = [
            self._build_loan(pk=1, loan_id="GL-011", borrower_name="Asha", amount="1200.00"),
            self._build_loan(pk=2, loan_id="GL-012", borrower_name="Bina", amount="900.00"),
        ]
        template = NotificationTemplate(
            event_type=NotificationEventType(
                key="loan.first_reminder_due",
                name="Loan First Reminder Due",
                domain=NotificationEventType.Domain.LOAN,
            ),
            channel=NotificationTemplate.Channel.LETTER,
            renderer_type=NotificationTemplate.RendererType.PDF,
            name="Default Letter",
            version=1,
            layout_key="loan.first_reminder_due",
        )
        mock_template_filter.return_value.order_by.return_value.first.return_value = template
        jobs = [
            SimpleNamespace(mark_rendered=MagicMock()),
            SimpleNamespace(mark_rendered=MagicMock()),
        ]
        batch = SimpleNamespace(
            pk=1,
            event_type=SimpleNamespace(key="loan.first_reminder_due"),
            jobs=SimpleNamespace(filter=MagicMock(return_value=jobs)),
            mark_rendered=MagicMock(),
        )

        artifact_one = SimpleNamespace(file=SimpleNamespace(save=MagicMock()))
        artifact_two = SimpleNamespace(file=SimpleNamespace(save=MagicMock()))
        mock_artifact_create.side_effect = [artifact_one, artifact_two]

        pdf = render_batch_pdf(batch, loans=loans)

        self.assertEqual(pdf, b"%PDF-1.4 batch")
        batch.mark_rendered.assert_called_once_with()
        self.assertEqual(mock_artifact_create.call_count, 2)
        self.assertTrue(all(job.mark_rendered.called for job in jobs))
        artifact_one.file.save.assert_called_once()
        artifact_two.file.save.assert_called_once()
        mock_render_bundle.assert_called_once()

    @patch("apps.tenant_apps.notify_v2.views.render")
    @patch("apps.tenant_apps.notify_v2.views.NotificationBatch.objects.select_related")
    @patch("apps.tenant_apps.notify_v2.views._notify_settings_summary", return_value={})
    @patch("apps.tenant_apps.notify_v2.access.assert_notify_v2_action_permission")
    def test_batch_list_is_domain_neutral(
        self, _access, _settings, mock_select_related, mock_render
    ):
        mock_select_related.return_value.prefetch_related.return_value = []
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/notify-v2/batches/")
        request.user = self.user
        request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        response = batch_list(request)

        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args.args[2]
        self.assertNotIn("entrypoint_url_name", context)
        self.assertNotIn("legacy_url_name", context)

    @patch("apps.tenant_apps.notify_v2.views.render")
    @patch("apps.tenant_apps.notify_v2.views.get_object_or_404")
    def test_batch_detail_includes_artifacts_for_downloads(self, mock_get_object_or_404, mock_render):
        artifact = SimpleNamespace(
            pk=21,
            artifact_type="PDF",
            file=SimpleNamespace(url="/media/notify_v2/artifacts/test.pdf", name="notify_v2/artifacts/test.pdf"),
            metadata={"loan_count": 1},
            created="2026-04-09",
            job=SimpleNamespace(event=SimpleNamespace(recipient=SimpleNamespace(name_snapshot="Asha"))),
        )
        job = SimpleNamespace(
            event=SimpleNamespace(recipient_id=101, recipient=SimpleNamespace(name_snapshot="Asha")),
            template="Default Letter",
            status="RENDERED",
            get_status_display=lambda: "Rendered",
            channel=NotificationJob.Channel.LETTER,
            get_channel_display=lambda: "Letter",
            attempt_count=1,
            artifacts=SimpleNamespace(all=MagicMock(return_value=[artifact])),
        )
        jobs_manager = MagicMock()
        jobs_manager.select_related.return_value.all.return_value = [job]
        batch = SimpleNamespace(
            pk=7,
            name="April Reminder Batch",
            event_type=SimpleNamespace(name="Loan First Reminder Due", key="loan.first_reminder_due"),
            created_by=self.user,
            created=None,
            printed_at=None,
            posted_at=None,
            selection_snapshot=[{"loan_id": "GL-001", "borrower_name": "Asha"}],
            job_count=1,
            jobs=jobs_manager,
        )
        mock_get_object_or_404.return_value = batch
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/notify-v2/batches/7/")
        request.user = self.user
        request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        response = batch_detail(request, pk=7)

        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args.args[2]
        self.assertIn("artifacts", context)
        self.assertEqual(len(context["artifacts"]), 1)
        self.assertEqual(context["artifacts"][0].file.url, "/media/notify_v2/artifacts/test.pdf")

    @patch("apps.tenant_apps.notify_v2.views.dispatch_batch_jobs")
    @patch("apps.tenant_apps.notify_v2.views.get_object_or_404")
    def test_batch_send_digital_redirects_after_dispatch(self, mock_get_object_or_404, mock_dispatch_batch_jobs):
        batch = SimpleNamespace(pk=7)
        mock_get_object_or_404.return_value = batch
        mock_dispatch_batch_jobs.return_value = SimpleNamespace(sent_count=2, failed_count=0, skipped_count=0)

        request = self.factory.post("/notify-v2/batches/7/send/")
        request.user = self.user
        request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        response = batch_send_digital(request, pk=7)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/notify-v2/batches/7/")
        mock_dispatch_batch_jobs.assert_called_once_with(batch)

    @patch("apps.tenant_apps.notify_v2.views.get_object_or_404")
    def test_batch_download_artifacts_returns_zip_file(self, mock_get_object_or_404):
        file_mock = MagicMock()
        file_mock.name = "notify_v2/artifacts/asha.pdf"
        file_mock.read.return_value = b"%PDF-1.4 sample"
        artifact = SimpleNamespace(
            pk=21,
            artifact_type="PDF",
            file=file_mock,
            job=SimpleNamespace(event=SimpleNamespace(recipient=SimpleNamespace(name_snapshot="Asha"))),
        )
        job = SimpleNamespace(
            artifacts=SimpleNamespace(all=MagicMock(return_value=[artifact])),
            event=SimpleNamespace(recipient_id=101, recipient=SimpleNamespace(name_snapshot="Asha")),
        )
        jobs_manager = MagicMock()
        jobs_manager.select_related.return_value.all.return_value = [job]
        batch = SimpleNamespace(pk=7, name="April Reminder Batch", jobs=jobs_manager)
        mock_get_object_or_404.return_value = batch

        request = self.factory.get("/notify-v2/batches/7/artifacts.zip")
        request.user = self.user
        request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        response = batch_download_artifacts(request, pk=7)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")
        self.assertIn("notify_v2_batch_7_artifacts.zip", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"PK"))

    @patch("apps.tenant_apps.notify_v2.views.get_object_or_404")
    def test_batch_mark_actions_redirect_to_detail(self, mock_get_object_or_404):
        batch = SimpleNamespace(
            pk=7,
            mark_printed=MagicMock(),
            mark_posted=MagicMock(),
        )
        mock_get_object_or_404.return_value = batch

        print_request = self.factory.post("/notify-v2/batches/7/mark-printed/")
        print_request.user = self.user
        print_request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)
        posted_request = self.factory.post("/notify-v2/batches/7/mark-posted/")
        posted_request.user = self.user
        posted_request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        print_response = batch_mark_printed(print_request, pk=7)
        posted_response = batch_mark_posted(posted_request, pk=7)

        self.assertIsInstance(print_response, HttpResponseRedirect)
        self.assertIsInstance(posted_response, HttpResponseRedirect)
        batch.mark_printed.assert_called_once_with()
        batch.mark_posted.assert_called_once_with()


    @patch("apps.tenant_apps.notify_v2.views.render")
    @patch("apps.tenant_apps.notify_v2.views.assess_whatsapp_cloud_readiness")
    @patch("apps.tenant_apps.notify_v2.views._notify_settings_summary")
    @patch("apps.tenant_apps.notify_v2.views.NotificationRecipient.objects.filter")
    @patch("apps.tenant_apps.notify_v2.views.NotificationTemplate.objects.filter")
    @patch("apps.tenant_apps.notify_v2.views.NotificationPolicy.objects.filter")
    @patch("apps.tenant_apps.notify_v2.views.NotificationEventType.objects.filter")
    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="123",
        WHATSAPP_CLOUD_ACCESS_TOKEN="token",
        WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN="verify",
    )
    def test_settings_overview_exposes_counts_and_config(
        self,
        mock_event_type_filter,
        mock_policy_filter,
        mock_template_filter,
        mock_recipient_filter,
        mock_settings_summary,
        mock_readiness,
        mock_render,
    ):
        mock_event_type_filter.return_value.count.return_value = 4
        mock_policy_filter.return_value.count.return_value = 3
        mock_template_filter.return_value.count.return_value = 7
        mock_recipient_filter.return_value.count.return_value = 12
        mock_settings_summary.return_value = {
            "whatsapp_provider": "cloud",
            "has_whatsapp_cloud_phone_id": True,
        }
        mock_readiness.return_value = SimpleNamespace(ready=True, blockers=())
        mock_render.return_value = HttpResponse("ok")

        request = self.factory.get("/notify-v2/settings/")
        request.user = self.user
        request.workspace = SimpleNamespace(pk=1, owner=self.user, owner_id=None)

        response = settings_overview(request)

        self.assertEqual(response.status_code, 200)
        context = mock_render.call_args.args[2]
        self.assertEqual(context["counts"]["event_types"], 4)
        self.assertEqual(context["counts"]["policies"], 3)
        self.assertEqual(context["counts"]["templates"], 7)
        self.assertEqual(context["counts"]["recipients"], 12)
        self.assertEqual(context["notify_settings"]["whatsapp_provider"], "cloud")
        self.assertTrue(context["notify_settings"]["has_whatsapp_cloud_phone_id"])
