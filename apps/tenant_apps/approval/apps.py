from django.apps import AppConfig


class ApprovalConfig(AppConfig):
    name = "apps.tenant_apps.approval"

    def ready(self):
        from . import signals
