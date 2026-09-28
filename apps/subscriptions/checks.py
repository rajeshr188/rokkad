from django.core.checks import Warning, register
from .readiness import assess_billing_configuration


@register("billing", deploy=True)
def check_billing_configuration(app_configs, **kwargs):
    report = assess_billing_configuration()
    if (report["checkout_enabled"] or report["recurring_authorization_enabled"]) and not report["configuration_ready"]:
        return [Warning("Enabled billing has incomplete or conflicting provider configuration.",
                        hint="Run check_billing_configuration --include-evidence privately.", id="subscriptions.W001")]
    return []
