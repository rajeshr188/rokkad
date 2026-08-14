from django.apps import AppConfig
from dynamic_preferences.registries import preference_models

from .registries import workspace_preferences_registry


class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.configuration"
    verbose_name = "Configuration"

    def ready(self):
        WorkspacePreferenceModel = self.get_model("WorkspacePreferenceModel")
        preference_models.register(
            WorkspacePreferenceModel,
            workspace_preferences_registry,
        )
