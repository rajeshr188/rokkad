import ast
from pathlib import Path

from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse

from apps.tenant_apps.dea.views import expense
from apps.tenant_apps.dea.views import voucher as voucher_views
from apps.tenant_apps.dea.views.voucher_hub import voucher_hub


@override_settings(ROOT_URLCONF="django_project.tenant_urls")
class Phase7CleanupReadinessTests(SimpleTestCase):
    """Characterize legacy/accountant surfaces before Phase 7 cleanup."""

    maxDiff = None

    def test_accountant_voucher_routes_resolve_before_cleanup(self):
        route_expectations = {
            "dea_voucher_hub": voucher_hub,
            "dea_voucher_post": voucher_views.post_voucher,
            "dea_voucher_reverse": voucher_views.reverse_voucher,
            "dea_expense_post": expense.post_expense_voucher,
        }

        for route_name, expected_view in route_expectations.items():
            kwargs = {"pk": 1} if route_name != "dea_voucher_hub" else {}
            with self.subTest(route=route_name):
                match = resolve(reverse(route_name, kwargs=kwargs))
                self.assertIs(match.func, expected_view)

    def test_runtime_code_does_not_import_legacy_direct_write_engine(self):
        project_root = Path(__file__).resolve().parents[4]
        runtime_roots = [
            project_root / "apps" / "tenant_apps" / "dea",
            project_root / "apps" / "tenant_apps" / "girvi",
        ]
        forbidden_modules = {
            "apps.tenant_apps.dea.posting.legacy_direct_write_engine",
            "apps.tenant_apps.dea.posting.legacy_direct_write_engine.BasePostingEngine",
            "apps.tenant_apps.dea.posting.legacy_direct_write_engine.DjangoPostingEngine",
        }
        violations = []

        for root in runtime_roots:
            for path in root.rglob("*.py"):
                if _is_excluded_from_runtime_import_scan(path):
                    continue
                tree = ast.parse(
                    path.read_text(encoding="utf-8-sig"),
                    filename=str(path),
                )
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in forbidden_modules:
                                violations.append(f"{path}: import {alias.name}")
                    elif isinstance(node, ast.ImportFrom):
                        module = node.module or ""
                        imported_names = {alias.name for alias in node.names}
                        if module in forbidden_modules or (
                            module == "apps.tenant_apps.dea.posting.legacy_direct_write_engine"
                            and imported_names
                        ):
                            violations.append(
                                f"{path}: from {module} import {', '.join(sorted(imported_names))}"
                            )

        self.assertEqual(violations, [])

    def test_voucher_view_legacy_materialization_helpers_are_removed(self):
        voucher_view_path = Path(voucher_views.__file__)
        tree = ast.parse(
            voucher_view_path.read_text(encoding="utf-8-sig"),
            filename=str(voucher_view_path),
        )
        forbidden_helpers = {
            "_create_journal_entry",
            "_create_ledger_transactions",
            "_create_account_transactions",
            "_create_reversal_journal_entry",
        }
        defined_helpers = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }

        self.assertEqual(defined_helpers & forbidden_helpers, set())


def _is_excluded_from_runtime_import_scan(path: Path) -> bool:
    parts = set(path.parts)
    if {"migrations", "tests", "__pycache__"} & parts:
        return True
    if path.name == "legacy_direct_write_engine.py":
        return True
    return False
