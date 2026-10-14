from datetime import date, timedelta
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.exceptions import PermissionDenied
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.loans.services.risk_snapshots import RiskSnapshotRefreshError

MODULE = "apps.tenant_apps.loans.management.commands.reassess_pawn_loans."
EMPTY = {"selected": 0, "current": 0, "errors": []}
SUCCESS = {"selected": 2, "current": 2, "errors": []}


class ReassessPawnLoansCommandTests(SimpleTestCase):
    @patch(MODULE + "signal.signal")
    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_termination_stops_cleanly_and_restores_handler(self, reassess, register):
        previous = object()
        register.return_value = previous
        def terminate(**kwargs):
            register.call_args.args[1](15, None)
        reassess.side_effect = terminate
        output = StringIO()
        call_command("reassess_pawn_loans", workspace_id=5, repeat_seconds=300, stdout=output)
        self.assertIn("Monitoring stopped.", output.getvalue())
        self.assertEqual(register.call_count, 2)
        self.assertIs(register.call_args.args[1], previous)

    @patch(MODULE + "signal.signal")
    @patch(MODULE + "reassess_pawn_loans_pass", side_effect=RuntimeError("Unexpected failure"))
    def test_unexpected_failure_restores_termination_handler(self, reassess, register):
        previous = object()
        register.return_value = previous
        with self.assertRaisesMessage(RuntimeError, "Unexpected failure"):
            call_command("reassess_pawn_loans", workspace_id=5)
        self.assertEqual(register.call_count, 2)
        self.assertIs(register.call_args.args[1], previous)

    @patch(MODULE + "threading.current_thread", return_value=object())
    @patch(MODULE + "signal.signal")
    @patch(MODULE + "reassess_pawn_loans_pass", return_value=EMPTY)
    def test_non_main_thread_does_not_install_signal_handler(self, reassess, register, current):
        call_command("reassess_pawn_loans", workspace_id=5, stdout=StringIO())
        register.assert_not_called()

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
        today = timezone.localdate()
        call_command("reassess_pawn_loans", workspace_id=5, as_of=today, batch_size=50, stdout=output)
        self.assertIn("workspace=5 selected=2 current=2 errors=0", output.getvalue())
        reassess.assert_called_once_with(workspace_id=5, as_of_date=today, batch_size=50)

    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_non_today_override_is_rejected_before_any_workspace_turn(self, reassess):
        for days in (-1, 1):
            with self.subTest(days=days), self.assertRaisesMessage(CommandError, "only be refreshed for today"):
                call_command("reassess_pawn_loans", workspace_id=[5, 6],
                             as_of=timezone.localdate() + timedelta(days=days))
        reassess.assert_not_called()

    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_access_denial_does_not_skip_the_next_workspace(self, reassess):
        reassess.side_effect = [PermissionDenied("Business writes denied"), SUCCESS]
        errors, output = StringIO(), StringIO()
        with self.assertRaisesMessage(CommandError, "1 PawnLoan"):
            call_command("reassess_pawn_loans", workspace_id=[5, 6], stderr=errors, stdout=output)
        self.assertIn("workspace=5 Business writes denied", errors.getvalue())
        self.assertIn("workspace=6 selected=2 current=2 errors=0", output.getvalue())
        self.assertEqual([call.kwargs["workspace_id"] for call in reassess.call_args_list], [5, 6])

    @patch(MODULE + "time.sleep", side_effect=[None, KeyboardInterrupt])
    @patch(MODULE + "reassess_pawn_loans_pass")
    def test_repeating_worker_continues_after_access_denial(self, reassess, sleep):
        reassess.side_effect = [PermissionDenied("Read-only"), SUCCESS, EMPTY, EMPTY]
        call_command("reassess_pawn_loans", workspace_id=[5, 6], repeat_seconds=300,
                     busy_seconds=2, stdout=StringIO(), stderr=StringIO())
        self.assertEqual([call.kwargs["workspace_id"] for call in reassess.call_args_list], [5, 6, 5, 6])
        self.assertEqual([call.args[0] for call in sleep.call_args_list], [2, 300])

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
