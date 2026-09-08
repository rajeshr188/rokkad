from django.core.exceptions import ImproperlyConfigured
from django.db import connection, IntegrityError
from django.test import SimpleTestCase, TestCase
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from apps.tenancy.context import current_workspace_id, workspace_context


class WorkspaceContextValidationTests(SimpleTestCase):
    def test_rejects_missing_non_numeric_and_non_positive_ids(self):
        for value in (None, "", "not-a-number", 0, -1):
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                with workspace_context(value):
                    pass

    def test_workspace_middleware_context_spans_until_response(self):
        from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware

        middleware = SecureWorkspaceMiddleware(lambda request: None)
        request = SimpleNamespace()
        workspace = SimpleNamespace(id=17)
        manager = MagicMock()

        with patch("apps.orgs.middleware_v2.workspace_context", return_value=manager):
            middleware._set_workspace_context(request, workspace)

        manager.__enter__.assert_called_once_with()
        self.assertIs(request.workspace, workspace)

        response = object()
        self.assertIs(middleware.process_response(request, response), response)
        manager.__exit__.assert_called_once_with(None, None, None)


class WorkspaceContextDatabaseTests(TestCase):
    def test_deferred_failure_rolls_back_before_context_is_cleared(self):
        from apps.orgs.models import Company

        with self.assertRaises(IntegrityError):
            with workspace_context(17):
                Company.all_objects.create(
                    name="Invalid boundary owner", schema_name="invalid-boundary-owner",
                    owner_id=9876543, creator_id=9876543,
                )

        self.assertFalse(Company.all_objects.filter(name="Invalid boundary owner").exists())
        self.assertIsNone(current_workspace_id())
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.workspace_id', true)")
            self.assertIn(cursor.fetchone()[0], (None, ""))

    def test_same_workspace_nested_scope_waits_for_outer_completion(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company

        with workspace_context(17):
            with workspace_context(17):
                workspace = Company.all_objects.create(
                    name="Deferred boundary owner", schema_name="deferred-boundary-owner",
                    owner_id=9876543, creator_id=9876543,
                )
            get_user_model().objects.create(pk=9876543, username="deferred-boundary-owner")

        self.assertTrue(Company.all_objects.filter(pk=workspace.pk).exists())
        self.assertIsNone(current_workspace_id())

    def test_sets_transaction_local_database_and_python_context(self):
        self.assertIsNone(current_workspace_id())

        with workspace_context(17):
            self.assertEqual(current_workspace_id(), 17)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.workspace_id', true)")
                self.assertEqual(cursor.fetchone()[0], "17")

        self.assertIsNone(current_workspace_id())

    def test_rejects_conflicting_nested_context(self):
        with workspace_context(17):
            with self.assertRaises(ImproperlyConfigured):
                with workspace_context(18):
                    pass
