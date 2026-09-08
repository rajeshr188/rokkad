from django.contrib.auth import get_user_model
from django.db.models import Max
from django.test import TestCase

from apps.configuration.models import PreferenceAuditLog, WorkspacePreferenceModel
from apps.configuration.services import PreferenceService
from dynamic_preferences.registries import global_preferences_registry

from apps.configuration.registries import workspace_preferences_registry
from apps.orgs.models import Company


class PreferenceServiceTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="owner",
            email="owner@example.com",
            password="pass",
        )
        next_company_id = (Company.all_objects.aggregate(max_id=Max("id"))["max_id"] or 0) + 1
        self.workspace = Company(
            id=next_company_id,
            name="Preference Workspace",
            schema_name="pref_workspace",
            owner=self.user,
            creator=self.user,
        )
        self.workspace.auto_create_schema = False
        self.workspace.save()
        self.other_workspace = Company(
            id=next_company_id + 1,
            name="Other Preference Workspace",
            schema_name="pref_other",
            owner=self.user,
            creator=self.user,
        )
        self.other_workspace.auto_create_schema = False
        self.other_workspace.save()

    def test_workspace_preference_can_be_set_and_read(self):
        PreferenceService.set_workspace(
            self.workspace,
            "accounting__default_currency",
            "USD",
            user=self.user,
        )

        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "accounting__default_currency",
            ),
            "USD",
        )
        self.assertTrue(
            WorkspacePreferenceModel.objects.filter(
                instance=self.workspace,
                section="accounting",
                name="default_currency",
            ).exists()
        )

    def test_workspace_write_invalidates_cached_default(self):
        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "accounting__integration_mode",
            ),
            "DEFERRED",
        )

        PreferenceService.set_workspace(
            self.workspace,
            "accounting__integration_mode",
            "DEA",
            user=self.user,
        )

        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "accounting__integration_mode",
            ),
            "DEA",
        )

    def test_workspace_preferences_are_instance_scoped(self):
        PreferenceService.set_workspace(
            self.workspace,
            "accounting__invoice_prefix",
            "ACME",
            user=self.user,
        )

        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "accounting__invoice_prefix",
            ),
            "ACME",
        )
        self.assertEqual(
            PreferenceService.get_workspace(
                self.other_workspace,
                "accounting__invoice_prefix",
            ),
            "INV",
        )

    def test_workspace_missing_value_falls_back_to_global_default(self):
        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "accounting__default_currency",
            ),
            "INR",
        )

    def test_user_override_applies_only_to_allowlisted_ui_keys(self):
        PreferenceService.set_workspace(
            self.workspace,
            "ui__default_landing_page",
            "workspace",
            user=self.user,
        )
        PreferenceService.set_user(self.user, "ui__default_landing_page", "reports")

        self.assertEqual(
            PreferenceService.get_effective(
                user=self.user,
                workspace=self.workspace,
                key="ui__default_landing_page",
            ),
            "reports",
        )

    def test_user_cannot_override_business_key(self):
        with self.assertRaises(ValueError):
            PreferenceService.set_user(
                self.user,
                "accounting__voucher_prefix",
                "USR",
            )

    def test_business_key_effective_resolution_ignores_user_preference(self):
        PreferenceService.set_workspace(
            self.workspace,
            "accounting__voucher_prefix",
            "WSP",
            user=self.user,
        )

        self.assertEqual(
            PreferenceService.get_effective(
                user=self.user,
                workspace=self.workspace,
                key="accounting__voucher_prefix",
            ),
            "WSP",
        )

    def test_set_workspace_writes_audit_log(self):
        PreferenceService.set_workspace(
            self.workspace,
            "notifications__email_enabled",
            False,
            user=self.user,
        )

        audit = PreferenceAuditLog.objects.get(
            scope=PreferenceAuditLog.Scope.WORKSPACE,
            workspace=self.workspace,
            key="notifications__email_enabled",
        )
        self.assertEqual(audit.changed_by, self.user)
        self.assertEqual(audit.new_value, "False")

    def _get_registry_page_size(self, workspace, *, global_registry=global_preferences_registry):
        return PreferenceService.get_workspace_from_registry(
            workspace=workspace,
            key="ui__default_table_page_size",
            workspace_registry=workspace_preferences_registry,
            workspace_preference_model=WorkspacePreferenceModel,
            global_registry=global_registry,
            default=10,
        )

    def test_registry_resolver_prefers_workspace_override(self):
        PreferenceService.set_workspace(self.workspace, "ui__default_table_page_size", 50)

        self.assertEqual(self._get_registry_page_size(self.workspace), 50)
        self.assertTrue(WorkspacePreferenceModel.objects.filter(
            instance=self.workspace, section="ui", name="default_table_page_size",
        ).exists())

    def test_registry_resolver_uses_global_fallback(self):
        key = "ui__default_table_page_size"
        previous = PreferenceService.get_global(key)
        self.addCleanup(PreferenceService.set_global, key, previous)
        PreferenceService.set_global(key, 75)

        self.assertEqual(self._get_registry_page_size(self.workspace), 75)

    def test_registry_resolver_keeps_workspace_overrides_isolated(self):
        PreferenceService.set_workspace(self.workspace, "ui__default_table_page_size", 50)
        PreferenceService.set_workspace(self.other_workspace, "ui__default_table_page_size", 100)

        self.assertEqual(self._get_registry_page_size(self.workspace), 50)
        self.assertEqual(self._get_registry_page_size(self.other_workspace), 100)

    def test_registry_resolver_uses_code_default_without_global_registry(self):
        self.assertEqual(self._get_registry_page_size(self.workspace, global_registry=None), 10)
