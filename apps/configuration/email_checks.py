from django.core.checks import Warning, register

from .email_readiness import assess_email_configuration


@register("email", deploy=True)
def check_external_email(app_configs, **kwargs):
    report = assess_email_configuration()
    if report["blockers"]:
        return [Warning(
            "Shared Django email configuration needs attention.",
            hint="Run check_email_configuration for shared Django mail and check_platform_mail for the separate invitation/receipt SES path.",
            id="configuration.W001",
        )]
    return []
