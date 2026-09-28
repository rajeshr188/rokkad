"""Root-owned host watchdog. No email sending, secrets or message content in output."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timezone


JOBS = ("dispatch", "feedback", "recovery")


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
    atomic_json(directory/"health.json", result)
    print("PLATFORM_MAIL_" + ("ALERT: " + ",".join(result["flags"]) if result["flags"] else "OK (sending " + ("enabled" if result["dispatch_marker"] else "paused") + ")"))
    raise SystemExit(1 if result["flags"] else 0)


if __name__ == "__main__":
    main()
