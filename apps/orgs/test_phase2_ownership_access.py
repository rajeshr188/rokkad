from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models.deletion import ProtectedError
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company, Membership, Role
from apps.orgs.services.control_plane import transfer_workspace_ownership


class Phase2OwnershipAccessTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.owner = users.create_user(username="phase2-owner")
        self.member = users.create_user(username="phase2-member")
        self.outsider = users.create_user(username="phase2-outsider")
        self.owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.member_role, _ = Role.objects.get_or_create(name="Member")
        self.admin_role, _ = Role.objects.get_or_create(name="Admin")
        self.workspace = Company.objects.create(
            schema_name="phase2", name="Phase 2", owner=self.owner, creator=self.owner
        )
        Membership.objects.create(
            user=self.owner, company=self.workspace, role=self.owner_role
        )
        Membership.objects.create(
            user=self.member, company=self.workspace, role=self.member_role
        )

    def test_workspace_access_is_request_independent_and_fail_closed(self):
        member_access = resolve_workspace_access(actor=self.member, workspace=self.workspace)
        outsider_access = resolve_workspace_access(actor=self.outsider, workspace=self.workspace)
        self.assertTrue(member_access.can("workspace.view"))
        self.assertFalse(outsider_access.can("workspace.view"))
        with self.assertRaises(PermissionDenied):
            outsider_access.require("workspace.view")

    def test_transfer_updates_owner_and_both_mirrored_roles_atomically(self):
        transfer_workspace_ownership(
            workspace=self.workspace,
            new_owner=self.member,
            actor=self.owner,
            previous_owner_role=self.admin_role,
            reason="Succession",
        )
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.owner, self.member)
        self.assertEqual(
            Membership.objects.get(user=self.member, company=self.workspace).role,
            self.owner_role,
        )
        self.assertEqual(
            Membership.objects.get(user=self.owner, company=self.workspace).role,
            self.admin_role,
        )

    def test_transfer_rejects_non_member_without_partial_change(self):
        with self.assertRaises(ValidationError):
            transfer_workspace_ownership(
                workspace=self.workspace,
                new_owner=self.outsider,
                actor=self.owner,
                previous_owner_role=self.admin_role,
                reason="Invalid target",
            )
        self.workspace.refresh_from_db()
        self.assertEqual(self.workspace.owner, self.owner)

    def test_owner_user_deletion_is_protected(self):
        with self.assertRaises(ProtectedError):
            self.owner.delete()

    def test_stale_previous_owner_cannot_transfer_after_ownership_changes(self):
        transfer_workspace_ownership(
            workspace=self.workspace,
            new_owner=self.member,
            actor=self.owner,
            previous_owner_role=self.admin_role,
            reason="First transfer",
        )
        with self.assertRaises(PermissionDenied):
            transfer_workspace_ownership(
                workspace=self.workspace,
                new_owner=self.owner,
                actor=self.owner,
                previous_owner_role=self.member_role,
                reason="Stale competing transfer",
            )


class Phase2OwnershipConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def test_competing_transfers_serialize_and_only_one_commits(self):
        users = get_user_model().objects
        owner = users.create_user(username="phase2-race-owner")
        candidates = [
            users.create_user(username=f"phase2-race-{index}") for index in range(2)
        ]
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        member_role, _ = Role.objects.get_or_create(name="Member")
        admin_role, _ = Role.objects.get_or_create(name="Admin")
        workspace = Company.objects.create(
            schema_name="phase2_race",
            name="Phase 2 Race",
            owner=owner,
            creator=owner,
        )
        Membership.objects.create(user=owner, company=workspace, role=owner_role)
        for candidate in candidates:
            Membership.objects.create(
                user=candidate, company=workspace, role=member_role
            )

        barrier = Barrier(2)

        def attempt(candidate_id):
            close_old_connections()
            barrier.wait()
            try:
                transfer_workspace_ownership(
                    workspace=Company.objects.get(pk=workspace.pk),
                    new_owner=get_user_model().objects.get(pk=candidate_id),
                    actor=get_user_model().objects.get(pk=owner.pk),
                    previous_owner_role=Role.objects.get(pk=admin_role.pk),
                    reason="Concurrent transfer test",
                )
                return "committed"
            except PermissionDenied:
                return "denied"
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(attempt, [user.pk for user in candidates]))

        self.assertCountEqual(outcomes, ["committed", "denied"])
        workspace.refresh_from_db()
        self.assertIn(workspace.owner_id, [user.pk for user in candidates])
        self.assertEqual(
            Membership.objects.filter(company=workspace, role=owner_role).count(), 1
        )
