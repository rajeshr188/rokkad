"""
CI guardrail: enforce that no file outside dea/ imports DEA internals directly.

Rule: only dea/facade.py may be imported from outside apps/tenant_apps/dea/.
      All other dea sub-modules (models/, posting/, services/, utils/) are internal.

Usage:
    python scripts/check_dea_boundary.py          # exits 1 if violations found
    python scripts/check_dea_boundary.py --list   # prints violations and exits 1

Add to CI:
    - python scripts/check_dea_boundary.py
"""

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
TENANT_APPS = REPO_ROOT / "apps" / "tenant_apps"
DEA_DIR = TENANT_APPS / "dea"

# Pattern: any cross-app import into dea that is NOT dea.facade
VIOLATION_PATTERN = re.compile(
    r"""from\s+apps\.tenant_apps\.dea\.(?!facade\b)([a-zA-Z0-9_.]+)"""
)

# Files explicitly allowlisted (structural coupling that requires a larger refactor,
# or admin/seeding utilities that have acceptable DEA access).
# Each entry is a path relative to REPO_ROOT (forward slashes).
ALLOWLISTED_FILES = {
    # DEPRECATED model file — Loan/LoanPayment removed BusinessDoc inheritance (2026-05-03)
    # but AccountTransaction/LedgerTransaction are still used for historical data queries.
    # Remove this entry when loan.py is deleted (planned Q3 2026).
    "apps/tenant_apps/girvi/models/loan.py",
    # Admin seeding utility — VoucherType bootstrapping is acceptable here.
    "apps/orgs/management/commands/seed_workspace_defaults.py",
    # Dashboard reporting views — use DEA accounting query models directly.
    # TODO: wrap AccountStatement/Ledger queries in facade reporting functions.
    "pages/views.py",
}

# Path patterns to skip entirely (test directories, migrations, etc.)
SKIP_PATTERNS = [
    lambda p: any(part in ("tests", "test") or part.startswith("test_") for part in p.parts),
    lambda p: "migrations" in p.parts,
]


def is_inside_dea(path: Path) -> bool:
    try:
        path.relative_to(DEA_DIR)
        return True
    except ValueError:
        return False


def is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return rel in ALLOWLISTED_FILES


def is_skipped(path: Path) -> bool:
    return any(check(path) for check in SKIP_PATTERNS)


def find_violations() -> list[tuple[Path, int, str]]:
    violations = []
    for py_file in REPO_ROOT.rglob("*.py"):
        if is_inside_dea(py_file):
            continue
        if is_allowlisted(py_file):
            continue
        if is_skipped(py_file):
            continue
        try:
            lines = py_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, start=1):
            if VIOLATION_PATTERN.search(line):
                violations.append((py_file, lineno, line.strip()))
    return violations


def main():
    parser = argparse.ArgumentParser(description="Enforce DEA facade boundary.")
    parser.add_argument("--list", action="store_true", help="Print all violations.")
    args = parser.parse_args()

    violations = find_violations()
    if not violations:
        print("DEA boundary OK — no violations found.")
        sys.exit(0)

    print(f"DEA BOUNDARY VIOLATION: {len(violations)} direct import(s) into DEA internals found.")
    print("Only 'from apps.tenant_apps.dea.facade import ...' is allowed outside dea/.\n")
    if args.list:
        for path, lineno, line in violations:
            rel = path.relative_to(REPO_ROOT)
            print(f"  {rel}:{lineno}  {line}")
    else:
        print("Run with --list to see all violations.")
    sys.exit(1)


if __name__ == "__main__":
    main()
