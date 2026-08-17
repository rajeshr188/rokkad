import re
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from django_project.control_plane_contract_registry import (
    CONTRACT_COVERAGE_GAPS,
    CONTRACT_TEST_LABELS,
)

CONTRACTS_DOCUMENT = Path("docs/architecture/control-plane-contracts.md")
CONTRACT_ID_PATTERN = re.compile(r"CP-[A-Z]+-[0-9]{3}")


def _flatten(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from _flatten(test)
        else:
            yield test


class ControlPlaneContractRegistryTests(SimpleTestCase):
    def test_registry_exactly_covers_accepted_contract_ids(self):
        documented_ids = set(
            CONTRACT_ID_PATTERN.findall(
                CONTRACTS_DOCUMENT.read_text(encoding="utf-8")
            )
        )
        self.assertEqual(set(CONTRACT_TEST_LABELS), documented_ids)
        self.assertLessEqual(set(CONTRACT_COVERAGE_GAPS), documented_ids)

    def test_every_registered_label_resolves_to_one_executable_test(self):
        loader = unittest.TestLoader()
        for contract_id, labels in CONTRACT_TEST_LABELS.items():
            self.assertTrue(labels, f"{contract_id} has no test evidence")
            for label in labels:
                with self.subTest(contract_id=contract_id, label=label):
                    tests = tuple(_flatten(loader.loadTestsFromName(label)))
                    self.assertEqual(len(tests), 1)
                    self.assertNotEqual(tests[0].__class__.__name__, "_FailedTest")
                    self.assertEqual(tests[0].id(), label)

    def test_only_workspace_context_primitive_sets_postgres_workspace_id(self):
        allowed = Path("apps/tenancy/context.py")
        setters = ("set_config('app.workspace_id'", 'set_config("app.workspace_id"')
        violations = []
        for root in (Path("apps"), Path("django_project"), Path("pages"), Path("scripts")):
            for path in root.rglob("*.py"):
                normalized = path.as_posix()
                if path == allowed or "/migrations/" in normalized or "test" in path.name:
                    continue
                source = path.read_text(encoding="utf-8")
                if any(setter in source for setter in setters):
                    violations.append(normalized)
        self.assertEqual(violations, [])

    def test_business_apps_do_not_import_subscription_or_provider_state(self):
        forbidden = (
            "apps.subscriptions.models",
            "apps.subscriptions.billing",
            "apps.subscriptions.razorpay_service",
        )
        violations = []
        for app in ("party", "loans", "notify_v2", "rates"):
            root = Path("apps/tenant_apps") / app
            for path in root.rglob("*.py"):
                normalized = path.as_posix()
                if "/migrations/" in normalized or "test" in path.name:
                    continue
                source = path.read_text(encoding="utf-8")
                if any(module in source for module in forbidden):
                    violations.append(normalized)
        self.assertEqual(violations, [])
