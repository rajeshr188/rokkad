from django.apps import AppConfig


class DeaConfig(AppConfig):
    name = "apps.tenant_apps.dea"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals
