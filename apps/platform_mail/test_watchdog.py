import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from scripts.platform_mail_watchdog import heartbeat, inspect, NoRedirect


class WatchdogTests(SimpleTestCase):
    def test_heartbeat_only_pings_healthy_running_mail_and_never_exposes_errors(self):
        config = {"heartbeat_url": "https://uptime.betterstack.com/api/v1/heartbeat/private-token"}
        healthy = {"flags": [], "dispatch_marker": True}
        with patch("scripts.platform_mail_watchdog.urllib.request.build_opener") as opener:
            self.assertEqual(heartbeat({}, healthy), "disabled")
            self.assertEqual(heartbeat(config, {"flags": ["failure"], "dispatch_marker": True}), "withheld")
            self.assertEqual(heartbeat(config, {"flags": [], "dispatch_marker": False}), "withheld")
            self.assertEqual(heartbeat({"heartbeat_url": "https://example.com/private-token"}, healthy), "failed")
            opener.assert_not_called()
            opener.return_value.open.return_value.__enter__.return_value.status = 204
            self.assertEqual(heartbeat(config, healthy), "sent")
            opener.return_value.open.assert_called_once_with(config["heartbeat_url"], timeout=10)
            opener.return_value.open.side_effect = OSError(config["heartbeat_url"])
            self.assertEqual(heartbeat(config, healthy), "failed")
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, None, None, "https://example.com"))

    def test_dashboard_incidents_host_is_allowed_but_lookalikes_and_redirect_paths_are_not(self):
        healthy = {"flags": [], "dispatch_marker": True}
        with patch("scripts.platform_mail_watchdog.urllib.request.build_opener") as opener:
            for url in ("http://incidents.betterstack.com/api/v1/heartbeat/token",
                        "https://incidents.betterstack.com.evil.example/api/v1/heartbeat/token",
                        "https://incidents.betterstack.com/api/v1/heartbeat/token/fail",
                        "https://incidents.betterstack.com/api/v1/heartbeat/token?redirect=1"):
                self.assertEqual(heartbeat({"heartbeat_url": url}, healthy), "failed")
            opener.assert_not_called()
            url = "https://incidents.betterstack.com/api/v1/heartbeat/dashboard-token"
            opener.return_value.open.return_value.__enter__.return_value.status = 200
            self.assertEqual(heartbeat({"heartbeat_url": url}, healthy), "sent")
            opener.return_value.open.assert_called_once_with(url, timeout=10)

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
