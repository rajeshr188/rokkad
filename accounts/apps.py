from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "accounts"

    def ready(self):
        # from actstream import registry
        import accounts.signals

        # registry.register(self.get_model("CustomUser"))
