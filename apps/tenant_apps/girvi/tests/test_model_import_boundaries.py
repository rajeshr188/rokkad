import ast
from pathlib import Path

from django.test import SimpleTestCase


GIRVI_ROOT = Path(__file__).resolve().parents[1]


def _python_files():
    for path in GIRVI_ROOT.rglob("*.py"):
        if "migrations" in path.parts or "tests" in path.parts:
            continue
        yield path


def _imports_for(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


class GirviModelImportBoundaryTests(SimpleTestCase):
    def test_runtime_does_not_reference_transitional_loan_module(self):
        violations = []
        for path in _python_files():
            for import_name in _imports_for(path):
                if "loan_refactored" in import_name:
                    violations.append(f"{path.relative_to(GIRVI_ROOT)}: {import_name}")

        self.assertEqual(violations, [])

    def test_runtime_does_not_reference_legacy_loan_module(self):
        violations = []
        for path in _python_files():
            relative_path = path.relative_to(GIRVI_ROOT)
            for import_name in _imports_for(path):
                if import_name.endswith("legacy_loan"):
                    violations.append(f"{relative_path}: {import_name}")

        self.assertEqual(violations, [])
