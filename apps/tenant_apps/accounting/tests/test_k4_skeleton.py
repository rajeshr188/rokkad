import importlib
from pathlib import Path
from unittest import TestCase

from django_project.settings.base import INSTALLED_APPS, TENANT_APPS

from apps.tenant_apps.accounting.apps import AccountingConfig


class AccountingAppSkeletonTests(TestCase):
    def test_app_config_is_import_safe_and_has_stable_identity(self):
        module = importlib.import_module("apps.tenant_apps.accounting")
        config = AccountingConfig("apps.tenant_apps.accounting", module)

        self.assertEqual(config.name, "apps.tenant_apps.accounting")
        self.assertEqual(config.label, "standalone_accounting")
        self.assertEqual(config.verbose_name, "Standalone Accounting")
        self.assertEqual(config.default_auto_field, "django.db.models.BigAutoField")

    def test_app_is_registered_as_a_tenant_app_for_k5(self):
        config_path = "apps.tenant_apps.accounting.apps.AccountingConfig"

        self.assertIn(config_path, TENANT_APPS)
        self.assertIn(config_path, INSTALLED_APPS)

    def test_k8_runtime_surface_remains_bounded(self):
        package_root = Path(__file__).resolve().parents[1]

        self.assertTrue((package_root / "models.py").exists())
        self.assertTrue((package_root / "migrations" / "0001_initial.py").exists())
        self.assertTrue(
            (
                package_root
                / "migrations"
                / "0002_externalaccount_externalaccountclassification_and_more.py"
            ).exists()
        )
        self.assertTrue(
            (
                package_root
                / "migrations"
                / "0007_openitemallocation_reversal_of_and_more.py"
            ).exists()
        )
        self.assertTrue(
            (
                package_root
                / "migrations"
                / "0006_openitem_openitemallocation_and_more.py"
            ).exists()
        )
        self.assertTrue(
            (
                package_root
                / "migrations"
                / "0003_voucher_accountingtransaction_accounttransaction_and_more.py"
            ).exists()
        )
        self.assertTrue(
            (package_root / "migrations" / "0004_transactionbatch_and_more.py").exists()
        )
        self.assertTrue(
            (
                package_root
                / "migrations"
                / "0005_transactionbatch_reversal_reason_and_more.py"
            ).exists()
        )
        self.assertTrue((package_root / "urls.py").exists())
        self.assertTrue((package_root / "views.py").exists())
        self.assertFalse((package_root / "admin.py").exists())

    def test_domain_contracts_import_without_django_setup(self):
        domain = importlib.import_module("apps.tenant_apps.accounting.domain")

        self.assertTrue(hasattr(domain, "TransactionBatch"))
        self.assertTrue(hasattr(domain, "post_voucher"))
