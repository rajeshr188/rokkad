from io import StringIO
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import get_itemtype_averages
from apps.tenant_apps.girvi.tasks import notify_interest_overdue, notify_pending_loans


class GirviCleanupGuardrailTests(SimpleTestCase):
    def test_legacy_do_command_is_disabled(self):
        with self.assertRaises(CommandError) as exc:
            call_command("do")

        self.assertIn("disabled", str(exc.exception).lower())

    def test_legacy_missingcol_requires_explicit_opt_in(self):
        with patch.dict("os.environ", {}, clear=False):
            with self.assertRaises(CommandError) as exc:
                call_command("missingcol", "dummy.csv", "tenant1")

        self.assertIn("girvi_enable_legacy_import_commands", str(exc.exception).lower())

    def test_legacy_missingcol_runs_with_explicit_opt_in(self):
        output = StringIO()

        with patch.dict("os.environ", {"GIRVI_ENABLE_LEGACY_IMPORT_COMMANDS": "1"}, clear=False):
            with patch("builtins.open") as open_mock:
                open_mock.return_value.__enter__.return_value = StringIO("id,lid\n1,L0001\n")
                with patch(
                    "apps.tenant_apps.girvi.management.commands.missingcol.Loan.objects.get"
                ) as get_mock:
                    with patch(
                        "apps.tenant_apps.girvi.management.commands.missingcol.schema_context"
                    ) as schema_context_mock:
                        schema_context_mock.return_value.__enter__.return_value = None
                        schema_context_mock.return_value.__exit__.return_value = None

                        loan = MagicMock()
                        get_mock.return_value = loan

                        call_command(
                            "missingcol",
                            "dummy.csv",
                            "tenant1",
                            stdout=output,
                        )

        loan.save.assert_called_once()
        self.assertIn("updated 1 rows", output.getvalue())

    def test_legacy_pending_loans_task_is_disabled(self):
        result = notify_pending_loans.run()

        self.assertEqual(result["status"], "disabled")
        self.assertIn("legacy_pending_loans", result["reason"])

    def test_legacy_interest_overdue_task_is_disabled(self):
        result = notify_interest_overdue.run()

        self.assertEqual(result["status"], "disabled")
        self.assertIn("legacy_interest_overdue", result["reason"])

    def test_itemtype_averages_no_longer_filters_on_removed_loan_type(self):
        filter_result = MagicMock()
        values_result = MagicMock()
        annotate_one = MagicMock()
        annotate_two = MagicMock()

        filter_result.values.return_value = values_result
        values_result.annotate.return_value = annotate_one
        annotate_one.annotate.return_value = annotate_two
        annotate_two.order_by.return_value = []

        with patch(
            "apps.tenant_apps.girvi.models.LoanItem.objects.filter",
            return_value=filter_result,
        ) as filter_mock:
            result = get_itemtype_averages()

        self.assertEqual(result, {})
        filter_mock.assert_called_once_with(loan__release__isnull=True)
