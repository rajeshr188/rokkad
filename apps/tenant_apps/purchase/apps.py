from django.apps import AppConfig


class PurchaseConfig(AppConfig):
    name = "apps.tenant_apps.purchase"

    def ready(self):
        from . import signals
