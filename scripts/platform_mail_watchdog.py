"""Root-owned host watchdog. No email sending, secrets or message content in output."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import re
import urllib.request
from datetime import datetime, timezone


JOBS = ("dispatch", "feedback", "recovery")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def heartbeat(config, result):
    """Optional external dead-man check. Never send queue data or error output.

    The root-only config holds the capability URL. An unhealthy/paused worker
    withholds success; the external monitor detects missing pings/server loss.
    """
    url = config.get("heartbeat_url")
    if not url:
        return "disabled"
    if result["flags"] or not result["dispatch_marker"]:
        return "withheld"
    if not isinstance(url, str) or not re.fullmatch(
        r"https://(?:uptime|incidents)\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9_-]+", url
    ):
        return "failed"
    try:
        # Do not forward the capability URL to another host or include a body.
        with urllib.request.build_opener(NoRedirect).open(url, timeout=10) as response:
            return "sent" if 200 <= response.status < 300 else "failed"
    except Exception:
        # Exception strings can contain the secret URL. Keep them private.
        return "failed"


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, timeout=70, **kwargs)


def atomic_json(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2))
    temporary.replace(path)


def inspect(config, directory):
    flags = []
    report = {}
    try:
        result = run(config["command"] + ["check_platform_mail_queue", "--since", config["reviewed_before"]])
        if result.returncode:
            flags.append("queue_inspection_failed")
        else:
            report = json.loads(result.stdout)
            flags.extend(report["flags"])
            if report["queued_source_problems"] or report["review_truncated"]:
                flags.append("queued_sources_need_review")
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
        flags.append("queue_inspection_failed")
    marker = Path(config["dispatch_marker"]).exists()
    if report and marker != report["sending_enabled"]:
        flags.append("dispatch_gates_disagree")
    services = {}
    for job in JOBS:
        unit = "rokkad-platform-mail-" + job
        try:
            result = run(["systemctl", "show", unit+".service", "-p", "Result", "-p", "LoadState"])
            state = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
            services[job] = state
            if result.returncode or state.get("LoadState") != "loaded" or state.get("Result") != "success":
                flags.append(job+"_service_failed")
            if marker and run(["systemctl", "is-active", unit+".timer"]).returncode:
                flags.append(job+"_timer_inactive")
        except (OSError, subprocess.TimeoutExpired):
            flags.append(job+"_inspection_failed")
    if any((directory/"alerts").glob("*.json")):
        flags.append("unacknowledged_worker_failure")
    return {"checked_at": datetime.now(timezone.utc).isoformat(), "flags": sorted(set(flags)),
            "queue": report, "services": services, "dispatch_marker": marker}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--record-failure", choices=(*JOBS, "acceptance"))
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() != 0:
        raise SystemExit("Run through the root-owned platform mail service.")
    config = json.loads(Path(args.config).read_text())
    directory = Path(config["state_directory"])
    (directory/"alerts").mkdir(parents=True, exist_ok=True)
    if args.record_failure:
        atomic_json(directory/"alerts"/(args.record_failure+".json"),
                    {"unit": args.record_failure, "recorded_at": datetime.now(timezone.utc).isoformat()})
        print("PLATFORM_MAIL_ALERT: worker failed; inspect private mail health.")
        return
    result = inspect(config, directory)
    result["external_heartbeat"] = heartbeat(config, result)
    if result["external_heartbeat"] == "failed":
        result["flags"].append("external_heartbeat_failed")
    atomic_json(directory/"health.json", result)
    print("PLATFORM_MAIL_" + ("ALERT: " + ",".join(result["flags"]) if result["flags"] else "OK (sending " + ("enabled" if result["dispatch_marker"] else "paused") + ")"))
    raise SystemExit(1 if result["flags"] else 0)


if __name__ == "__main__":
    main()
