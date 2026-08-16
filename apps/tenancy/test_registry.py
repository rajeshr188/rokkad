from django.test import SimpleTestCase

from .registry import rls_protected_models, workspace_owned_models


class WorkspaceModelRegistryTests(SimpleTestCase):
    def test_registry_accounts_for_every_surviving_business_model(self):
        models = workspace_owned_models()

        self.assertEqual(len(models), 95)
        self.assertEqual(
            {model._meta.app_label for model in models},
            {"party", "loans", "notify_v2", "rates"},
        )
        for model in models:
            with self.subTest(model=model._meta.label):
                field = model._meta.get_field("workspace")
                self.assertFalse(field.null)
                self.assertEqual(field.remote_field.model._meta.label_lower, "orgs.company")

    def test_rls_rollout_registry_covers_every_surviving_model(self):
        labels = {model._meta.label_lower for model in rls_protected_models()}

        self.assertEqual(len(labels), 95)
        self.assertEqual(
            {label.split(".", 1)[0] for label in labels},
            {"loans", "notify_v2", "party", "rates"},
        )
