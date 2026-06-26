from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.statement import Statement


class StatementModelSelectorDelegationTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.selectors.get_statement_missing_loans")
    def test_get_missing_loans_delegates(self, mock_selector):
        statement = Statement()
        marker = object()
        mock_selector.return_value = marker

        result = statement.get_missing_loans()

        self.assertIs(result, marker)
        mock_selector.assert_called_once_with(statement)

    @patch("apps.tenant_apps.girvi.selectors.get_statement_released_items_present")
    def test_get_released_items_present_delegates(self, mock_selector):
        statement = Statement()
        marker = object()
        mock_selector.return_value = marker

        result = statement.get_released_items_present()

        self.assertIs(result, marker)
        mock_selector.assert_called_once_with(statement)

    @patch("apps.tenant_apps.girvi.selectors.build_statement_verification_summary")
    def test_get_verification_summary_delegates(self, mock_selector):
        statement = Statement()
        marker = {"missing_count": 2}
        mock_selector.return_value = marker

        result = statement.get_verification_summary()

        self.assertEqual(result, marker)
        mock_selector.assert_called_once_with(statement)
