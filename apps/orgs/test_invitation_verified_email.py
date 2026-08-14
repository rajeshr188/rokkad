import contextlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.orgs.services import control_plane


class InvitationVerifiedEmailTests(SimpleTestCase):
    def _invitation(self, email="invitee@example.com"):
        return SimpleNamespace(
            email=email,
            company=SimpleNamespace(id=9, name="Acme"),
            role=SimpleNamespace(name="Member"),
            accept=MagicMock(),
        )

    def _user(self, email="invitee@example.com"):
        return SimpleNamespace(id=7, email=email, is_authenticated=True)

    def test_matching_verified_email_can_accept(self):
        invitation = self._invitation()
        user = self._user(email="INVITEE@example.com")
        verified_query = SimpleNamespace(exists=lambda: True)
        membership_query = SimpleNamespace(exists=lambda: True)

        with patch(
            "apps.orgs.services.control_plane._public_schema_context",
            return_value=contextlib.nullcontext(),
        ), patch.object(
            control_plane.EmailAddress.objects,
            "filter",
            return_value=verified_query,
        ) as email_filter, patch.object(
            control_plane.Membership.objects,
            "filter",
            return_value=membership_query,
        ), patch(
            "apps.orgs.services.control_plane.AuditLog.log"
        ):
            control_plane.accept_invitation(
                invitation=invitation,
                user=user,
                request=SimpleNamespace(),
            )

        email_filter.assert_called_once_with(
            user=user,
            email__iexact=invitation.email,
            verified=True,
        )
        invitation.accept.assert_called_once()

    def test_matching_unverified_email_cannot_accept(self):
        invitation = self._invitation()
        user = self._user()
        unverified_query = SimpleNamespace(exists=lambda: False)

        with patch(
            "apps.orgs.services.control_plane._public_schema_context",
            return_value=contextlib.nullcontext(),
        ), patch.object(
            control_plane.EmailAddress.objects,
            "filter",
            return_value=unverified_query,
        ), patch.object(
            control_plane.Membership.objects,
            "filter",
        ) as membership_filter, patch(
            "apps.orgs.services.control_plane.AuditLog.log"
        ) as audit_log:
            with self.assertRaisesMessage(
                ValidationError,
                "Verify the invited email address before accepting this invitation.",
            ):
                control_plane.accept_invitation(
                    invitation=invitation,
                    user=user,
                    request=SimpleNamespace(),
                )

        membership_filter.assert_not_called()
        invitation.accept.assert_not_called()
        audit_log.assert_not_called()

    def test_verified_different_email_cannot_accept(self):
        invitation = self._invitation(email="invited@example.com")
        user = self._user(email="other@example.com")

        with patch(
            "apps.orgs.services.control_plane._public_schema_context",
            return_value=contextlib.nullcontext(),
        ), patch.object(
            control_plane.EmailAddress.objects,
            "filter",
        ) as email_filter:
            with self.assertRaisesMessage(
                ValidationError,
                "This invitation was sent to a different email address.",
            ):
                control_plane.accept_invitation(
                    invitation=invitation,
                    user=user,
                    request=SimpleNamespace(),
                )

        email_filter.assert_not_called()
        invitation.accept.assert_not_called()
