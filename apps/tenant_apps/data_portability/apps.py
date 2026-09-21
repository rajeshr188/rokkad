from django.apps import AppConfig


class DataPortabilityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant_apps.data_portability"
    verbose_name = "Party data portability"
