from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.statement import verification_session_detail


class StatementViewReadModelTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.statement.render")
    @patch("apps.tenant_apps.girvi.views.statement.build_statement_detail_read_model")
    @patch("apps.tenant_apps.girvi.views.statement.get_object_or_404")
    def test_verification_session_detail_delegates_read_model(
        self,
        mock_get_object,
        mock_read_model,
        mock_render,
    ):
        request = self.factory.get("/girvi/statement/1/")
        request.user = self.user
        request.tenant = SimpleNamespace(schema_name="tenant-1", owner=self.user)

        statement = SimpleNamespace(pk=1)
        mock_get_object.return_value = statement
        mock_read_model.return_value = {
            "statement": statement,
            "items": [],
            "summary": {"dc": []},
        }

        response = SimpleNamespace(status_code=200)
        mock_render.return_value = response

        result = verification_session_detail(request, pk=1)

        self.assertEqual(result, response)
        mock_read_model.assert_called_once_with(statement)
        context = mock_render.call_args.kwargs["context"]
        self.assertIn("statement", context)
        self.assertIn("items", context)
        self.assertIn("summary", context)
