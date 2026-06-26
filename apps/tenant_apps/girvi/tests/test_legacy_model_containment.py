import ast
from pathlib import Path

from django.test import SimpleTestCase

import apps.tenant_apps.girvi.models as girvi_models
from apps.tenant_apps.girvi import resources as girvi_resources
from apps.tenant_apps.girvi.models import legacy as legacy_models


GIRVI_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MODEL_NAMES = {"Loan", "LoanPayment"}


class LegacyModelContainmentTests(SimpleTestCase):
    def test_girvi_models_package_does_not_export_legacy_models(self):
        for name in FORBIDDEN_MODEL_NAMES:
            self.assertFalse(
                hasattr(girvi_models, name),
                f"apps.tenant_apps.girvi.models must not export deprecated {name}; "
                "use models.legacy only for explicit compatibility surfaces.",
            )

    def test_runtime_code_does_not_import_legacy_models_from_broad_namespace(self):
        violations = []
        for path in GIRVI_ROOT.rglob("*.py"):
            if _is_excluded(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = _absolute_import_module(path, node)
                if module != "apps.tenant_apps.girvi.models":
                    continue
                imported = {alias.name for alias in node.names}
                forbidden = imported & FORBIDDEN_MODEL_NAMES
                if forbidden:
                    violations.append(
                        f"{path.relative_to(GIRVI_ROOT)} imports {sorted(forbidden)} "
                        "from apps.tenant_apps.girvi.models"
                    )

        self.assertEqual(
            violations,
            [],
            "Deprecated legacy model imports must go through "
            "apps.tenant_apps.girvi.models.legacy.",
        )

    def test_legacy_loan_payment_resource_is_explicitly_named(self):
        self.assertIs(
            girvi_resources.LoanPaymentResource,
            girvi_resources.LegacyLoanPaymentResource,
        )
        self.assertIs(
            girvi_resources.LegacyLoanPaymentResource.Meta.model,
            legacy_models.LoanPayment,
        )
        self.assertIs(
            girvi_resources.LegacyLoanPaymentResource.fields["loan"].widget.model,
            legacy_models.Loan,
        )

    def test_direct_legacy_module_imports_are_restricted_to_compat_surfaces(self):
        violations = []
        for path in GIRVI_ROOT.rglob("*.py"):
            if _is_excluded(path):
                continue
            rel_path = str(path.relative_to(GIRVI_ROOT)).replace("\\", "/")
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = _absolute_import_module(path, node)
                if module not in {
                    "apps.tenant_apps.girvi.models.loan",
                    "apps.tenant_apps.girvi.models.legacy",
                }:
                    continue
                if rel_path not in {
                    "models/__init__.py",
                    "models/loan_refactored.py",
                    "resources.py",
                    "management/commands/missingcol.py",
                }:
                    violations.append(
                        f"{rel_path} directly imports from {module}; use package-level models imports or explicit compat seams"
                    )

        self.assertEqual(
            violations,
            [],
            "Direct imports from legacy modules loan.py/legacy.py must stay limited to explicit compatibility files.",
        )

    def test_notify_and_contact_model_imports_are_blocked_in_boundary_modules(self):
        guarded_files = {
            "selectors.py",
            "views/loan.py",
            "views/notice.py",
            "views/prints.py",
            "transitions/commands.py",
        }
        forbidden_modules = {
            "apps.tenant_apps.notify.models",
            "apps.tenant_apps.notify.services",
            "apps.tenant_apps.notify_v2.models",
            "apps.tenant_apps.notify_v2.services",
            "apps.tenant_apps.contact.models",
        }

        violations = []
        for rel_path in guarded_files:
            path = GIRVI_ROOT / rel_path
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = _absolute_import_module(path, node)
                    if module in forbidden_modules:
                        violations.append(f"{rel_path} imports from {module}")

                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in forbidden_modules:
                            violations.append(f"{rel_path} imports {alias.name}")

        self.assertEqual(
            violations,
            [],
            "Boundary modules must use Girvi integration/facade adapters instead of direct notify/contact model imports.",
        )

    def test_runtime_dea_imports_are_limited_to_accounting_adapter_boundary(self):
        allowed_paths = {
            "integrations/dea_adapter.py",
            "service_modules/posting_adapter.py",
        }
        violations = []

        for path in GIRVI_ROOT.rglob("*.py"):
            if _is_excluded(path):
                continue
            rel_path = str(path.relative_to(GIRVI_ROOT)).replace("\\", "/")
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = _absolute_import_module(path, node) or ""
                    if module.startswith("apps.tenant_apps.dea") and rel_path not in allowed_paths:
                        violations.append(f"{rel_path} imports from {module}")

                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("apps.tenant_apps.dea") and rel_path not in allowed_paths:
                            violations.append(f"{rel_path} imports {alias.name}")

        self.assertEqual(
            violations,
            [],
            "Runtime Girvi code must use integrations.dea_adapter for DEA access.",
        )

    def test_legacy_model_imports_in_management_commands_are_limited_to_missingcol(self):
        commands_root = GIRVI_ROOT / "management" / "commands"
        violations = []

        for path in commands_root.glob("*.py"):
            if path.name in {"__init__.py", "missingcol.py"}:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                module = _absolute_import_module(path, node)
                if module in {
                    "apps.tenant_apps.girvi.models.loan",
                    "apps.tenant_apps.girvi.models.legacy",
                }:
                    violations.append(
                        f"management/commands/{path.name} imports from {module}"
                    )

        self.assertEqual(
            violations,
            [],
            "Only missingcol.py may import deprecated legacy loan models in command surfaces.",
        )

    def test_runtime_modules_do_not_import_legacy_manual_commands(self):
        forbidden_modules = {
            "apps.tenant_apps.girvi.management.commands.do",
            "apps.tenant_apps.girvi.management.commands.missingcol",
        }
        violations = []

        for path in GIRVI_ROOT.rglob("*.py"):
            if _is_excluded(path):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    module = _absolute_import_module(path, node)
                    if module in forbidden_modules:
                        violations.append(
                            f"{path.relative_to(GIRVI_ROOT)} imports from {module}"
                        )

                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in forbidden_modules:
                            violations.append(
                                f"{path.relative_to(GIRVI_ROOT)} imports {alias.name}"
                            )

        self.assertEqual(
            violations,
            [],
            "Legacy manual commands do/missingcol must not be imported by runtime modules.",
        )


def _is_excluded(path):
    parts = set(path.relative_to(GIRVI_ROOT).parts)
    if "migrations" in parts or "tests" in parts or "__pycache__" in parts:
        return True
    return path.name == "loan.py" or path.name == "legacy.py"


def _absolute_import_module(path, node):
    if node.level == 0:
        return node.module

    package_parts = ["apps", "tenant_apps", "girvi", *path.relative_to(GIRVI_ROOT).parts[:-1]]
    if node.level > 1:
        package_parts = package_parts[: -(node.level - 1)]
    if node.module:
        package_parts.extend(node.module.split("."))
    return ".".join(package_parts)
