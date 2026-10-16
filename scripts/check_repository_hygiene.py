"""Reject tracked generated files; never delete local files or inspect their contents."""
import subprocess
import sys


GENERATED_ROOTS = {"staticfiles", "outputs", "output", "media", ".tmp", "tmp",
                   ".worktrees", ".local-backups", "backup", "%SystemDrive%"}


def violations(paths):
    return [path for path in paths if path.split("/", 1)[0] in GENERATED_ROOTS
            or "__pycache__" in path.split("/") or path.endswith((".pyc", ".pyo"))]


def main():
    paths = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    errors = violations(filter(None, paths))
    if errors:
        print("Generated files must not be tracked:\n" + "\n".join(errors))
        return 1
    print("No tracked generated files in protected runtime/output directories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
