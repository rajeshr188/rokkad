from io import StringIO
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.risk_borrower_notices import _fingerprint
from apps.tenant_apps.loans.services.risk_email_pilot import (
    RiskEmailPilotReport,
    assess_risk_email_pilot,
)


class RiskEmailPilotTests(SimpleTestCase):
    def test_preview_fingerprint_is_deterministic_and_content_sensitive(self):
        readiness = SimpleNamespace(alert=SimpleNamespace(pk=3, source_event_id=4))
        channel = SimpleNamespace(template=SimpleNamespace(pk=5, version=2), recipient="a@example.com")
        payload = {"loan": "PL-1", "total": "100.00"}
        first = _fingerprint(readiness, channel, payload, "Subject", "Body")
        self.assertEqual(first, _fingerprint(readiness, channel, payload, "Subject", "Body"))
        self.assertNotEqual(first, _fingerprint(readiness, channel, payload, "Subject", "Changed"))

    def test_reconciliation_detects_artifact_that_differs_from_preview(self):
        notice = SimpleNamespace(
            pk=7,
            payload_snapshot={"communication_evidence": {
                "consent": {"id": 8},
                "preview": {"subject": "Confirmed", "body": "Exact body"},
            }},
        )
        row = SimpleNamespace(
            notice=notice,
            status="SENT",
            artifact=SimpleNamespace(rendered_text="Subject: Different\n\nExact body"),
        )
        queryset = MagicMock()
        queryset.select_related.return_value.order_by.return_value = (notice,)
        with patch(
            "apps.tenant_apps.loans.services.risk_email_pilot.current_tenant_workspace_id",
            return_value=10,
        ), patch(
            "apps.tenant_apps.loans.services.risk_email_pilot.PawnLoanNotice.objects.filter",
            return_value=queryset,
        ), patch(
            "apps.tenant_apps.loans.services.risk_email_pilot.build_pawn_loan_notice_rows",
            return_value=(row,),
        ), patch(
            "apps.tenant_apps.loans.services.risk_email_pilot.get_email_provider_readiness",
            return_value=SimpleNamespace(ready=True),
        ):
            report = assess_risk_email_pilot()
        self.assertFalse(report.ready)
        self.assertIn("differs", report.evidence_issues[0])

    def test_command_can_fail_closed_for_automation(self):
        report = RiskEmailPilotReport(
            provider=SimpleNamespace(ready=False, backend="console", sender="x", message="blocked"),
            notice_count=0,
            sent_count=0,
            failed_count=0,
            pending_count=0,
            evidence_issues=(),
        )
        with patch(
            "apps.tenant_apps.loans.management.commands.check_pawn_risk_email_pilot.assess_risk_email_pilot",
            return_value=report,
        ), self.assertRaises(CommandError):
            call_command("check_pawn_risk_email_pilot", "--fail-on-blocker", stdout=StringIO())
