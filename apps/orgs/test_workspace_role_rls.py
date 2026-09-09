from uuid import uuid4

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import connection, transaction, DatabaseError
from django.test import TransactionTestCase

from apps.orgs.models import Company, Role, WorkspaceRole, WorkspaceRoleGrant
from apps.orgs.services.workspace_roles import seed_workspace_roles
from apps.tenancy.context import workspace_context


class WorkspaceRoleRLSTests(TransactionTestCase):
    def test_role_and_grant_dml_is_isolated_under_restricted_role(self):
        owner = get_user_model().objects.create_user(username="local-role-rls")
        workspaces = [Company.objects.create(schema_name=f"role-rls-{i}", name=f"Role RLS {i}",
            owner=owner, creator=owner) for i in range(2)]
        profiles, grants = [], []
        for workspace in workspaces:
            seed_workspace_roles(workspace.pk)
            with workspace_context(workspace.pk):
                profiles.append(WorkspaceRole.objects.filter(workspace=workspace).first())
                grants.append(WorkspaceRoleGrant.objects.filter(workspace=workspace).first())
        extra = Role.objects.create(name="RLS extra")
        permission = Permission.objects.first()
        role = connection.ops.quote_name("role_scope_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON orgs_workspacerole, orgs_workspacerolegrant TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                self.assertEqual(WorkspaceRole.objects.count(), 0)
                self.assertEqual(WorkspaceRoleGrant.objects.count(), 0)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceRole.objects.create(workspace=workspaces[0], role=extra)
            with workspace_context(workspaces[0].pk):
                with connection.cursor() as cursor:
                    cursor.execute(f"SET LOCAL ROLE {role}")
                for model, foreign in ((WorkspaceRole, profiles[1]), (WorkspaceRoleGrant, grants[1])):
                    self.assertFalse(model.objects.filter(pk=foreign.pk).exists())
                    self.assertEqual(model.objects.filter(pk=foreign.pk).update(workspace=workspaces[0]), 0)
                    self.assertEqual(model.objects.filter(pk=foreign.pk).delete()[0], 0)
                for model, own in ((WorkspaceRole, profiles[0]), (WorkspaceRoleGrant, grants[0])):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.filter(pk=own.pk).update(workspace=workspaces[1])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceRole.objects.bulk_create([WorkspaceRole(workspace=workspaces[1], role=extra)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceRoleGrant.objects.bulk_create([WorkspaceRoleGrant(workspace=workspaces[0],
                        workspace_role=profiles[1], permission=permission)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceRoleGrant.objects.bulk_create([WorkspaceRoleGrant(workspace=workspaces[1],
                        workspace_role=profiles[1], permission=permission)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    WorkspaceRole.objects.filter(pk=profiles[0].pk).update(role=extra)
                allowed = WorkspaceRole.objects.create(workspace=workspaces[0], role=extra)
                row = WorkspaceRoleGrant.objects.create(workspace=workspaces[0], workspace_role=allowed, permission=permission)
                self.assertEqual(WorkspaceRoleGrant.objects.filter(pk=row.pk).delete()[0], 1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
