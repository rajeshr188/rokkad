"""Identity policy tests; locked acceptance is covered by test_phase5_invitations."""

from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.orgs.services import control_plane


class InvitationVerifiedEmailTests(SimpleTestCase):
    def setUp(self):
        self.invitation = SimpleNamespace(email="invitee@example.com")
        self.user = SimpleNamespace(id=7, email="INVITEE@example.com")

    def test_matching_verified_email_is_allowed(self):
        with patch.object(control_plane.EmailAddress.objects, "filter") as query:
            query.return_value.exists.return_value = True
            control_plane.assert_verified_invitation_identity(
                invitation=self.invitation, user=self.user
            )

        query.assert_called_once_with(
            user=self.user, email__iexact=self.invitation.email, verified=True
        )

    def test_matching_unverified_email_is_rejected(self):
        with patch.object(control_plane.EmailAddress.objects, "filter") as query:
            query.return_value.exists.return_value = False
            with self.assertRaisesMessage(ValidationError, "Verify the invited email"):
                control_plane.assert_verified_invitation_identity(
                    invitation=self.invitation, user=self.user
                )

    def test_verified_different_email_is_rejected(self):
        self.user.email = "other@example.com"
        with patch.object(control_plane.EmailAddress.objects, "filter") as query:
            with self.assertRaisesMessage(ValidationError, "different email address"):
                control_plane.assert_verified_invitation_identity(
                    invitation=self.invitation, user=self.user
                )

        query.assert_not_called()
