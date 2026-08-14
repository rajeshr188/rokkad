from django.apps import AppConfig


class ContactConfig(AppConfig):
    name = "apps.tenant_apps.contact"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals  # noqa: F401

        pass
