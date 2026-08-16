import ast
from pathlib import Path

from django.test import SimpleTestCase


TENANT_APPS_ROOT = Path(__file__).resolve().parent


def _runtime_python_files(*app_names):
    for app_name in app_names:
        app_root = TENANT_APPS_ROOT / app_name
        for path in app_root.rglob("*.py"):
            parts = set(path.parts)
            if "migrations" in parts or "tests" in parts:
                continue
            if path.name.startswith("test_") or path.name == "tests.py":
                continue
            yield path


def _imports_for(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                yield node.module


class ArchitectureBoundaryTests(SimpleTestCase):
    def assert_no_forbidden_imports(self, files, forbidden_prefixes, allowed_imports):
        violations = []
        for path in files:
            for import_name in _imports_for(path):
                if import_name in allowed_imports:
                    continue
                if any(
                    import_name == prefix or import_name.startswith(f"{prefix}.")
                    for prefix in forbidden_prefixes
                ):
                    rel_path = path.relative_to(TENANT_APPS_ROOT.parent.parent)
                    violations.append(f"{rel_path}: {import_name}")

        self.assertEqual(violations, [])

    def test_surviving_apps_do_not_import_retired_apps(self):
        files = _runtime_python_files("party", "loans", "notify_v2", "rates")
        self.assert_no_forbidden_imports(
            files,
            forbidden_prefixes=[
                "apps.tenant_apps.dea",
                "apps.tenant_apps.accounting",
                "apps.tenant_apps.standalone_accounting",
                "apps.tenant_apps.girvi",
                "apps.tenant_apps.contact",
                "apps.tenant_apps.product",
                "apps.tenant_apps.savings_scheme",
                "apps.tenant_apps.terms",
            ],
            allowed_imports=set(),
        )
