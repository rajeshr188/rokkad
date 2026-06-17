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

    def test_apps_use_dea_public_facade_only(self):
        files = _runtime_python_files("contact", "girvi", "purchase", "sales")
        self.assert_no_forbidden_imports(
            files,
            forbidden_prefixes=[
                "apps.tenant_apps.dea.models",
                "apps.tenant_apps.dea.posting",
                "apps.tenant_apps.dea.services",
            ],
            allowed_imports={"apps.tenant_apps.dea.facade"},
        )

    def test_contact_uses_girvi_public_facade_only(self):
        files = _runtime_python_files("contact")
        self.assert_no_forbidden_imports(
            files,
            forbidden_prefixes=[
                "apps.tenant_apps.girvi.models",
                "apps.tenant_apps.girvi.service_modules",
                "apps.tenant_apps.girvi.views",
                "apps.tenant_apps.girvi.transitions",
            ],
            allowed_imports={"apps.tenant_apps.girvi.facade"},
        )

    def test_dea_uses_girvi_public_facade_only(self):
        files = _runtime_python_files("dea")
        self.assert_no_forbidden_imports(
            files,
            forbidden_prefixes=[
                "apps.tenant_apps.girvi.models",
                "apps.tenant_apps.girvi.service_modules",
                "apps.tenant_apps.girvi.views",
                "apps.tenant_apps.girvi.transitions",
            ],
            allowed_imports={"apps.tenant_apps.girvi.facade"},
        )
