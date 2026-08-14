from django.test import SimpleTestCase

from apps.tenant_apps.utils.importing.forms import _tenant_model_choices, tenant_app_configs
from apps.tenant_apps.utils.importing.views import _find_tenant_model


class TenantImportRegistryTests(SimpleTestCase):
    def test_app_config_class_entries_resolve_to_installed_labels(self):
        configs = {config.label: config for config in tenant_app_configs()}
        self.assertEqual(configs["loans"].name, "apps.tenant_apps.loans")
        self.assertEqual(configs["standalone_accounting"].name, "apps.tenant_apps.accounting")

    def test_model_choices_and_lookup_accept_app_config_class_settings(self):
        choices = dict(_tenant_model_choices())
        model, app_path = _find_tenant_model("PawnLoan")
        self.assertIn("PawnLoan", choices)
        self.assertEqual(model._meta.app_label, "loans")
        self.assertEqual(app_path, "apps.tenant_apps.loans")
