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
