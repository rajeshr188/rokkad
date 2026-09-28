import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from scripts.platform_mail_watchdog import inspect


class WatchdogTests(SimpleTestCase):
    def test_paused_health_and_latched_failure_without_network(self):
        with TemporaryDirectory() as path:
            directory = Path(path)
            (directory/"alerts").mkdir()
            config = {"command": ["private-command"], "reviewed_before": "2026-09-26T00:00:00Z",
                      "dispatch_marker": str(directory/"enabled")}
            def process(argv):
                output = json.dumps({"flags": [], "queued_source_problems": [], "review_truncated": False,
                                     "sending_enabled": False}) if argv[0] == "private-command" else "LoadState=loaded\nResult=success\n"
                return SimpleNamespace(returncode=0, stdout=output)
            with patch("scripts.platform_mail_watchdog.run", side_effect=process):
                self.assertEqual(inspect(config, directory)["flags"], [])
                (directory/"alerts"/"feedback.json").write_text("{}")
                self.assertIn("unacknowledged_worker_failure", inspect(config, directory)["flags"])
                (directory/"enabled").touch()
                self.assertIn("dispatch_gates_disagree", inspect(config, directory)["flags"])

    def test_failed_inspection_is_visible_and_does_not_expose_output(self):
        with TemporaryDirectory() as path, patch("scripts.platform_mail_watchdog.run",
                return_value=SimpleNamespace(returncode=1, stdout="private credentials must not leak")):
            config = {"command": ["private-command"], "reviewed_before": "2026-09-26T00:00:00Z",
                      "dispatch_marker": str(Path(path)/"enabled")}
            result = inspect(config, Path(path))
            self.assertIn("queue_inspection_failed", result["flags"])
            self.assertNotIn("credentials", json.dumps(result))
