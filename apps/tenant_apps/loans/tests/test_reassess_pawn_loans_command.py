from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase


class ReassessPawnLoansCommandTests(SimpleTestCase):
    def test_repeat_validates_interval_and_rejects_fixed_dates(self):
        for options in ({"repeat_seconds": 1}, {"repeat_seconds": 60, "as_of": date(2026, 1, 1)}):
            with self.assertRaises(CommandError):
                call_command("reassess_pawn_loans", workspace_id=5, **options)

    @patch("apps.tenant_apps.loans.management.commands.reassess_pawn_loans.close_old_connections")
    @patch("apps.tenant_apps.loans.management.commands.reassess_pawn_loans.time.sleep", side_effect=[None, KeyboardInterrupt])
    @patch("apps.tenant_apps.loans.management.commands.reassess_pawn_loans.workspace_context")
    @patch("apps.tenant_apps.loans.management.commands.reassess_pawn_loans.reassess_pawn_loans_batch")
    def test_repeat_owns_each_context_and_recomputes_date_after_failure(self, reassess, context, sleep, close):
        from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError
        reassess.side_effect = [RiskSnapshotRefreshError("Workspace unavailable"), {"selected": 0, "current": 0, "errors": []}]
        with patch("apps.tenant_apps.loans.management.commands.reassess_pawn_loans.timezone.localdate", side_effect=[date(2026, 9, 11), date(2026, 9, 12)]):
            call_command("reassess_pawn_loans", workspace_id=5, repeat_seconds=300, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(context.call_count, 2)
        self.assertEqual(context.return_value.__exit__.call_count, 2)
        self.assertEqual(reassess.call_args.kwargs["as_of_date"], date(2026, 9, 12))
        self.assertEqual(close.call_count, 4)

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
