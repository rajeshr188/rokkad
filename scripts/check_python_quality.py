"""Run Ruff on maintained source and Black on changed Python files."""

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = ("accounts", "apps", "django_project", "helpers", "pages", "scripts")


def changed_files(base):
    paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", base, "--", "*.py"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    paths += subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "*.py"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    return sorted(
        path
        for path in set(paths)
        if (ROOT / path).is_file()
        and (path.split("/")[0] in SOURCE_ROOTS or path == "manage.py")
        and "migrations" not in path.split("/")
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base", default="HEAD", help="Git revision to compare (default HEAD)"
    )
    args = parser.parse_args()
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", *SOURCE_ROOTS, "manage.py"], cwd=ROOT
    )
    if result.returncode:
        return result.returncode
    files = changed_files(args.base)
    if not files:
        print("No changed Python files to format-check.")
        return 0
    return subprocess.run(
        [sys.executable, "-m", "black", "--check", *files], cwd=ROOT
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
