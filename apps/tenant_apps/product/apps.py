from django.apps import AppConfig


class ProductConfig(AppConfig):
    name = "apps.tenant_apps.product"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        import apps.tenant_apps.product.signals
