from django.db import connection
from django.test import SimpleTestCase, TestCase

from .registry import rls_protected_models, workspace_owned_models


class WorkspaceModelRegistryTests(SimpleTestCase):
    def test_registry_accounts_for_every_surviving_business_model(self):
        models = workspace_owned_models()

        self.assertEqual(len(models), 97)
        self.assertEqual(
            {model._meta.app_label for model in models},
            {"party", "loans", "notify_v2", "rates", "orgs"},
        )
        for model in models:
            with self.subTest(model=model._meta.label):
                field = model._meta.get_field("workspace")
                self.assertFalse(field.null)
                self.assertEqual(field.remote_field.model._meta.label_lower, "orgs.company")

    def test_rls_rollout_registry_covers_every_surviving_model(self):
        labels = {model._meta.label_lower for model in rls_protected_models()}

        self.assertEqual(len(labels), 97)
        self.assertEqual(
            {label.split(".", 1)[0] for label in labels},
            {"loans", "notify_v2", "party", "rates", "orgs"},
        )


class WorkspaceDataPlaneMetadataTests(TestCase):
    def test_every_registered_model_has_canonical_forced_rls_metadata(self):
        models = rls_protected_models()
        expected_tables = {model._meta.db_table for model in models}

        for model in models:
            with self.subTest(model=model._meta.label):
                field = model._meta.get_field("workspace")
                self.assertFalse(field.null)
                self.assertEqual(
                    field.remote_field.model._meta.label_lower,
                    "orgs.company",
                )

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                       p.polname, pg_get_expr(p.polqual, p.polrelid),
                       pg_get_expr(p.polwithcheck, p.polrelid)
                FROM pg_class c
                LEFT JOIN pg_policy p
                  ON p.polrelid = c.oid AND p.polname = 'workspace_isolation'
                WHERE c.relnamespace = 'public'::regnamespace
                  AND c.relname = ANY(%s)
                ORDER BY c.relname
                """,
                [sorted(expected_tables)],
            )
            metadata = {row[0]: row[1:] for row in cursor.fetchall()}

        self.assertEqual(set(metadata), expected_tables)
        for table, row in metadata.items():
            with self.subTest(table=table):
                enabled, forced, policy_name, using, with_check = row
                self.assertTrue(enabled)
                self.assertTrue(forced)
                self.assertEqual(policy_name, "workspace_isolation")
                self.assertIn("app.workspace_id", using)
                self.assertIn("app.workspace_id", with_check)
