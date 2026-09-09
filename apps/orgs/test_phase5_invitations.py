from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.orgs.services.control_plane import accept_invitation
from apps.subscriptions.models import Plan, Subscription
from apps.subscriptions.services import ensure_entitlements_for_subscription
from apps.subscriptions import entitlements


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class CanonicalInvitationAcceptanceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_user(username="phase5-owner")
        self.invitee = user_model.objects.create_user(
            username="phase5-invitee",
            email="invitee@example.com",
        )
        EmailAddress.objects.create(
            user=self.invitee,
            email=self.invitee.email,
            verified=True,
            primary=True,
        )
        self.owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.member_role, _ = Role.objects.get_or_create(name="Member")
        self.workspace = Company.all_objects.create(
            name="Phase 5 Workspace",
            schema_name="phase-5-workspace",
            owner=self.owner,
            creator=self.owner,
        )
        Membership.objects.create(
            user=self.owner,
            company=self.workspace,
            role=self.owner_role,
        )
        self.invitation = CompanyInvitation.create(
            email=self.invitee.email,
            company=self.workspace,
            role=self.member_role,
            inviter=self.owner,
        )

    def test_changed_grants_or_removed_inviter_block_acceptance(self):
        from apps.tenancy.testing import workspace_role_permissions
        workspace_role_permissions(self.member_role, self.workspace).clear()
        with self.assertRaisesMessage(ValidationError, "Role permissions changed"):
            accept_invitation(invitation=self.invitation, user=self.invitee, request=None)
        Membership.objects.filter(user=self.owner, company=self.workspace).delete()
        with self.assertRaises(ValidationError):
            accept_invitation(invitation=self.invitation, user=self.invitee, request=None)
        self.assertFalse(Membership.objects.filter(user=self.invitee, company=self.workspace).exists())

    def test_used_invitation_cannot_restore_removed_member(self):
        membership = accept_invitation(invitation=self.invitation, user=self.invitee, request=None)
        membership.delete()
        with self.assertRaisesMessage(ValidationError, "already used"):
            accept_invitation(invitation=self.invitation, user=self.invitee, request=None)

    def test_acceptance_creates_membership_and_terminal_invitation_state(self):
        membership = accept_invitation(
            invitation=self.invitation,
            user=self.invitee,
            request=None,
        )

        self.invitation.refresh_from_db()
        self.assertEqual(membership.role, self.member_role)
        self.assertEqual(self.invitation.status, CompanyInvitation.Status.ACCEPTED)
        self.assertTrue(self.invitation.accepted)
        self.assertIsNotNone(self.invitation.responded_at)

    def test_retry_is_idempotent(self):
        first = accept_invitation(
            invitation=self.invitation,
            user=self.invitee,
            request=None,
        )
        second = accept_invitation(
            invitation=self.invitation,
            user=self.invitee,
            request=None,
        )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            Membership.objects.filter(
                user=self.invitee,
                company=self.workspace,
            ).count(),
            1,
        )

    def test_unverified_invited_email_is_rejected_without_mutation(self):
        EmailAddress.objects.filter(user=self.invitee).update(verified=False)

        with self.assertRaisesMessage(ValidationError, "Verify the invited email"):
            accept_invitation(
                invitation=self.invitation,
                user=self.invitee,
                request=None,
            )

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, CompanyInvitation.Status.PENDING)
        self.assertFalse(Membership.objects.filter(user=self.invitee).exists())

    def test_expired_invitation_is_rejected_without_membership(self):
        self.invitation.sent = timezone.now() - timedelta(days=30)
        self.invitation.save(update_fields=["sent"])

        with self.assertRaisesMessage(ValidationError, "expired"):
            accept_invitation(
                invitation=self.invitation,
                user=self.invitee,
                request=None,
            )

        self.assertFalse(Membership.objects.filter(user=self.invitee).exists())

    def test_non_active_workspace_is_rejected(self):
        self.workspace.lifecycle_state = Company.LifecycleState.SUSPENDED
        self.workspace.save(update_fields=["lifecycle_state"])

        with self.assertRaisesMessage(ValidationError, "not accepting invitations"):
            accept_invitation(
                invitation=self.invitation,
                user=self.invitee,
                request=None,
            )

        self.assertFalse(Membership.objects.filter(user=self.invitee).exists())

    def test_seat_limit_failure_leaves_invitation_pending(self):
        plan = Plan.objects.create(
            name="One Seat",
            tier=Plan.PlanTierChoices.STARTER,
            price=Decimal("100.00"),
            description="One-seat acceptance test",
            max_users=1,
        )
        subscription = Subscription.objects.create(
            company=self.workspace,
            plan=plan,
            end_date=timezone.now() + timedelta(days=30),
        )
        ensure_entitlements_for_subscription(subscription)
        self.assertEqual(
            entitlements.limit(self.workspace, "workspace.max_members"),
            1,
        )

        with patch(
            "apps.orgs.services.control_plane.ensure_workspace_has_member_capacity",
            side_effect=ValidationError("Workspace seat limit reached (1/1)."),
        ):
            with self.assertRaisesMessage(
                ValidationError, "Workspace seat limit reached"
            ):
                accept_invitation(
                    invitation=self.invitation,
                    user=self.invitee,
                    request=None,
                )

        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, CompanyInvitation.Status.PENDING)
        self.assertFalse(Membership.objects.filter(user=self.invitee).exists())

    def test_direct_invitation_get_is_confirmation_only_and_post_accepts(self):
        self.client.force_login(self.invitee)
        url = f"/orgs/team/invitations/accept/{self.invitation.key}/"

        confirmation = self.client.get(url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "Accept invitation")
        self.assertFalse(Membership.objects.filter(user=self.invitee).exists())

        accepted = self.client.post(url)
        self.assertEqual(accepted.status_code, 302)
        self.assertTrue(Membership.objects.filter(user=self.invitee).exists())

    def test_anonymous_invitation_link_preserves_key_through_login(self):
        url = f"/orgs/team/invitations/accept/{self.invitation.key}/"

        response = self.client.get(url)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
        self.assertIn("next=", response.url)
        self.assertIn(self.invitation.key, response.url)
