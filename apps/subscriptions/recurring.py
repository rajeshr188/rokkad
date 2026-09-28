"""Mode-specific recurring preparation; mandate state is separate from paid access.

Public commands own their transactions: the attempt MUST commit before provider
creation. Do not call these from middleware's atomic Workspace request context.
"""

from datetime import datetime, timezone as dt_timezone
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from uuid import UUID

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.db import connection, transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.orgs.permissions import is_platform_admin
from apps.tenancy.context import workspace_context
from .checkout import require_billing_owner
from .models import (Invoice, Plan, RecurringAgreement, RecurringAgreementEvent,
                     RecurringPlanBinding, Subscription)
from .razorpay_service import BillingProviderError, RazorpayService
from .services import build_entitlement_defaults, get_workspace_member_usage
from .seller import billing_tax_rate, live_seller


def _test_mode():
    # Test catalog registration retains its explicit preparation switch.
    if not getattr(settings, "BILLING_RECURRING_ENABLED", False):
        raise PermissionDenied("Recurring agreement preparation is disabled.")
    return provider_test_mode()


def provider_test_mode():
    """Keep rehearsal-only operations, such as reservation release, isolated."""
    mode = recurring_provider_mode()
    if mode != "test":
        raise PermissionDenied("This operation requires Test Mode credentials.")
    return mode


def recurring_provider_mode():
    """Recovery uses the configured mode even when new authorization is paused."""
    from .provider_configuration import provider_mode
    try:
        return provider_mode()
    except ValidationError as exc:
        raise PermissionDenied("Recurring billing requires matching configured provider credentials.") from exc


def _creation_mode():
    if not getattr(settings, "BILLING_RECURRING_ENABLED", False):
        raise PermissionDenied("Recurring agreement preparation is disabled.")
    mode = recurring_provider_mode()
    if mode == "live":
        live_seller()
        if not getattr(settings, "RAZORPAY_WEBHOOK_SECRET", "").strip():
            raise PermissionDenied("Configure the live webhook secret before recurring authorization.")
        from .readiness import billing_evidence_inventory
        blockers = billing_evidence_inventory()["blockers"]
        if blockers:
            raise ValidationError(blockers)
    return mode


def _outside_transaction():
    if connection.in_atomic_block or not connection.get_autocommit():
        raise ImproperlyConfigured("Recurring commands must own their transactions; call outside Workspace context.")


def _identity(value, prefix):
    if (not isinstance(value, str) or not value.startswith(prefix) or
            not value[len(prefix):].isalnum() or len(value) > 255):
        raise ValidationError("Invalid provider identity.")
    return value


def _offer(plan, cycle, *, mode="test"):
    """Pure offer snapshot; live callers must explicitly request issuer validation."""
    if cycle not in ("monthly", "yearly"):
        raise ValidationError("Choose monthly or yearly billing.")
    amount = plan.price if cycle == "monthly" else plan.yearly_price
    seller = {"seller": live_seller()} if mode == "live" else {}
    tax_rate = billing_tax_rate()
    if not plan.is_active or amount is None or amount <= 0:
        raise ValidationError("An active payable plan and valid tax rate are required.")
    tax = (amount * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return {
        **seller,
        "plan_id": plan.pk, "plan_name": plan.name, "billing_cycle": cycle,
        "base_amount": str(amount), "tax_rate": str(tax_rate), "tax_amount": str(tax),
        "amount": int((amount + tax) * 100), "currency": "INR",
        "entitlements": build_entitlement_defaults(SimpleNamespace(plan=plan)),
    }


def _verify_plan(entity, provider_id, snapshot):
    if not isinstance(entity, dict):
        raise ValidationError("Provider plan response is invalid.")
    item = entity.get("item")
    if (entity.get("id") != provider_id or entity.get("entity") != "plan" or
            entity.get("period") != snapshot["billing_cycle"] or
            type(entity.get("interval")) is not int or entity["interval"] != 1 or
            not isinstance(item, dict) or type(item.get("amount")) is not int or
            item["amount"] != snapshot["amount"] or item.get("currency") != snapshot["currency"]):
        raise ValidationError("Provider plan does not match the frozen price, currency and cycle.")


def _catalog_mode(mode, *, preview=False):
    from .provider_configuration import provider_mode
    if mode == "test":
        if preview:
            provider_test_mode()
        else:
            _test_mode()
    if mode not in {"test", "live"} or provider_mode() != mode:
        raise ValidationError("Catalog mode must match the configured provider mode.")
    if mode == "live":
        if settings.BILLING_CHECKOUT_ENABLED or settings.BILLING_RECURRING_ENABLED:
            raise PermissionDenied("Pause checkout and recurring authorization before live catalog preparation.")
        from .readiness import billing_evidence_inventory
        blockers = billing_evidence_inventory()["blockers"]
        if blockers:
            raise ValidationError(blockers)
    if RecurringPlanBinding.objects.exclude(mode=mode).exists():
        raise ValidationError("Stored catalog bindings belong to another provider mode.")
    return mode


def review_plan_binding(*, actor, plan_id, cycle, provider_plan_id, reason, mode="test"):
    """Read one provider plan and return local commercial terms; persist nothing."""
    _outside_transaction()
    if not actor.is_active or not is_platform_admin(actor):
        raise PermissionDenied("Only a platform administrator can bind provider plans.")
    _catalog_mode(mode, preview=True)
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError("A catalog binding reason is required.")
    provider_plan_id = _identity(provider_plan_id, "plan_")
    plan = Plan.objects.get(pk=plan_id)
    snapshot = _offer(plan, cycle, mode=mode)
    entity = RazorpayService.get_plan(provider_plan_id)
    _verify_plan(entity, provider_plan_id, snapshot)
    if _offer(Plan.objects.get(pk=plan_id), cycle, mode=mode) != snapshot:
        raise ValidationError("The local offer changed during provider verification.")
    existing = RecurringPlanBinding.objects.filter(mode=mode, provider_plan_id=provider_plan_id).first()
    if existing and (existing.plan_id != plan.pk or existing.snapshot != snapshot):
        raise ValidationError("This provider plan is already bound to different terms.")
    _catalog_mode(mode, preview=True)
    return {"mode": mode, "plan_id": plan.pk, "provider_plan_id": provider_plan_id,
            "snapshot": snapshot, "reason": reason}


def bind_plan(*, actor, plan_id, cycle, provider_plan_id, reason, mode="test"):
    """Register verified catalog terms only; never create a provider plan or mandate."""
    _outside_transaction()
    if not actor.is_active or not is_platform_admin(actor):
        raise PermissionDenied("Only a platform administrator can bind provider plans.")
    _catalog_mode(mode)
    review = review_plan_binding(actor=actor, plan_id=plan_id, cycle=cycle,
        provider_plan_id=provider_plan_id, reason=reason, mode=mode)
    snapshot = review["snapshot"]
    with transaction.atomic():
        plan = Plan.objects.select_for_update().get(pk=plan_id)
        _catalog_mode(mode)
        if _offer(plan, cycle, mode=mode) != snapshot:
            raise ValidationError("The local offer changed during provider verification.")
        existing = RecurringPlanBinding.objects.filter(mode=mode, provider_plan_id=provider_plan_id).first()
        if existing:
            if existing.plan_id != plan.pk or existing.snapshot != snapshot:
                raise ValidationError("This provider plan is already bound to different terms.")
            return existing
        return RecurringPlanBinding.objects.create(
            plan=plan, mode=mode, provider_plan_id=provider_plan_id,
            snapshot=snapshot, actor=actor, reason=review["reason"],
        )


def require_no_recurring_agreement(workspace):
    """Called with the Company row locked by the manual purchase path too."""
    if RecurringAgreement.objects.filter(workspace=workspace, closed_at__isnull=True).exists():
        raise ValidationError("A recurring agreement or uncertain attempt needs reconciliation before another purchase.")


def _locked_owner(workspace_id, actor):
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    if not actor.is_active:
        raise PermissionDenied("An active billing actor is required.")
    require_billing_owner(workspace=workspace, actor=actor)
    return workspace


def create_agreement(*, workspace_id, actor, binding_id, total_count, request_key, start_at=None):
    """Commit exactly one attempt before one POST. Unknown outcomes never repost."""
    _outside_transaction()
    mode = _creation_mode()
    if start_at is not None and mode == "live":
        raise ValidationError("Scheduled live starts require a separately reviewed transition workflow.")
    try:
        key = UUID(str(request_key))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError("A valid agreement request key is required.") from exc
    if type(total_count) is not int or not 1 <= total_count <= 100:
        raise ValidationError("Provide an explicit duration of 1 to 100 billing cycles.")
    if start_at is not None:
        if type(start_at) is not int or start_at <= 0:
            raise ValidationError("Scheduled start must be an integer Unix timestamp.")
        try:
            datetime.fromtimestamp(start_at, tz=dt_timezone.utc)
        except (ValueError, OverflowError, OSError) as exc:
            raise ValidationError("Scheduled start is outside the supported date range.") from exc
    with workspace_context(workspace_id):
        workspace = _locked_owner(workspace_id, actor)
        existing = RecurringAgreement.objects.filter(request_key=key).first()
        if existing:
            if (existing.workspace_id != workspace.pk or existing.binding_id != binding_id or
                    existing.request_snapshot["total_count"] != total_count or existing.binding.mode != mode or
                    existing.request_snapshot.get("start_at") != start_at):
                raise ValidationError("The request key belongs to a different agreement.")
            if existing.state != RecurringAgreement.State.VERIFIED:
                raise ValidationError("This agreement creation needs provider reconciliation; do not create another.")
            return existing
        if start_at is not None and start_at <= timezone.now().timestamp():
            raise ValidationError("A new scheduled agreement must start in the future.")
        if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
            raise ValidationError("Only an active Workspace can start a recurring agreement.")
        require_no_recurring_agreement(workspace)
        binding = RecurringPlanBinding.objects.select_related("plan").get(pk=binding_id)
        if binding.mode != mode or binding.snapshot != _offer(binding.plan, binding.snapshot["billing_cycle"], mode=mode):
            raise ValidationError("The provider binding is stale or belongs to another mode.")
        seats = next(x for x in binding.snapshot["entitlements"] if x["feature_code"] == "workspace.max_members")
        if get_workspace_member_usage(workspace=workspace, include_pending_invitations=True) > int(seats["value"]):
            raise ValidationError("Workspace members and pending invitations exceed this offer's seats.")
        subscription = Subscription.objects.filter(company=workspace).first()
        if subscription:
            if (subscription.razorpay_subscription_id or
                    (subscription.status == "active" and subscription.end_date > timezone.now()) or
                    (subscription.status == "trial" and subscription.trial_end_date and subscription.trial_end_date > timezone.now())):
                raise ValidationError("Existing paid/trial time or a legacy mandate requires a scheduled transition review.")
            if Invoice.objects.filter(subscription=subscription, status__in=["issued", "overdue"]).exists():
                raise ValidationError("Resolve outstanding manual purchases before starting recurring billing.")
        payload = {
            "plan_id": binding.provider_plan_id, "total_count": total_count, "quantity": 1,
            "customer_notify": False,
            "notes": {"workspace_id": str(workspace.pk), "rokkad_attempt": str(key)},
        }
        if start_at is not None:
            payload["start_at"] = start_at
        agreement = RecurringAgreement.objects.create(
            workspace=workspace, binding=binding, request_key=key, request_snapshot=payload, actor=actor,
        )
        RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor, event_type="creation.requested")
    # The Workspace transaction has COMMITTED here, including the exclusive reservation.
    try:
        _verify_plan(RazorpayService.get_plan(binding.provider_plan_id), binding.provider_plan_id, binding.snapshot)
        entity = RazorpayService.create_subscription(payload)
        return _record_provider(agreement_id=agreement.pk, workspace_id=workspace_id, actor=actor,
                                entity=entity, event_type="creation.verified", reason="Initial provider response")
    except (BillingProviderError, ValidationError):
        with workspace_context(workspace_id):
            Company.all_objects.select_for_update().get(pk=workspace_id)
            current = RecurringAgreement.objects.select_for_update().get(pk=agreement.pk)
            # A concurrent explicit reconciliation may already have verified it.
            if current.state != RecurringAgreement.State.VERIFIED:
                current.state = RecurringAgreement.State.UNKNOWN
                current.save(update_fields=["state"])
                RecurringAgreementEvent.objects.create(agreement=current, actor=actor, event_type="creation.unknown")
        raise


def verify_agreement(agreement, entity):
    expected = agreement.request_snapshot
    if not isinstance(entity, dict):
        raise ValidationError("Invalid provider agreement response; reconcile the saved attempt.")
    provider_id = _identity(entity.get("id"), "sub_")
    if "start_at" in expected and (type(entity.get("start_at")) is not int or
                                   entity["start_at"] != expected["start_at"]):
        raise ValidationError("Provider agreement does not match the frozen scheduled start.")
    if (entity.get("entity") != "subscription" or entity.get("plan_id") != expected["plan_id"] or
            type(entity.get("quantity")) is not int or entity["quantity"] != 1 or
            type(entity.get("total_count")) is not int or entity["total_count"] != expected["total_count"] or
            entity.get("notes") != expected["notes"] or entity.get("customer_notify") not in (False, 0) or
            entity.get("has_scheduled_changes") is not False or entity.get("offer_id") or
            entity.get("status") not in {"created", "authenticated", "active", "pending", "halted",
                                         "cancelled", "completed", "expired", "paused"} or
            (agreement.provider_subscription_id and agreement.provider_subscription_id != provider_id)):
        raise ValidationError("Provider agreement does not match this Workspace's frozen attempt.")
    return provider_id


def verify_agreement_observation(agreement, entity):
    """Validate a status write; old financial evidence uses identity checks only."""
    provider_id = verify_agreement(agreement, entity)
    terminal = {"cancelled", "completed", "expired"}
    if agreement.provider_status in terminal and entity["status"] not in terminal:
        raise ValidationError("Provider status conflicts with the saved terminal state; reconcile the agreement.")
    return provider_id


def _record_provider(*, agreement_id, workspace_id, actor, entity, event_type, reason):
    with workspace_context(workspace_id):
        Company.all_objects.select_for_update().get(pk=workspace_id)
        agreement = RecurringAgreement.objects.select_for_update().select_related("binding").get(
            pk=agreement_id, workspace_id=workspace_id)
        provider_id = verify_agreement_observation(agreement, entity)
        if agreement.closed_at:
            return agreement  # Closed identity/history is immutable; reconciliation cannot reopen it.
        if RecurringAgreement.objects.filter(provider_subscription_id=provider_id).exclude(pk=agreement.pk).exists():
            raise ValidationError("Provider agreement is already assigned to another attempt.")
        agreement.provider_subscription_id = provider_id
        agreement.provider_status = entity["status"]
        agreement.state = RecurringAgreement.State.VERIFIED
        agreement.verified_at = timezone.now()
        agreement.save(update_fields=["provider_subscription_id", "provider_status", "state", "verified_at"])
        RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor, event_type=event_type,
            detail={"provider_status": entity["status"], "reason": reason})
        # Terminal observations keep the slot until the explicit settlement release review.
        # No Subscription dates, auto_renew, invoices, payments or entitlements are written here.
        return agreement


def reconcile_agreement(*, workspace_id, actor, agreement_id, provider_subscription_id, reason):
    """Verify an operator-located ID against the durable identity, never re-POST."""
    _outside_transaction()
    mode = recurring_provider_mode()
    reason = str(reason or "").strip()
    if not reason:
        raise ValidationError("A reconciliation reason is required.")
    provider_subscription_id = _identity(provider_subscription_id, "sub_")
    with workspace_context(workspace_id):
        _locked_owner(workspace_id, actor)
        agreement = RecurringAgreement.objects.select_related("binding").filter(
            pk=agreement_id, workspace_id=workspace_id).first()
        if not agreement or agreement.binding.mode != mode:
            raise ValidationError("No matching agreement exists in this Workspace and provider mode.")
        if agreement.provider_subscription_id and agreement.provider_subscription_id != provider_subscription_id:
            raise ValidationError("Reconciliation cannot replace the provider identity.")
    entity = RazorpayService.get_subscription(provider_subscription_id)
    if not isinstance(entity, dict) or entity.get("id") != provider_subscription_id:
        raise ValidationError("Provider subscription identity does not match.")
    _verify_plan(RazorpayService.get_plan(agreement.binding.provider_plan_id),
                 agreement.binding.provider_plan_id, agreement.binding.snapshot)
    # Recheck owner after remote reads before committing an operator action.
    with workspace_context(workspace_id):
        _locked_owner(workspace_id, actor)
        return _record_provider(agreement_id=agreement.pk, workspace_id=workspace_id, actor=actor,
                                entity=entity, event_type="agreement.reconciled", reason=reason)
