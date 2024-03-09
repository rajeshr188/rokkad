from django.apps import AppConfig


class ContactConfig(AppConfig):
    name = "apps.tenant_apps.contact"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from actstream import registry

        import apps.tenant_apps.contact.signals

        registry.register(self.get_model("Customer"))
        registry.register(self.get_model("Contact"))
        registry.register(self.get_model("Address"))
