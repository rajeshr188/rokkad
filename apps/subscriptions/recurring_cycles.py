"""Verify recurring invoices/payments, then atomically record exactly one paid period."""
from calendar import monthrange
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from .billing import transition_subscription
from .checkout import require_billing_owner
from .models import (BillingAccount, Invoice, Payment, RecurringAgreement, RecurringAgreementEvent,
                     RecurringCycle, Subscription, SubscriptionEvent)
from .notifications import send_checkout_receipt
from .razorpay_service import RazorpayService
from .recurring import (_identity, _verify_plan, recurring_provider_mode, verify_agreement,
                        verify_agreement_observation)
from .services import (build_billing_account_defaults, ensure_entitlements_for_subscription,
                       get_workspace_member_usage)


def _timestamp(value):
    if type(value) is not int or value <= 0:
        raise ValidationError("Provider billing dates must be explicit timestamps.")
    try:
        return datetime.fromtimestamp(value, tz=dt_timezone.utc)
    except (ValueError, OverflowError, OSError) as exc:
        raise ValidationError("Invalid provider billing date.") from exc


def _agreement(subscription_id):
    mode = recurring_provider_mode()
    agreement = RecurringAgreement.objects.select_related("binding", "workspace").filter(
        provider_subscription_id=_identity(subscription_id, "sub_"), binding__mode=mode, state="verified").first()
    if not agreement:
        raise ValidationError("A verified local agreement in this provider mode is required.")
    return agreement


def _valid_period(start, end, cycle):
    minimum, maximum = (28, 31) if cycle == "monthly" else (365, 366)
    duration = end - start
    if timedelta(days=minimum) <= duration <= timedelta(days=maximum):
        return True
    # Observed INR annual invoices end at midnight IST on the anniversary,
    # while initial authorization can occur later in the day. Validate that
    # exact boundary; do not admit an arbitrary one-day-short annual period.
    if cycle != "yearly" or not timedelta(days=364) < duration < timedelta(days=365):
        return False
    local_start = start.astimezone(ZoneInfo("Asia/Kolkata"))
    if local_start.year == 9999:
        return False
    year = local_start.year + 1
    day = min(local_start.day, monthrange(year, local_start.month)[1])
    anniversary = local_start.replace(year=year, day=day, hour=0, minute=0, second=0, microsecond=0)
    return end == anniversary


def _facts(agreement, invoice_id, *, payment_id=None):
    provider_invoice = RazorpayService.get_invoice(_identity(invoice_id, "inv_"))
    if (not isinstance(provider_invoice, dict) or provider_invoice.get("id") != invoice_id or
            provider_invoice.get("subscription_id") != agreement.provider_subscription_id):
        raise ValidationError("Provider invoice does not belong to this agreement.")
    if provider_invoice.get("status") != "paid":
        raise ValidationError("Razorpay has not marked this invoice as paid. Already-paid access is unchanged.")
    actual_payment_id = _identity(provider_invoice.get("payment_id"), "pay_")
    if payment_id is not None and payment_id != actual_payment_id:
        raise ValidationError("Payment does not match the recurring invoice.")
    payment = RazorpayService.get_payment_status(actual_payment_id)
    provider_agreement = RazorpayService.get_subscription(agreement.provider_subscription_id)
    verify_agreement(agreement, provider_agreement)
    _verify_plan(RazorpayService.get_plan(agreement.binding.provider_plan_id),
                 agreement.binding.provider_plan_id, agreement.binding.snapshot)
    snapshot = agreement.binding.snapshot
    order_id = _identity(provider_invoice.get("order_id"), "order_")
    if (provider_invoice.get("entity") != "invoice" or provider_invoice.get("status") != "paid" or
            provider_invoice.get("currency") != snapshot["currency"] or
            any(type(provider_invoice.get(k)) is not int or provider_invoice[k] != v
                for k, v in {"amount": snapshot["amount"], "amount_paid": snapshot["amount"], "amount_due": 0}.items()) or
            not isinstance(payment, dict) or payment.get("entity") != "payment" or payment.get("id") != actual_payment_id or
            payment.get("invoice_id") != invoice_id or payment.get("order_id") != order_id or
            payment.get("currency") != snapshot["currency"] or type(payment.get("amount")) is not int or
            payment["amount"] != snapshot["amount"] or payment.get("status") not in {"captured", "refunded"} or
            type(payment.get("amount_refunded")) is not int or not 0 <= payment["amount_refunded"] <= snapshot["amount"]):
        raise ValidationError("A fully paid matching invoice and captured payment are required.")
    lines = provider_invoice.get("line_items")
    if (not isinstance(lines, list) or len(lines) != 1 or not isinstance(lines[0], dict) or
            lines[0].get("type") != "plan" or type(lines[0].get("quantity")) is not int or lines[0]["quantity"] != 1 or
            type(lines[0].get("amount")) is not int or lines[0]["amount"] != snapshot["amount"] or
            lines[0].get("currency") != snapshot["currency"]):
        raise ValidationError("The invoice must contain exactly the frozen plan, without add-ons.")
    start, end = _timestamp(provider_invoice.get("billing_start")), _timestamp(provider_invoice.get("billing_end"))
    paid_at = _timestamp(provider_invoice.get("paid_at"))
    now = timezone.now()
    if (not _valid_period(start, end, snapshot["billing_cycle"]) or
            int(start.timestamp()) < agreement.request_snapshot.get("start_at", 0) or
            int(start.timestamp()) < int(agreement.created_at.timestamp()) or paid_at > now):
        raise ValidationError("The invoice needs a valid monthly/yearly billing period and a payment timestamp that is not in the future.")
    evidence = {"subscription_id": agreement.provider_subscription_id, "invoice_id": invoice_id,
                "payment_id": actual_payment_id, "order_id": order_id, "amount": snapshot["amount"],
                "currency": snapshot["currency"], "billing_start": int(start.timestamp()),
                "billing_end": int(end.timestamp()), "paid_at": int(paid_at.timestamp())}
    return evidence, payment, start, end, paid_at


def record_paid_cycle(*, agreement_id, provider_invoice_id, payment_id=None, actor=None, workspace=None, reason="Provider paid cycle"):
    """Trusted webhook entry; owner recovery must supply explicit actor/Workspace."""
    initial = RecurringAgreement.objects.select_related("binding").get(pk=agreement_id)
    agreement = _agreement(initial.provider_subscription_id)
    if actor is not None:
        require_billing_owner(workspace=workspace, actor=actor)
        if not actor.is_active or workspace.pk != agreement.workspace_id:
            raise PermissionDenied("Recurring recovery requires this Workspace's active billing owner.")
    evidence, payment, start, end, paid_at = _facts(agreement, provider_invoice_id, payment_id=payment_id)
    with transaction.atomic():
        company = Company.all_objects.select_for_update().get(pk=agreement.workspace_id)
        if actor is not None:
            require_billing_owner(workspace=company, actor=actor)
        agreement = RecurringAgreement.objects.select_for_update().select_related("binding").get(pk=agreement.pk)
        existing = RecurringCycle.objects.filter(provider_invoice_id=provider_invoice_id).first()
        if existing:
            if existing.agreement_id != agreement.pk or existing.evidence != evidence:
                raise ValidationError("Recurring invoice identity conflicts with saved evidence.")
            return existing  # No reactivation, new receipt or date change on replay, including after a refund.
        if payment["status"] != "captured" or payment["amount_refunded"]:
            raise ValidationError("An unrecorded refunded cycle needs financial review before granting access.")
        if agreement.cycles.filter(period_start__lt=end, period_end__gt=start).exists():
            raise ValidationError("Another invoice already covers this agreement's billing period.")
        if agreement.cycles.count() >= agreement.request_snapshot["total_count"]:
            raise ValidationError("The agreement's cycle count is exhausted.")
        if Payment.objects.filter(razorpay_payment_id=evidence["payment_id"]).exists():
            raise ValidationError("Payment is already linked to a different invoice.")
        snapshot = agreement.binding.snapshot
        subscription, created = Subscription.objects.get_or_create(company=company, defaults={
            "plan_id": snapshot["plan_id"], "status": "past_due", "auto_renew": False})
        subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
        previous_end = None if created else subscription.end_date
        previous_cycle = RecurringCycle.objects.filter(invoice__subscription=subscription).exclude(
            access_action="review", access_resolution__isnull=True).order_by("-period_end").first()
        has_paid_evidence = Invoice.objects.filter(subscription=subscription, status="paid").exclude(
            recurring_cycle__access_action="review", recurring_cycle__access_resolution__isnull=True).exists()
        action = "retained"
        future_period = start > timezone.now()
        current = RecurringAgreement.objects.filter(workspace=company, closed_at__isnull=True).first()
        release = RecurringAgreementEvent.objects.filter(agreement__workspace=company,
            agreement__closed_at__isnull=False, event_type="reservation.released").order_by("-pk").first()
        replacement = bool(release and subscription.status == "cancelled" and
            release.detail.get("revision") == subscription.updated_at.isoformat() and
            agreement.created_at >= release.created_at and not agreement.cycles.exists() and
            not Invoice.objects.filter(subscription=subscription, status="paid").exclude(
                recurring_cycle__agreement__closed_at__isnull=False, payment__status="refunded",
                billing_resolution__action__in=["end_access", "retain_access"]).exists())
        # A trial's model-default end_date is not paid time. Its first due capture
        # can adopt the agreed paid plan only after natural trial expiry, with no
        # previous financial history or overlapping mandate to reinterpret.
        trial_pending = not created and subscription.status == "trial"
        trial_conversion = bool(trial_pending and subscription.trial_end_date and
            subscription.trial_end_date <= agreement.created_at and
            subscription.trial_end_date <= start <= timezone.now() < end and
            company.lifecycle_state == Company.LifecycleState.ACTIVE and
            not subscription.razorpay_subscription_id and
            not Invoice.objects.filter(subscription=subscription).exists() and
            not RecurringCycle.objects.filter(agreement__workspace=company).exists() and
            get_workspace_member_usage(workspace=company, include_pending_invitations=True) <= int(next(
                item["value"] for item in snapshot["entitlements"] if item["feature_code"] == "workspace.max_members")))
        trial_evidence = ({"previous_plan_id": subscription.plan_id,
                           "previous_end_date": subscription.end_date.isoformat(),
                           "trial_end_date": subscription.trial_end_date.isoformat()}
                          if trial_conversion else None)
        if (future_period or not current or current.pk != agreement.pk or
                company.lifecycle_state in {Company.LifecycleState.ARCHIVED, Company.LifecycleState.DELETION_PENDING} or
                (trial_pending and not trial_conversion) or
                (not created and not replacement and not trial_conversion and subscription.plan_id != snapshot["plan_id"]) or
                (not created and not replacement and not previous_cycle and (
                    ((subscription.status == "active" or has_paid_evidence) and previous_end > start) or
                    (subscription.status == "trial" and subscription.trial_end_date and subscription.trial_end_date > start)))):
            action = "review"
        elif (trial_conversion or replacement or created or (not has_paid_evidence and subscription.status == "past_due") or end > previous_end):
            # Use the verified period, never now + a duration or the mutable agreement.current_end.
            subscription.plan_id = snapshot["plan_id"]
            subscription.end_date = max(end, previous_end) if has_paid_evidence and previous_end and not replacement else end
            subscription.save(update_fields=["plan", "end_date", "updated_at"])
            subscription, _ = transition_subscription(subscription=subscription, target_status="active",
                event_type="recurring.payment", payload={"provider_invoice_id": provider_invoice_id,
                    **({"trial_conversion": trial_evidence} if trial_conversion else {})})
            ensure_entitlements_for_subscription(subscription, projection=snapshot["entitlements"])
            action = "applied"
        if created and action == "review":
            # Financial parent only: do not retain the model's default future term.
            subscription.end_date = paid_at
            subscription.save(update_fields=["end_date", "updated_at"])
        account_defaults = build_billing_account_defaults(subscription)
        account_defaults.pop("company")
        account, _ = BillingAccount.objects.get_or_create(company=company, defaults=account_defaults)
        frozen = {**snapshot, "kind": "recurring", "workspace_id": company.pk, "agreement_id": agreement.pk,
                  "provider_invoice_id": provider_invoice_id, "contact_name": account.contact_name or company.name,
                  "billing_email": account.billing_email or "", "period_start": start.isoformat(), "period_end": end.isoformat()}
        if future_period:
            frozen["access_review_reason"] = "future_period"
        invoice = Invoice.objects.create(subscription=subscription, invoice_number=f"RCY-{provider_invoice_id}",
            checkout_snapshot=frozen, base_amount=Decimal(snapshot["base_amount"]), gst_rate=Decimal(snapshot["tax_rate"]),
            invoice_date=timezone.localdate(paid_at), due_date=timezone.localdate(paid_at), paid_at=paid_at, status="paid",
            razorpay_order_id=evidence["order_id"], razorpay_payment_id=evidence["payment_id"])
        if int(invoice.total_amount * 100) != evidence["amount"]:
            raise ValidationError("Local invoice arithmetic differs from the frozen provider price.")
        Payment.objects.create(invoice=invoice, razorpay_payment_id=evidence["payment_id"],
            razorpay_order_id=evidence["order_id"], amount=invoice.total_amount, status="captured", payment_date=paid_at,
            payment_method=payment.get("method") or "")
        cycle = RecurringCycle.objects.create(agreement=agreement, invoice=invoice, provider_invoice_id=provider_invoice_id,
            period_start=start, period_end=end, evidence=evidence, access_action=action)
        SubscriptionEvent.objects.create(subscription=subscription, event_type="recurring.cycle_paid", payload={
            "cycle_id": cycle.pk, "invoice_id": invoice.pk, "agreement_id": agreement.pk, "plan_id": snapshot["plan_id"],
            "period_start": start.isoformat(), "period_end": end.isoformat(), "access_action": action,
            "actor_id": getattr(actor, "pk", None), "reason": reason})
        RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor, event_type="cycle.paid",
            detail={"cycle_id": cycle.pk, "access_action": action, "reason": reason})
        send_checkout_receipt(invoice.pk)
        return cycle


def reconcile_cycle(*, workspace, actor, agreement_id, provider_invoice_id, reason):
    require_billing_owner(workspace=workspace, actor=actor)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A reconciliation reason of up to 1000 characters is required.")
    if not RecurringAgreement.objects.filter(pk=agreement_id, workspace=workspace).exists():
        raise ValidationError("No matching Workspace agreement exists.")
    with transaction.atomic():
        cycle = record_paid_cycle(agreement_id=agreement_id, provider_invoice_id=provider_invoice_id,
                                  actor=actor, workspace=workspace, reason=reason.strip())
        RecurringAgreementEvent.objects.create(agreement_id=agreement_id, actor=actor, event_type="cycle.reconciled",
            detail={"cycle_id": cycle.pk, "reason": reason.strip()})
        return cycle


def handle_subscription_event(data):
    event = data.get("event")
    if event not in {"subscription.charged", "subscription.authenticated", "subscription.activated",
                     "subscription.pending", "subscription.halted", "subscription.cancelled",
                     "subscription.completed", "subscription.paused", "subscription.resumed", "subscription.updated"}:
        return False
    entity = data.get("payload", {}).get("subscription", {}).get("entity", {})
    agreement = _agreement(entity.get("id"))
    if event == "subscription.charged":
        hint = data.get("payload", {}).get("payment", {}).get("entity", {})
        payment_id = _identity(hint.get("id"), "pay_")
        payment = RazorpayService.get_payment_status(payment_id)
        if not isinstance(payment, dict) or payment.get("id") != payment_id:
            raise ValidationError("Provider payment identity does not match.")
        record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id=payment.get("invoice_id"), payment_id=payment_id)
        return True
    provider = RazorpayService.get_subscription(agreement.provider_subscription_id)
    verify_agreement(agreement, provider)
    with transaction.atomic():
        Company.all_objects.select_for_update().get(pk=agreement.workspace_id)
        agreement = RecurringAgreement.objects.select_for_update().get(pk=agreement.pk)
        verify_agreement_observation(agreement, provider)
        if not agreement.closed_at:
            agreement.provider_status, agreement.verified_at = provider["status"], timezone.now()
            agreement.save(update_fields=["provider_status", "verified_at"])
        RecurringAgreementEvent.objects.create(agreement=agreement, event_type="provider.observed",
            detail={"event": event, "provider_status": provider["status"]})
    return True  # Authorization, failure and cancellation do not alter purchased time.


def handle_recurring_capture(payment_hint):
    payment_id = _identity(payment_hint.get("id"), "pay_")
    invoice_id = _identity(payment_hint.get("invoice_id"), "inv_")
    invoice = RazorpayService.get_invoice(invoice_id)
    if not isinstance(invoice, dict) or invoice.get("id") != invoice_id:
        raise ValidationError("Provider invoice identity does not match.")
    agreement = _agreement(invoice.get("subscription_id"))
    record_paid_cycle(agreement_id=agreement.pk, provider_invoice_id=invoice_id, payment_id=payment_id)
    return True
