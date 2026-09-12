from datetime import date
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError

MODULE = "apps.tenant_apps.loans.management.commands.reassess_pawn_loans."
EMPTY = {"selected": 0, "current": 0, "errors": []}
SUCCESS = {"selected": 2, "current": 2, "errors": []}


class ReassessPawnLoansCommandTests(SimpleTestCase):
    def test_invalid_options_are_rejected_before_database_work(self):
        for options in ({"repeat_seconds": 1}, {"repeat_seconds": 60, "as_of": date(2026, 1, 1)},
                        {"busy_seconds": 0}, {"busy_seconds": 61}, {"batch_size": 1001}):
            with self.assertRaises(CommandError):
                call_command("reassess_pawn_loans", workspace_id=5, **options)

    @patch(MODULE + "close_old_connections")
    @patch(MODULE + "time.sleep", side_effect=[None, KeyboardInterrupt])
    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_repeat_recomputes_date_after_failure(self, reassess, sleep, close):
        reassess.side_effect = [RiskSnapshotRefreshError("Workspace unavailable"), EMPTY]
        with patch(MODULE + "timezone.localdate", side_effect=[date(2026, 9, 11), date(2026, 9, 12)]):
            call_command("reassess_pawn_loans", workspace_id=5, repeat_seconds=300, stdout=StringIO(), stderr=StringIO())
        self.assertEqual(reassess.call_args.kwargs["as_of_date"], date(2026, 9, 12))
        self.assertEqual(close.call_count, 4)
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [300, 300])

    @patch(MODULE + "reassess_pawn_loans_pass", return_value=SUCCESS)
    def test_reports_successful_bounded_pass(self, reassess):
        output = StringIO()
        call_command("reassess_pawn_loans", workspace_id=5, as_of=date(2026, 8, 13), batch_size=50, stdout=output)
        self.assertIn("workspace=5 selected=2 current=2 errors=0", output.getvalue())
        reassess.assert_called_once_with(workspace_id=5, as_of_date=date(2026, 8, 13), batch_size=50)

    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_one_shot_reports_partial_failure_after_other_workspace_turns(self, reassess):
        reassess.side_effect = [{"selected": 2, "current": 1, "errors": [{"loan_id": 9, "error": "Missing policy."}]}, SUCCESS]
        errors = StringIO()
        with self.assertRaisesMessage(CommandError, "1 PawnLoan"):
            call_command("reassess_pawn_loans", workspace_id=[5, 6], stderr=errors, stdout=StringIO())
        self.assertIn("workspace=5 loan=9 error=Missing policy.", errors.getvalue())
        self.assertEqual([call.kwargs["workspace_id"] for call in reassess.call_args_list], [5, 6])

    @patch(MODULE + "time.sleep", side_effect=[None, None, KeyboardInterrupt])
    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_busy_workspaces_take_turns_and_empty_or_failed_rounds_back_off(self, reassess, sleep):
        partial = {"selected": 2, "current": 1, "errors": [{"loan_id": 9, "error": "Invalid evidence"}]}
        reassess.side_effect = [partial, SUCCESS, RiskSnapshotRefreshError("Suspended"), SUCCESS, EMPTY, EMPTY]
        call_command("reassess_pawn_loans", workspace_id=[5, 6, 5], repeat_seconds=300, busy_seconds=2,
                     stdout=StringIO(), stderr=StringIO())
        self.assertEqual([call.kwargs["workspace_id"] for call in reassess.call_args_list], [5, 6, 5, 6, 5, 6])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 2, 300])
