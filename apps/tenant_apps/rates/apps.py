from django.apps import AppConfig


class RatesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant_apps.rates"

    def ready(self):
        import apps.tenant_apps.rates.signals  # noqa
