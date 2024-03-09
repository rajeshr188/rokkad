from django.apps import AppConfig
from django.conf import settings
from dynamic_preferences.registries import preference_models

from .registries import company_preference_registry


class OrgsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orgs"

    def ready(self):
        import apps.orgs.signals  # noqa

        CompanyPreferenceModel = self.get_model("CompanyPreferenceModel")
        preference_models.register(CompanyPreferenceModel, company_preference_registry)
