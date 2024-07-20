from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    name = "apps.tenant_apps.purchase"

    def ready(self):
        import apps.tenant_apps.purchase.signals
