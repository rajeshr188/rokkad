from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.models import PawnLoanCommunicationConsent
from apps.tenant_apps.loans.services.communication_consents import (
    CommunicationConsentError,
    set_pawn_loan_communication_consent,
)


class CommunicationConsentServiceTests(SimpleTestCase):
    def test_missing_evidence_fails_before_write(self):
        with patch(
            "apps.tenant_apps.loans.services.communication_consents.current_tenant_workspace_id",
            return_value=5,
        ), self.assertRaisesMessage(CommunicationConsentError, "evidence"):
            set_pawn_loan_communication_consent.__wrapped__(
                7, channel="EMAIL", decision="ALLOW", evidence=""
            )

    def test_allow_and_opt_out_map_to_explicit_persistence(self):
        party = MagicMock(pk=7)
        party_query = MagicMock()
        party_query.get.return_value = party
        manager = MagicMock()
        manager.update_or_create.return_value = (MagicMock(), True)
        with patch(
            "apps.tenant_apps.loans.services.communication_consents.current_tenant_workspace_id",
            return_value=5,
        ), patch(
            "apps.tenant_apps.loans.services.communication_consents.Party.objects.select_for_update",
            return_value=party_query,
        ), patch.object(PawnLoanCommunicationConsent, "objects", manager):
            set_pawn_loan_communication_consent.__wrapped__(
                7, channel="EMAIL", decision="ALLOW",
                evidence="Signed service notice consent", actor="owner",
            )
            allowed = manager.update_or_create.call_args.kwargs["defaults"]
            set_pawn_loan_communication_consent.__wrapped__(
                7, channel="EMAIL", decision="OPT_OUT",
                evidence="Borrower requested stop", actor="owner",
            )
            opted_out = manager.update_or_create.call_args.kwargs["defaults"]

        self.assertTrue(allowed["service_notices_allowed"])
        self.assertIsNone(allowed["opted_out_at"])
        self.assertFalse(opted_out["service_notices_allowed"])
        self.assertIsNotNone(opted_out["opted_out_at"])
