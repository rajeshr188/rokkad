from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.onboarding"
    verbose_name = "User Onboarding"

    def ready(self):
        """Import signals when app is ready"""
        try:
            import apps.onboarding.signals  # noqa
        except ImportError:
            pass
