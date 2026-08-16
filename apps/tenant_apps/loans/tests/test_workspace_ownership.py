from django.apps import apps
from django.test import SimpleTestCase


class LoansWorkspaceOwnershipRegistryTests(SimpleTestCase):
    def test_every_concrete_loans_model_has_non_null_workspace(self):
        missing = []
        nullable = []

        for model in apps.get_app_config("loans").get_models():
            try:
                field = model._meta.get_field("workspace")
            except Exception:
                missing.append(model.__name__)
                continue
            if field.null:
                nullable.append(model.__name__)

        self.assertEqual(missing, [])
        self.assertEqual(nullable, [])
