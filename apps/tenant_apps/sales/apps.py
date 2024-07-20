from django.apps import AppConfig


class SalesConfig(AppConfig):
    name = "apps.tenant_apps.sales"

    def ready(self):
        from . import signals
