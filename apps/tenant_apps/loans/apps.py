from django.apps import AppConfig


class LoansConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant_apps.loans"
    verbose_name = "Loans"

    def ready(self):
        from . import risk_signals  # noqa: F401
