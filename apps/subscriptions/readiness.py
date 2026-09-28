"""Sanitized configuration diagnostics; never provider or launch acceptance."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Count, Q

from .provider_configuration import provider_mode


def assess_billing_configuration():
    raw_mode = getattr(settings, "BILLING_PROVIDER_MODE", "disabled")
    mode = raw_mode if raw_mode in {"disabled", "test", "live"} else "invalid"
    blockers = []
    try:
        provider_mode()
    except ValidationError as exc:
        blockers.extend(exc.messages)
    if not getattr(settings, "RAZORPAY_WEBHOOK_SECRET", ""):
        blockers.append("A mode-specific Razorpay webhook secret is missing.")
    from apps.platform_mail.readiness import assess_platform_mail
    return {"provider_mode": mode, "configuration_ready": not blockers,
        "checkout_enabled": settings.BILLING_CHECKOUT_ENABLED,
        "recurring_authorization_enabled": settings.BILLING_RECURRING_ENABLED,
        "live_recurring_supported": True, "launch_ready": False,
        "blockers": blockers, "receipts": assess_platform_mail(),
        "unverified": ["Provider acceptance and account/method eligibility",
            "Mode-isolated database and reviewed legacy evidence",
            "Signed HTTPS callbacks, recovery monitoring and rollback",
            "Actual receipt delivery and worker/feedback readiness",
            "Final commercial terms and approved activation"]}


def billing_evidence_inventory():
    from .models import Invoice, ProviderWebhookEvent, RecurringAgreement, RecurringPlanBinding
    from apps.platform_mail.models import Delivery
    mode = getattr(settings, "BILLING_PROVIDER_MODE", "disabled")
    bindings = dict(RecurringPlanBinding.objects.values_list("mode").annotate(count=Count("pk")))
    one_off = Invoice.objects.filter(Q(checkout_snapshot__kind__isnull=True) | ~Q(checkout_snapshot__kind="recurring"))
    # PostgreSQL JSON missing keys must be included explicitly, not lost to SQL NULL.
    classified = {value: one_off.filter(checkout_snapshot__provider_mode=value).count() for value in ("test", "live")}
    unclassified = one_off.count() - sum(classified.values())
    blockers = []
    if any(value != mode and count for value, count in bindings.items()) or any(
            value != mode and count for value, count in classified.items()):
        blockers.append("Stored payment evidence belongs to another provider mode. Do not switch this database in place.")
    if unclassified:
        blockers.append("Historical one-off invoices have no verified mode; review before any live migration.")
    return {"recurring_bindings_by_mode": bindings, "one_off_invoices_by_mode": classified,
        "unclassified_one_off_invoices": unclassified,
        "open_agreements": RecurringAgreement.objects.filter(closed_at__isnull=True).count(),
        "unresolved_creation_attempts": RecurringAgreement.objects.exclude(state="verified").count(),
        "webhook_events_needing_review": ProviderWebhookEvent.objects.exclude(status="processed").count(),
        "receipts_by_status": dict(Delivery.objects.filter(invoice__isnull=False).values_list("status").annotate(count=Count("pk"))),
        "blockers": blockers}
