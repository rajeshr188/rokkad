from django.apps import AppConfig

class ConfigurationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.configuration"
    verbose_name = "Configuration"

    def ready(self):
        from . import email_checks  # noqa: F401
