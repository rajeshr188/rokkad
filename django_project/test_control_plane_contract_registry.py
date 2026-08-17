import importlib
import re
import unittest
from pathlib import Path

from django.test import SimpleTestCase

from django_project.control_plane_contract_registry import CONTRACT_TEST_MODULES


CONTRACTS_DOCUMENT = Path("docs/architecture/control-plane-contracts.md")
CONTRACT_ID_PATTERN = re.compile(r"CP-[A-Z]+-[0-9]{3}")


class ControlPlaneContractRegistryTests(SimpleTestCase):
    def test_registry_exactly_covers_accepted_contract_ids(self):
        documented_ids = set(
            CONTRACT_ID_PATTERN.findall(
                CONTRACTS_DOCUMENT.read_text(encoding="utf-8")
            )
        )

        self.assertEqual(set(CONTRACT_TEST_MODULES), documented_ids)

    def test_every_registered_module_contains_executable_tests(self):
        loader = unittest.TestLoader()

        for contract_id, module_names in CONTRACT_TEST_MODULES.items():
            self.assertTrue(module_names, f"{contract_id} has no test evidence")
            for module_name in module_names:
                with self.subTest(contract_id=contract_id, module=module_name):
                    module = importlib.import_module(module_name)
                    suite = loader.loadTestsFromModule(module)
                    self.assertGreater(suite.countTestCases(), 0)
