from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class ReassessPawnLoansCommandTests(SimpleTestCase):
    @patch(
        "apps.tenant_apps.loans.management.commands.reassess_pawn_loans.reassess_pawn_loans_batch"
    )
    @patch(
        "apps.tenant_apps.loans.management.commands.reassess_pawn_loans.workspace_context"
    )
    def test_reports_successful_bounded_batch(self, context, reassess):
        reassess.return_value = {"selected": 2, "current": 2, "errors": []}
        output = StringIO()

        call_command(
            "reassess_pawn_loans",
            workspace_id=5,
            as_of=date(2026, 8, 13),
            batch_size=50,
            stdout=output,
        )

        self.assertIn("selected=2 current=2 errors=0", output.getvalue())
        context.assert_called_once_with(5)
        reassess.assert_called_once_with(
            workspace_id=5,
            as_of_date=date(2026, 8, 13),
            batch_size=50,
        )

    @patch(
        "apps.tenant_apps.loans.management.commands.reassess_pawn_loans.reassess_pawn_loans_batch"
    )
    @patch(
        "apps.tenant_apps.loans.management.commands.reassess_pawn_loans.workspace_context"
    )
    def test_partial_failure_is_visible_to_scheduler(self, context, reassess):
        reassess.return_value = {
            "selected": 2,
            "current": 1,
            "errors": [{"loan_id": 9, "error": "Missing monitoring policy."}],
        }
        errors = StringIO()

        with self.assertRaisesMessage(CommandError, "1 PawnLoan"):
            call_command(
                "reassess_pawn_loans",
                workspace_id=5,
                as_of=date(2026, 8, 13),
                batch_size=50,
                stderr=errors,
            )

        self.assertIn("loan=9 error=Missing monitoring policy.", errors.getvalue())
        context.assert_called_once_with(5)
