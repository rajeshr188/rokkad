import sys
from unittest.mock import patch

from django.test import SimpleTestCase

from scripts import start_monitoring


class MonitoringStartupTests(SimpleTestCase):
    def test_explicit_multi_workspace_scope_and_bounded_defaults(self):
        self.assertEqual(start_monitoring.worker_arguments({"ROKKAD_MONITOR_WORKSPACE_IDS": "1 2 3 1"}),
            [sys.executable, "-u", "manage.py", "reassess_pawn_loans", "--workspace-id", "1", "2", "3",
             "--batch-size", "10", "--busy-seconds", "5", "--repeat-seconds", "300"])

    def test_single_workspace_compatibility_and_explicit_list_precedence(self):
        self.assertIn("7", start_monitoring.worker_arguments({"ROKKAD_MONITOR_WORKSPACE_ID": "7"}))
        self.assertNotIn("7", start_monitoring.worker_arguments(
            {"ROKKAD_MONITOR_WORKSPACE_ID": "7", "ROKKAD_MONITOR_WORKSPACE_IDS": "2 3"}))

    def test_invalid_configuration_fails_before_runtime_database_check(self):
        cases = ({}, {"ROKKAD_MONITOR_WORKSPACE_IDS": ""}, {"ROKKAD_MONITOR_WORKSPACE_IDS": "0"},
                 {"ROKKAD_MONITOR_WORKSPACE_IDS": "1,2"}, {"ROKKAD_MONITOR_WORKSPACE_IDS": "1 -2"})
        for values in cases:
            with self.subTest(values=values), patch.dict(start_monitoring.os.environ, values, clear=True), \
                    patch("scripts.start_web.check_runtime") as check, self.assertRaises(ValueError):
                start_monitoring.main()
            check.assert_not_called()

    def test_all_numeric_bounds_are_enforced(self):
        for key, values in (("ROKKAD_MONITOR_BATCH_SIZE", ("0", "1001", "ten")),
                            ("ROKKAD_MONITOR_BUSY_SECONDS", ("0", "61")),
                            ("ROKKAD_MONITOR_REPEAT_SECONDS", ("0", "59", "86401"))):
            for value in values:
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    start_monitoring.worker_arguments({"ROKKAD_MONITOR_WORKSPACE_IDS": "1", key: value})

    def test_schema_and_restricted_runtime_check_precedes_exec(self):
        calls = []
        with patch.dict(start_monitoring.os.environ, {"ROKKAD_MONITOR_WORKSPACE_IDS": "1 2 3"}, clear=True), \
                patch("scripts.start_web.check_runtime", side_effect=lambda: calls.append("check")), \
                patch.object(start_monitoring.os, "execv", side_effect=lambda *_: calls.append("exec")):
            start_monitoring.main()
        self.assertEqual(calls, ["check", "exec"])

    def test_failed_runtime_check_never_starts_worker(self):
        with patch.dict(start_monitoring.os.environ, {"ROKKAD_MONITOR_WORKSPACE_IDS": "1"}, clear=True), \
                patch("scripts.start_web.check_runtime", side_effect=RuntimeError("Pending migrations")), \
                patch.object(start_monitoring.os, "execv") as execute, self.assertRaises(RuntimeError):
            start_monitoring.main()
        execute.assert_not_called()
