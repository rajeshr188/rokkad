import unittest
from pathlib import Path

from scripts.check_app_boundaries import violations


class ImportBoundaryTests(unittest.TestCase):
    def test_retired_import_spellings_and_literal_dynamic_imports(self):
        for source in (
            "import apps.tenant_apps.dea.facade",
            "from apps.tenant_apps import girvi",
            "from apps.tenant_apps.contact.models import Customer",
            "from django_tenants.utils import schema_context",
            "from importlib import import_module as load; load('apps.tenant_apps.product.models')",
            "import importlib as il; il.import_module('apps.tenant_apps.notify')",
            "__import__('apps.tenant_apps.accounting')",
        ):
            with self.subTest(source=source):
                self.assertTrue(violations(source, Path("pages/views.py")))

    def test_relative_imports_are_resolved(self):
        self.assertTrue(violations("from ..dea import facade", Path("apps/tenant_apps/loans/views.py")))

    def test_current_notify_and_historical_strings_are_not_imports(self):
        source = "from apps.tenant_apps.notify_v2.models import NotificationJob\n# import django_tenants\npermission = 'contact.view'\n"
        self.assertEqual(violations(source, Path("apps/tenant_apps/loans/views.py")), [])

    def test_billing_internals_are_denied_only_in_business_apps(self):
        source = "from apps.subscriptions.checkout import create_checkout"
        self.assertTrue(violations(source, Path("apps/tenant_apps/party/views.py")))
        self.assertEqual(violations(source, Path("apps/orgs/views.py")), [])


if __name__ == "__main__":
    unittest.main()
