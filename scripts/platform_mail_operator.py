"""Host entry point; install root-private beside the watchdog configuration."""
import argparse
import getpass
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("action", choices=("check", "suppress"))
    parser.add_argument("--operator")
    parser.add_argument("--reference")
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit("Use sudo for this private deployment-operator command.")
    config = json.loads(Path(args.config).read_text())
    command = config["command"][:]
    if args.action == "check":
        raise SystemExit(subprocess.call(command + ["check_platform_mail_queue", "--since", config["reviewed_before"]]))
    active = subprocess.run(["systemctl", "show", "rokkad-platform-mail-dispatch.service", "-p", "ActiveState", "--value"],
                            capture_output=True, text=True, timeout=10)
    if Path(config["dispatch_marker"]).exists() or active.returncode or active.stdout.strip() not in ("inactive", "failed"):
        raise SystemExit("Pause dispatch and wait for its service to stop before suppressing a recipient.")
    if not args.operator or not args.reference:
        parser.error("suppress requires --operator and --reference")
    address = getpass.getpass("Recipient (hidden; never included in argv): ")
    command.insert(2, "-i")  # docker run -i, only for this private stdin operation.
    raise SystemExit(subprocess.run(command + ["suppress_platform_mail", "--operator", args.operator,
        "--reference", args.reference, "--recipient-stdin"], input=address+"\n", text=True).returncode)


if __name__ == "__main__":
    main()
