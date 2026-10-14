"""Start the existing bounded worker after validating explicit scope and runtime."""
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def worker_arguments(environ):
    # Keep the original single-Workspace deployment setting compatible.
    raw = environ.get("ROKKAD_MONITOR_WORKSPACE_IDS")
    if raw is None:
        raw = environ.get("ROKKAD_MONITOR_WORKSPACE_ID", "")
    try:
        ids = tuple(dict.fromkeys(int(value) for value in raw.split()))
        batch = int(environ.get("ROKKAD_MONITOR_BATCH_SIZE", "10"))
        busy = int(environ.get("ROKKAD_MONITOR_BUSY_SECONDS", "5"))
        idle = int(environ.get("ROKKAD_MONITOR_REPEAT_SECONDS", "300"))
    except (ValueError, TypeError) as exc:
        raise ValueError("Monitoring configuration requires integer values and space-separated Workspace IDs.") from exc
    if not ids or any(value < 1 for value in ids):
        raise ValueError("Monitoring requires explicit positive Workspace IDs.")
    if not 1 <= batch <= 1000 or not 1 <= busy <= 60 or not 60 <= idle <= 86400:
        raise ValueError("Monitoring batch/pause settings are outside the command's supported bounds.")
    return [sys.executable, "-u", "manage.py", "reassess_pawn_loans", "--workspace-id",
            *(str(value) for value in ids), "--batch-size", str(batch),
            "--busy-seconds", str(busy), "--repeat-seconds", str(idle)]


def main():
    arguments = worker_arguments(os.environ)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_project.settings.prod")
    from scripts.start_web import check_runtime
    check_runtime()
    os.execv(arguments[0], arguments)


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
