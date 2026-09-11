"""Workspace-bound, one-off purchases. Provider calls never accept browser prices."""

from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from uuid import UUID

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from .billing import effective_billing_state, transition_subscription
from .models import BillingAccount, Invoice, Payment, Plan, Subscription, SubscriptionEvent
from .razorpay_service import BillingProviderError, RazorpayService
from .services import build_billing_account_defaults, build_entitlement_defaults, ensure_entitlements_for_subscription


def require_billing_owner(*, workspace, actor):
    if workspace is None or current_workspace_id() != workspace.pk:
        raise PermissionDenied("Explicit matching Workspace context required.")
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not (access.platform_override or (access.membership and workspace.owner_id == actor.pk)):
        raise PermissionDenied("Only the Workspace owner can manage billing.")


@transaction.atomic
def create_checkout(*, workspace, actor, plan_id, billing_cycle, request_key):
    require_billing_owner(workspace=workspace, actor=actor)
    workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
    require_billing_owner(workspace=workspace, actor=actor)
    if workspace.lifecycle_state not in (Company.LifecycleState.ACTIVE, Company.LifecycleState.SUSPENDED):
        raise ValidationError("This Workspace cannot start a purchase.")
    try:
        key = UUID(str(request_key))
        plan_id = int(plan_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("A plan and valid checkout key are required.") from exc
    if billing_cycle not in ("monthly", "yearly"):
        raise ValidationError("Choose monthly or yearly billing.")
    existing = Invoice.objects.filter(checkout_key=key).first()
    if existing:
        snapshot = existing.checkout_snapshot
        if (existing.subscription.company_id != workspace.pk or
                snapshot.get("plan_id") != plan_id or snapshot.get("billing_cycle") != billing_cycle):
            raise ValidationError("Checkout key does not match this purchase.")
        if not existing.razorpay_order_id:
            raise ValidationError("This checkout needs payment-provider reconciliation.")
        return existing
    plan = Plan.objects.filter(pk=plan_id, is_active=True).first()
    if plan is None:
        raise ValidationError("Choose an available plan.")
    amount = plan.yearly_price if billing_cycle == "yearly" else plan.price
    if amount is None or amount <= 0:
        raise ValidationError("This plan has no payable price for that cycle.")
    subscription, _ = Subscription.objects.get_or_create(
        company=workspace, defaults={"plan": plan, "status": Subscription.StatusChoices.PAST_DUE, "auto_renew": False},
    )
    subscription = Subscription.objects.select_for_update().get(pk=subscription.pk)
    if (subscription.status == Subscription.StatusChoices.ACTIVE
            and effective_billing_state(subscription).commercially_available
            and subscription.plan_id != plan.pk):
        raise ValidationError("Active plan changes require a billing review; renew the current plan here.")
    defaults = build_billing_account_defaults(subscription)
    defaults.pop("company")
    account, _ = BillingAccount.objects.get_or_create(company=workspace, defaults=defaults)
    tax_rate = Decimal(str(getattr(settings, "BILLING_TAX_RATE", "18")))
    tax = (amount * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    snapshot = {
        "workspace_id": workspace.pk, "plan_id": plan.pk, "plan_name": plan.name,
        "billing_cycle": billing_cycle, "currency": "INR", "amount": int((amount + tax) * 100),
        "subscription_revision": subscription.updated_at.isoformat(),
        "contact_name": account.contact_name or workspace.name,
        "billing_email": account.billing_email or "",
        "entitlements": build_entitlement_defaults(SimpleNamespace(plan=plan)),
    }
    invoice = Invoice.objects.create(
        subscription=subscription, checkout_key=key, checkout_snapshot=snapshot,
        invoice_number=f"CHK-{key.hex}", base_amount=amount, gst_rate=tax_rate,
        invoice_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=7),
    )
    order = RazorpayService.create_order(
        amount=snapshot["amount"], currency="INR", receipt=invoice.invoice_number, workspace_id=workspace.pk,
    )
    if (not isinstance(order, dict) or not isinstance(order.get("id"), str) or not order["id"] or
            len(order["id"]) > 255 or order.get("amount") != snapshot["amount"] or order.get("currency") != "INR"):
        raise BillingProviderError("Payment provider returned an invalid order; contact support before retrying.")
    invoice.razorpay_order_id = order["id"]
    invoice.save(update_fields=["razorpay_order_id", "updated_at"])
    return invoice


def confirm_checkout(*, workspace, actor, order_id, payment_id, signature):
    require_billing_owner(workspace=workspace, actor=actor)
    if not isinstance(order_id, str) or not order_id or len(order_id) > 255:
        raise ValidationError("Provide a valid order ID.")
    invoice = Invoice.objects.filter(subscription__company=workspace, razorpay_order_id=order_id).first() if order_id else None
    if not invoice or not invoice.checkout_snapshot:
        raise ValidationError("No matching checkout exists in this Workspace.")
    if not RazorpayService.verify_payment_signature(invoice.razorpay_order_id, payment_id, signature):
        raise ValidationError("Payment signature verification failed.")
    payment = RazorpayService.get_payment_status(payment_id)
    if not isinstance(payment, dict) or payment.get("id") != payment_id:
        raise ValidationError("Payment identity does not match.")
    return _apply_capture(invoice_id=invoice.pk, payment=payment, actor=actor, workspace=workspace)


@transaction.atomic
def _apply_capture(*, invoice_id, payment, actor=None, workspace=None):
    # Browser and provider callbacks use the same lock order and mutation path.
    initial = Invoice.objects.select_related("subscription").get(pk=invoice_id)
    company = Company.all_objects.select_for_update().get(pk=initial.subscription.company_id)
    if actor is not None:
        require_billing_owner(workspace=company, actor=actor)
        if workspace.pk != company.pk:
            raise PermissionDenied("Checkout Workspace mismatch.")
    invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
    snapshot = invoice.checkout_snapshot
    if (not snapshot or snapshot.get("workspace_id") != company.pk or
            payment.get("order_id") != invoice.razorpay_order_id or
            type(payment.get("amount")) is not int or payment["amount"] != snapshot["amount"] or
            payment.get("currency") != snapshot["currency"] or payment.get("status") != "captured" or
            payment.get("amount_refunded", 0) != 0 or not isinstance(payment.get("id"), str) or
            not payment["id"] or len(payment["id"]) > 255):
        raise ValidationError("Payment must be captured for this exact order, amount and currency.")
    if invoice.status == Invoice.StatusChoices.PAID:
        if not Payment.objects.filter(invoice=invoice, razorpay_payment_id=payment["id"], status__in=("captured", "refunded")).exists():
            raise ValidationError("Invoice has a different payment or needs reconciliation.")
        return invoice
    if invoice.status != Invoice.StatusChoices.ISSUED:
        raise ValidationError("This invoice cannot be paid automatically.")
    subscription = Subscription.objects.select_for_update().get(pk=invoice.subscription_id)
    if subscription.updated_at.isoformat() != snapshot["subscription_revision"]:
        raise ValidationError("Subscription changed after checkout; payment needs reconciliation.")
    if Payment.objects.filter(razorpay_payment_id=payment["id"]).exists():
        raise ValidationError("Payment is already linked to an invoice.")
    now = timezone.now()
    start = max(now, subscription.end_date) if subscription.status == "active" else now
    subscription.plan_id = snapshot["plan_id"]
    subscription.end_date = start + relativedelta(months=12 if snapshot["billing_cycle"] == "yearly" else 1)
    subscription.auto_renew = False  # Orders are one-off purchases, not a recurring mandate.
    subscription.save(update_fields=["plan", "end_date", "auto_renew", "updated_at"])
    subscription, _ = transition_subscription(
        subscription=subscription, target_status=Subscription.StatusChoices.ACTIVE,
        event_type="payment.captured", payload={"invoice_id": invoice.pk, "payment_id": payment["id"]},
    )
    ensure_entitlements_for_subscription(subscription, projection=snapshot["entitlements"])
    Payment.objects.create(
        invoice=invoice, razorpay_payment_id=payment["id"], razorpay_order_id=invoice.razorpay_order_id,
        amount=invoice.total_amount, status="captured", payment_date=now,
    )
    invoice.status = Invoice.StatusChoices.PAID
    invoice.paid_at = now
    invoice.razorpay_payment_id = payment["id"]
    invoice.save(update_fields=["status", "paid_at", "razorpay_payment_id", "updated_at"])
    SubscriptionEvent.objects.create(subscription=subscription, event_type="checkout.completed", payload={
        "invoice_id": invoice.pk, "plan_id": snapshot["plan_id"], "billing_cycle": snapshot["billing_cycle"],
        "period_start": start.isoformat(), "period_end": subscription.end_date.isoformat(),
        "actor_id": getattr(actor, "pk", None),
    })
    from .notifications import send_checkout_receipt
    transaction.on_commit(lambda: send_checkout_receipt(invoice.pk), robust=True)
    return invoice


def handle_provider_event(event_data):
    event_type = event_data.get("event")
    if event_type == "refund.processed":
        from .recovery import process_refund_webhook
        return process_refund_webhook(event_data)
    if event_type in ("payment.authorized", "payment.failed"):
        # Failed attempts never revoke another successful purchase.
        return True
    if event_type != "payment.captured":
        # Persist unsupported events as FAILED for operator review.
        return False
    payment = event_data.get("payload", {}).get("payment", {}).get("entity", {})
    if not isinstance(payment, dict) or not payment.get("order_id"):
        raise ValidationError("Payment entity is missing.")
    invoice = Invoice.objects.filter(razorpay_order_id=payment["order_id"]).first()
    if not invoice:
        raise ValidationError("Payment order needs reconciliation.")
    _apply_capture(invoice_id=invoice.pk, payment=payment)
    return True
