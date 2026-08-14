from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.loans.services.risk_whatsapp_pilot import assess_risk_whatsapp_pilot


class RiskWhatsAppPilotTests(SimpleTestCase):
    def _query(self, values):
        query = MagicMock()
        query.select_related.return_value.order_by.return_value = tuple(values)
        return query

    def test_delivered_receipt_produces_accepted_pilot(self):
        now = timezone.now()
        notice = SimpleNamespace(pk=1, notification_job_id=2, created_at=now, loan_id=3)
        job = SimpleNamespace(pk=2, status="SENT", sent_at=now, failure_reason="")
        receipt = SimpleNamespace(job_id=2, external_status="delivered", received_at=now, duplicate_count=0)
        jobs = MagicMock()
        jobs.select_related.return_value = (job,)
        receipts = MagicMock()
        receipts.order_by.return_value = (receipt,)
        unknown = MagicMock()
        unknown.order_by.return_value.__getitem__.return_value = ()
        with patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.current_tenant_workspace_id", return_value=5
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.PawnLoanNotice.objects.filter",
            return_value=self._query([notice]),
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.NotificationJob.objects.filter",
            return_value=jobs,
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.WhatsAppCloudWebhookReceipt.objects.filter",
            side_effect=[receipts, unknown],
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.assess_whatsapp_cloud_readiness",
            return_value=SimpleNamespace(ready=True, blockers=()),
        ):
            report = assess_risk_whatsapp_pilot()
        self.assertTrue(report.accepted)
        self.assertEqual(report.delivered_count, 1)
        self.assertEqual(report.unresolved_count, 0)

    def test_sent_without_callback_is_visible_as_unresolved(self):
        now = timezone.now() - timedelta(minutes=5)
        notice = SimpleNamespace(pk=1, notification_job_id=2, created_at=now, loan_id=3)
        job = SimpleNamespace(pk=2, status="SENT", sent_at=now, failure_reason="")
        jobs = MagicMock()
        jobs.select_related.return_value = (job,)
        receipts = MagicMock()
        receipts.order_by.return_value = ()
        unknown = MagicMock()
        unknown.order_by.return_value.__getitem__.return_value = ()
        with patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.current_tenant_workspace_id", return_value=5
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.PawnLoanNotice.objects.filter",
            return_value=self._query([notice]),
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.NotificationJob.objects.filter",
            return_value=jobs,
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.WhatsAppCloudWebhookReceipt.objects.filter",
            side_effect=[receipts, unknown],
        ), patch(
            "apps.tenant_apps.loans.services.risk_whatsapp_pilot.assess_whatsapp_cloud_readiness",
            return_value=SimpleNamespace(ready=True, blockers=()),
        ):
            report = assess_risk_whatsapp_pilot()
        self.assertFalse(report.accepted)
        self.assertEqual(report.unresolved_count, 1)
