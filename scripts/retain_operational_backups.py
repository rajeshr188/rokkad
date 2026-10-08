"""Bounded Linode database-backup retention; dry run unless --apply is supplied.

Install as ExecStartPost of the hourly backup service. This host operator does
not use Django, copy data off-host, or touch release checkpoints or R2 media.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess


FOLDER = Path("/home/rokkad/deploy/cutover-20260924/backups/operational")
NAME = re.compile(r"production-(\d{8}T\d{6}Z)\.dump\Z")


def regular(path, folder):
    if path.is_symlink() or path.resolve().parent != folder.resolve():
        raise ValueError("Backup path escapes its approved directory")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("Backup entry is not a regular file")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def catalogue(path):
    with path.open("rb") as incoming:
        result = subprocess.run(
            ["docker", "exec", "-i", "rokkad-rehearsal-db-db-1", "pg_restore", "--list"],
            stdin=incoming, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=120,
        )
    if result.returncode:
        raise ValueError("Retained archive catalogue validation failed")


def plan_retention(folder, now, check_catalogue=catalogue):
    """Validate a complete plan before allowing any removals."""
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Invalid backup directory")
    copies = []
    fingerprints = {}
    digests = {}
    dates = {}
    for path in sorted(folder.iterdir()):
        match = NAME.fullmatch(path.name)
        if not match:
            continue  # Checkpoints, partial files and unrelated files are protected.
        stamp = datetime.strptime(match[1], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        if stamp > now + timedelta(minutes=5):
            raise ValueError("Backup timestamp is in the future")
        sidecar = path.with_suffix(".dump.sha256")
        fingerprints[path] = regular(path, folder)
        fingerprints[sidecar] = regular(sidecar, folder)
        if not fingerprints[path][2]:
            raise ValueError("Empty completed backup")
        fields = sidecar.read_text().split()
        if not fields or not re.fullmatch(r"[0-9a-f]{64}", fields[0]):
            raise ValueError("Invalid backup checksum sidecar")
        with path.open("rb") as incoming:
            digest = hashlib.file_digest(incoming, "sha256").hexdigest()
        if digest != fields[0]:
            raise ValueError("Completed backup checksum does not match")
        digests[path] = digest
        copies.append(path)
        dates[path] = stamp
    if not copies:
        raise ValueError("No completed backup exists")
    newest = copies[-1]
    if now - dates[newest] > timedelta(minutes=120):
        raise ValueError("Fresh successful backup required before expiry")
    latest_path = folder / "latest.json"
    fingerprints[latest_path] = regular(latest_path, folder)
    latest = json.loads(latest_path.read_text())
    if (latest.get("file") != str(newest)
            or latest.get("sha256") != digests[newest]
            or latest.get("size_bytes") != fingerprints[newest][2]
            or latest.get("archive_catalog_checked") is not True):
        raise ValueError("Latest metadata does not identify the newest verified backup")
    retained = set(copies[-24:])
    daily = {}
    first_date = now.date() - timedelta(days=29)
    for path in copies:
        if first_date <= dates[path].date() <= now.date():
            daily[dates[path].date()] = path
    retained.update(daily.values())
    for path in sorted(retained):
        check_catalogue(path)
    return dict(copies=copies, retained=retained,
                removed=[path for path in copies if path not in retained],
                fingerprints=fingerprints, latest=newest)


def apply_plan(folder, plan):
    # Recheck every inspected entry before the first deletion, under the shared lock.
    for path, fingerprint in plan["fingerprints"].items():
        if regular(path, folder) != fingerprint:
            raise ValueError("Backup set changed after validation; expiry refused")
    for path in plan["removed"]:
        path.with_suffix(".dump.sha256").unlink()
        path.unlink()


def main():
    import fcntl  # Linux-only operator; pure selection/validation is tested on Windows.

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    if FOLDER.resolve() != FOLDER or any(p.is_symlink() for p in (FOLDER, *FOLDER.parents)):
        raise ValueError("Operational directory must resolve to its fixed approved path")
    lock_path = FOLDER / ".backup.lock"
    regular(lock_path, FOLDER)
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        now = datetime.now(timezone.utc)
        plan = plan_retention(FOLDER, now)
        report = dict(checked_at=now.isoformat(), policy="24-hourly-plus-30-UTC-daily/1",
                      apply=args.apply, total=len(plan["copies"]), retained=len(plan["retained"]),
                      expired=len(plan["removed"]), latest=plan["latest"].name,
                      expire_bytes=sum(plan["fingerprints"][p][2] for p in plan["removed"]),
                      checkpoints_protected=True, off_host_copy=False)
        # Journal the exact validated proposal on-host before unlinking anything.
        with (FOLDER / "retention-audit.jsonl").open("a") as audit:
            audit.write(json.dumps({**report, "phase": "validated", "expiry_names":
                                    [p.name for p in plan["removed"]]}) + "\n")
            audit.flush()
            os.fsync(audit.fileno())
        if args.apply:
            apply_plan(FOLDER, plan)
        report["free_bytes"] = shutil.disk_usage(FOLDER).free
        report["low_space"] = report["free_bytes"] < 8 * 1024**3
        with (FOLDER / "retention-audit.jsonl").open("a") as audit:
            audit.write(json.dumps({**report, "phase": "completed"}) + "\n")
        temp = FOLDER / ".retention-last.partial"
        temp.write_text(json.dumps(report, indent=2) + "\n")
        temp.replace(FOLDER / "retention-last.json")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
