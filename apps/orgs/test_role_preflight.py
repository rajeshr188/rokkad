import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company, CompanyInvitation, Membership, Role
from apps.orgs.services.role_preflight import build_role_preflight


class RolePreflightTests(TransactionTestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="preflight-owner")
        self.member = get_user_model().objects.create_user(username="preflight-member")
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.role = Role.objects.create(name="Custom review")
        self.unused = Role.objects.create(name="Unused review")
        self.workspaces = []
        for index in range(2):
            workspace = Company.objects.create(schema_name=f"preflight-{index}",
                name=f"Preflight {index}", owner=self.owner, creator=self.owner)
            Membership.objects.create(user=self.owner, company=workspace, role=owner_role)
            Membership.objects.create(user=self.member, company=workspace, role=self.role)
            self.workspaces.append(workspace)
        self.invite = CompanyInvitation.create(email="private-invite@example.com",
            company=self.workspaces[1], role=self.role, inviter=self.owner)
        CompanyInvitation.objects.filter(pk=self.invite.pk).update(status="revoked")

    def grant(self, code):
        permission, _ = Permission.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(Company), codename=code,
            defaults={"name": code})
        self.role.permissions.add(permission)

    def test_command_is_deterministic_read_only_and_includes_history(self):
        self.grant("loan_repay")
        with CaptureQueriesContext(connection) as queries:
            output = StringIO()
            call_command("role_migration_preflight", stdout=output)
        report = json.loads(output.getvalue())
        again = StringIO()
        call_command("role_migration_preflight", stdout=again)
        self.assertEqual(output.getvalue(), again.getvalue())
        self.assertFalse(any(q["sql"].lstrip().upper().startswith(
            ("INSERT ", "UPDATE ", "DELETE ")) for q in queries))
        self.assertTrue(any("READ ONLY" in q["sql"] for q in queries))
        self.assertNotIn("private-invite@example.com", output.getvalue())
        self.assertNotIn("preflight-member", output.getvalue())
        self.assertIn(self.unused.pk, report["unreferenced_role_ids"])
        self.assertEqual(report["invitations"][0]["status"], "revoked")
        copies = [r for r in report["proposed_role_copies"] if r["legacy_role_id"] == self.role.pk]
        self.assertEqual(len(copies), 2)
        self.assertIn(self.invite.pk, copies[1]["invitation_ids"])
        row = next(r for r in report["local_roles"] if r["role_id"] == self.role.pk and r["workspace_id"] == self.workspaces[0].pk)
        self.assertEqual(set(row["effective_actions"]),
            resolve_workspace_access(actor=self.member, workspace=self.workspaces[0]).actions)
        self.grant("loan_release")
        self.assertNotEqual(report["inventory_fingerprint"], build_role_preflight()["inventory_fingerprint"])

    def test_catalog_collisions_delegation_and_inactive_workspaces(self):
        self.grant("workspace_settings")
        self.grant("team_invite")
        self.grant("unrecognized_grant")
        self.grant("dea_entry_view")
        other = Role.objects.create(name=" custom REVIEW ")
        CompanyInvitation.create(email="other-private@example.com", company=self.workspaces[0],
                                 role=other, inviter=self.owner)
        Company.all_objects.filter(pk=self.workspaces[1].pk).update(lifecycle_state="ARCHIVED")
        report = build_role_preflight()
        self.assertTrue(any(w["id"] == self.workspaces[1].pk and w["lifecycle_state"] == "ARCHIVED"
                            for w in report["workspaces"]))
        kinds = {f["kind"] for f in report["findings"]}
        self.assertTrue({"unknown_codes", "retired_codes", "normalized_name_collision",
                         "sensitive_non_admin_role", "custom_role_delegation_review"} <= kinds)
        self.assertNotIn("owner_mirror_mismatch", kinds)

    def test_name_case_does_not_invent_default_permissions(self):
        lower = Role.objects.create(name="viewer")
        upper, _ = Role.objects.get_or_create(name="Viewer")
        report = build_role_preflight()
        rows = {r["role_id"]: r for r in report["roles"]}
        self.assertEqual(rows[lower.pk]["default_codes"], [])
        self.assertIn("data_view", rows[upper.pk]["default_codes"])
