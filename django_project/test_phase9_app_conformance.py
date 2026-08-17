from pathlib import Path

from django.test import SimpleTestCase


SUPPORTED_APP_ROOT = Path("apps/tenant_apps")
DIRECT_AUTH_MARKERS = ("is_platform_admin", "get_workspace_role_name")
KNOWN_DIRECT_AUTH_MODULES = {
    "loans/access.py",
    "loans/services/pawn_auctions.py",
    "loans/services/pawn_reversal.py",
    "loans/services/physical_verification.py",
    "loans/services/storage_operations.py",
    "loans/views.py",
    "loans/web/pawn_custody_actions.py",
    "loans/web/pawn_financial_actions.py",
    "loans/web/reports.py",
}


class Phase9AppConformanceBaselineTests(SimpleTestCase):
    def test_direct_authorization_debt_is_frozen_to_reviewed_modules(self):
        found = set()
        for app in ("party", "loans", "notify_v2", "rates"):
            root = SUPPORTED_APP_ROOT / app
            for path in root.rglob("*.py"):
                normalized = path.as_posix()
                if "/migrations/" in normalized or "test" in path.name:
                    continue
                source = path.read_text(encoding="utf-8")
                if any(marker in source for marker in DIRECT_AUTH_MARKERS):
                    found.add(path.relative_to(SUPPORTED_APP_ROOT).as_posix())

        self.assertEqual(found, KNOWN_DIRECT_AUTH_MODULES)

    def test_phase9_plan_locks_conversion_order_and_scope(self):
        plan = Path(
            "docs/plans/control-plane-phase9-app-conformance.md"
        ).read_text(encoding="utf-8")
        for required in (
            "### BLOCKER",
            "### FIX IN CURRENT PHASE",
            "### DEFER TO LATER PHASE",
            "### OUT OF SCOPE",
            "Convert Rates",
            "Convert Party",
            "Convert Notify v2",
            "Convert Loans",
        ):
            self.assertIn(required, plan)
