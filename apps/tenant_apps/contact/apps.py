from django.apps import AppConfig


class ContactConfig(AppConfig):
    name = "apps.tenant_apps.contact"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from . import signals

        # from actstream import registry

        pass

        # registry.register(self.get_model("Customer"))
        # registry.register(self.get_model("Contact"))
        # registry.register(self.get_model("Address"))
