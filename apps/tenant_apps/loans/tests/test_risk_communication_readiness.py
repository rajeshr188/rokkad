from datetime import time, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanRiskAlert, LoanRiskSnapshot, PawnLoanCommunicationConsent
from apps.tenant_apps.loans.services.risk_communication_readiness import (
    _provider_ready,
    _in_quiet_hours,
    assess_risk_alert_communication_readiness,
    get_email_provider_readiness,
)
from apps.tenant_apps.loans.web.communication_policy_actions import PawnLoanCommunicationPolicyForm


class RiskCommunicationReadinessTests(SimpleTestCase):
    def test_policy_form_rejects_partial_or_zero_length_quiet_hours(self):
        values = {"preferred_channel": "EMAIL", "cooldown_days": 7, "escalation_dpd": 30}
        partial = PawnLoanCommunicationPolicyForm({**values, "quiet_hours_start": "20:00"})
        same = PawnLoanCommunicationPolicyForm({
            **values, "quiet_hours_start": "20:00", "quiet_hours_end": "20:00"
        })
        self.assertFalse(partial.is_valid())
        self.assertFalse(same.is_valid())

    def test_quiet_hours_support_daytime_and_overnight_windows(self):
        daytime = SimpleNamespace(quiet_hours_start=time(9), quiet_hours_end=time(17))
        overnight = SimpleNamespace(quiet_hours_start=time(21), quiet_hours_end=time(7))
        self.assertTrue(_in_quiet_hours(daytime, time(12)))
        self.assertFalse(_in_quiet_hours(daytime, time(18)))
        self.assertTrue(_in_quiet_hours(overnight, time(23)))
        self.assertTrue(_in_quiet_hours(overnight, time(6)))
        self.assertFalse(_in_quiet_hours(overnight, time(12)))
    def test_consent_defaults_fail_closed_and_opt_out_wins(self):
        consent = PawnLoanCommunicationConsent(service_notices_allowed=False)
        self.assertFalse(consent.permits_service_notice)
        consent.service_notices_allowed = True
        self.assertTrue(consent.permits_service_notice)
        consent.opted_out_at = object()
        self.assertFalse(consent.permits_service_notice)

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="notices@example.com",
        DEBUG=False,
    )
    def test_provider_readiness_rejects_stub_but_accepts_real_email_backend(self):
        self.assertTrue(_provider_ready("EMAIL"))
        readiness = get_email_provider_readiness()
        self.assertTrue(readiness.ready)
        self.assertEqual(readiness.sender, "notices@example.com")
        self.assertFalse(_provider_ready("SMS"))
        self.assertFalse(_provider_ready("WHATSAPP"))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.console.EmailBackend",
        DEFAULT_FROM_EMAIL="notices@example.com",
    )
    def test_email_provider_readiness_labels_simulated_backends_as_blocked(self):
        readiness = get_email_provider_readiness()
        self.assertFalse(readiness.ready)
        self.assertIn("development/test", readiness.message)

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="phone-id",
        WHATSAPP_CLOUD_ACCESS_TOKEN="token",
        WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN="verify",
        WHATSAPP_CLOUD_APP_SECRET="secret",
    )
    @patch("apps.tenant_apps.loans.services.risk_communication_readiness.get_whatsapp_cloud_credentials")
    @patch("apps.tenant_apps.loans.services.risk_communication_readiness.current_tenant_workspace_id", return_value=5)
    def test_whatsapp_provider_requires_all_cloud_and_callback_settings(self, _workspace, credentials):
        credentials.return_value = SimpleNamespace(
            phone_number_id="phone-id", access_token="token",
            webhook_verify_token="verify", app_secret="secret",
        )
        self.assertTrue(_provider_ready("WHATSAPP"))
        self.assertFalse(_provider_ready("SMS"))

    @override_settings(
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="phone-id",
        WHATSAPP_CLOUD_ACCESS_TOKEN="token",
        WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN="verify",
        WHATSAPP_CLOUD_APP_SECRET="",
    )
    @patch("apps.tenant_apps.loans.services.risk_communication_readiness.get_whatsapp_cloud_credentials")
    @patch("apps.tenant_apps.loans.services.risk_communication_readiness.current_tenant_workspace_id", return_value=5)
    def test_whatsapp_provider_fails_closed_without_app_secret(self, _workspace, credentials):
        credentials.return_value = SimpleNamespace(
            phone_number_id="phone-id", access_token="token",
            webhook_verify_token="verify", app_secret="",
        )
        self.assertFalse(_provider_ready("WHATSAPP"))

    @override_settings(
        EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
        DEFAULT_FROM_EMAIL="notices@example.com",
        WHATSAPP_CLOUD_PHONE_NUMBER_ID="",
        WHATSAPP_CLOUD_ACCESS_TOKEN="",
    )
    def test_open_current_dpd_alert_exposes_only_complete_channels(self):
        snapshot = SimpleNamespace(
            status=LoanRiskSnapshot.Status.CURRENT,
            as_of_date=timezone.localdate(), source_provenance={"calculation_contract": "LOAN_RISK_SNAPSHOT_V2"},
            days_past_due=31,
            flags=["PAYMENT_OVERDUE"],
        )
        borrower = SimpleNamespace(
            pk=7,
            primary_email="borrower@example.com",
            primary_phone="+919999999999",
        )
        loan = SimpleNamespace(pk=9, borrower=borrower, borrower_id=7, state="ACTIVE", risk_snapshot=snapshot)
        event = SimpleNamespace(pk=11)
        alert = SimpleNamespace(
            pk=12,
            workspace_id=5,
            loan=loan,
            loan_id=9,
            source_event=event,
            source_event_id=11,
            status=LoanRiskAlert.Status.OPEN,
            alert_kind=LoanRiskAlert.Kind.DPD_WORSENING,
        )
        template = SimpleNamespace(pk=20, version=3, locale="en")
        alert_query = MagicMock()
        alert_query.get.return_value = alert
        consent_query = MagicMock()
        consent_query.first.return_value = SimpleNamespace(permits_service_notice=True)
        template_query = MagicMock()
        template_query.order_by.return_value.first.return_value = template
        notice_query = MagicMock()
        notice_query.exists.return_value = False
        policy_query = MagicMock()
        policy_query.first.return_value = None

        with patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.current_tenant_workspace_id",
            return_value=5,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.LoanRiskAlert.objects.select_related",
            return_value=alert_query,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.PawnLoanCommunicationConsent.objects.filter",
            return_value=consent_query,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.NotificationTemplate.objects.filter",
            return_value=template_query,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.PawnLoanNotice.objects.filter",
            return_value=notice_query,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.PawnLoanCommunicationPolicy.objects.filter",
            return_value=policy_query,
        ):
            result = assess_risk_alert_communication_readiness(alert.pk)
            snapshot.as_of_date -= timedelta(days=1)
            stale = assess_risk_alert_communication_readiness(alert.pk)
            self.assertFalse(stale.eligible)
            self.assertIn("RISK_NOT_CURRENT", {row.code for row in stale.blockers})

        self.assertTrue(result.eligible)
        by_channel = {row.channel: row for row in result.channels}
        self.assertTrue(by_channel["EMAIL"].eligible)
        self.assertFalse(by_channel["SMS"].eligible)
        self.assertIn("PROVIDER_NOT_READY", {row.code for row in by_channel["SMS"].blockers})

    def test_ltv_alert_has_no_approved_borrower_notice_mapping(self):
        alert = SimpleNamespace(
            pk=12,
            workspace_id=5,
            status=LoanRiskAlert.Status.OPEN,
            alert_kind=LoanRiskAlert.Kind.LTV_BREACH,
            loan=SimpleNamespace(state="ACTIVE", risk_snapshot=SimpleNamespace(status="CURRENT", flags=["LTV_BREACH"])),
        )
        alert_query = MagicMock()
        alert_query.get.return_value = alert
        policy_query = MagicMock()
        policy_query.first.return_value = None
        with patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.current_tenant_workspace_id",
            return_value=5,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.LoanRiskAlert.objects.select_related",
            return_value=alert_query,
        ), patch(
            "apps.tenant_apps.loans.services.risk_communication_readiness.PawnLoanCommunicationPolicy.objects.filter",
            return_value=policy_query,
        ):
            result = assess_risk_alert_communication_readiness(alert.pk)
        self.assertFalse(result.eligible)
        self.assertIn("NOTICE_KIND_UNAPPROVED", {row.code for row in result.blockers})
