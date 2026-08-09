from django.apps import AppConfig


class AccountingConfig(AppConfig):
    """Tenant-app config for the side-by-side accounting successor."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tenant_apps.accounting"
    label = "standalone_accounting"
    verbose_name = "Standalone Accounting"
