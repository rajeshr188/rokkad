"""Explicit release of fully refunded, reviewed Test Mode mandates.

This does not cancel, refund, create a replacement, or change commercial access.
Unpaid attempts, scheduled authorizations and unreturned money stay reserved.
"""
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from .models import (BillingResolution, Invoice, Payment, RecurringAgreement,
                     RecurringAgreementEvent, Subscription)
from .razorpay_service import RazorpayService
from .recurring import _identity, _outside_transaction, provider_test_mode, verify_agreement_observation
from .recurring_access import _active_owner
from .recurring_cycles import _facts
from .recovery import _validate_refund


def _collection(response):
    if (not isinstance(response, dict) or response.get("entity") != "collection" or
            not isinstance(response.get("items"), list) or type(response.get("count")) is not int or
            response["count"] != len(response["items"]) or
            any(not isinstance(row, dict) for row in response["items"])):
        raise ValidationError("Incomplete provider collection; keep the agreement reserved.")
    return response["items"]


def _invoice_ids(agreement):
    identities = set()
    # Bounded scan, including a final empty page. Never infer completeness from
    # a short page: providers may cap the requested page size.
    for _ in range(102):
        rows = _collection(RazorpayService.get_subscription_invoices(
            agreement.provider_subscription_id, skip=len(identities)))
        if not rows:
            return identities
        for row in rows:
            identity = _identity(row.get("id"), "inv_")
            if (identity in identities or row.get("subscription_id") != agreement.provider_subscription_id or
                    row.get("status") != "paid"):
                raise ValidationError("Duplicate, foreign or unpaid invoices require reconciliation before release.")
            identities.add(identity)
        if len(identities) > agreement.request_snapshot["total_count"]:
            break
    raise ValidationError("Provider invoice listing could not be fully reconciled.")


def _terminal(agreement, provider, count):
    verify_agreement_observation(agreement, provider)
    if (provider["status"] != "cancelled" or "charge_at" not in provider or provider["charge_at"] is not None or
            type(provider.get("paid_count")) is not int or provider["paid_count"] != count):
        raise ValidationError("A cancelled mandate with no next charge and matching paid count is required.")


def _local_evidence(agreement, subscription):
    cycles = list(agreement.cycles.select_related("invoice").order_by("pk"))
    if not cycles:
        raise ValidationError("No settled paid cycles exist; uncertain authorization attempts stay reserved.")
    result = []
    for cycle in cycles:
        payment = Payment.objects.filter(invoice=cycle.invoice,
            razorpay_payment_id=cycle.evidence["payment_id"]).first()
        resolution = BillingResolution.objects.filter(invoice=cycle.invoice).first()
        if (cycle.invoice.subscription_id != subscription.pk or cycle.invoice.status != "paid" or
                not payment or payment.status != "refunded" or payment.amount != cycle.invoice.total_amount or
                int(payment.amount * 100) != cycle.evidence["amount"] or payment.refund_amount != payment.amount or
                payment.refunds.aggregate(total=Sum("amount"))["total"] != payment.amount or not resolution or
                resolution.action not in {"end_access", "retain_access"} or
                resolution.evidence.get("cycle_id") != cycle.pk):
            raise ValidationError("Every cycle needs matching full refunds and a completed access review.")
        result.append({"cycle_id": cycle.pk, "invoice_id": cycle.provider_invoice_id,
            "payment_id": payment.razorpay_payment_id, "resolution_id": resolution.pk,
            "refunds": list(payment.refunds.order_by("pk").values_list("provider_refund_id", "amount"))})
    return cycles, result


def release_refunded_agreement(*, workspace_id, actor, agreement_id, revision, reason):
    """Own transactions, verify remotely, then compare local state under the Company lock."""
    _outside_transaction()
    mode = provider_test_mode()
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A release reason of up to 1000 characters is required.")
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        actor = _active_owner(workspace, actor)
        agreement = RecurringAgreement.objects.select_related("binding").filter(
            pk=agreement_id, workspace=workspace, binding__mode=mode, state="verified").first()
        if not agreement:
            raise ValidationError("A verified agreement in this Workspace and provider mode is required.")
        if agreement.closed_at:
            return agreement.events.get(event_type="reservation.released")
        if "start_at" in agreement.request_snapshot:
            raise ValidationError("Scheduled authorization settlement requires separate review.")
        subscription = Subscription.objects.get(company=workspace)
        cycles, evidence = _local_evidence(agreement, subscription)
    provider = RazorpayService.get_subscription(agreement.provider_subscription_id)
    _terminal(agreement, provider, len(cycles))
    identities = _invoice_ids(agreement)
    if identities != {cycle.provider_invoice_id for cycle in cycles}:
        raise ValidationError("Provider invoices differ from local cycles; reconcile every invoice before release.")
    for cycle, saved in zip(cycles, evidence):
        facts, payment, _, _, _ = _facts(agreement, cycle.provider_invoice_id)
        if facts != cycle.evidence or payment["status"] != "refunded" or payment["amount_refunded"] != facts["amount"]:
            raise ValidationError("Fresh full-refund evidence differs from the recorded cycle.")
        attempts = _collection(RazorpayService.get_order_payments(facts["order_id"]))
        attempt_ids = set()
        for attempt in attempts:
            identity = _identity(attempt.get("id"), "pay_")
            if identity in attempt_ids or attempt.get("order_id") != facts["order_id"]:
                raise ValidationError("Order payment evidence is inconsistent.")
            attempt_ids.add(identity)
            if identity == facts["payment_id"]:
                if attempt.get("status") != "refunded" or attempt.get("amount_refunded") != facts["amount"]:
                    raise ValidationError("Order refund evidence is inconsistent.")
            elif attempt.get("status") != "failed":
                raise ValidationError("Another payment attempt remains unsettled; keep the reservation.")
        if facts["payment_id"] not in attempt_ids:
            raise ValidationError("The order does not list the refunded payment.")
        for refund_id, amount in saved["refunds"]:
            refund = RazorpayService.get_refund(refund_id)
            _validate_refund(cycle.invoice, payment, refund, refund_id)
            if refund["amount"] != int(amount * 100):
                raise ValidationError("Fresh refund amount differs from saved evidence.")
    # Recheck collection and terminal state after remote reads, before local commit.
    if _invoice_ids(agreement) != identities:
        raise ValidationError("Provider invoices changed during release review.")
    provider = RazorpayService.get_subscription(agreement.provider_subscription_id)
    _terminal(agreement, provider, len(cycles))
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        actor = _active_owner(workspace, actor)
        agreement = RecurringAgreement.objects.select_for_update().get(pk=agreement_id, workspace=workspace)
        if agreement.closed_at:
            return agreement.events.get(event_type="reservation.released")
        _terminal(agreement, provider, len(cycles))
        subscription = Subscription.objects.select_for_update().get(company=workspace)
        if revision != subscription.updated_at.isoformat():
            raise ValidationError("Subscription changed during release review. Reload its current terms.")
        if (subscription.status != "cancelled" or subscription.razorpay_subscription_id or
                (subscription.trial_end_date and subscription.trial_end_date > timezone.now()) or
                Invoice.objects.filter(subscription=subscription, status__in=["issued", "overdue"]).exists()):
            raise ValidationError("Access must be ended and other purchase or trial obligations resolved before release.")
        if _local_evidence(agreement, subscription)[1] != evidence:
            raise ValidationError("Local settlement evidence changed during release review.")
        if Invoice.objects.filter(subscription=subscription, status="paid").exclude(
                recurring_cycle__agreement=agreement).exclude(
                recurring_cycle__agreement__closed_at__isnull=False, payment__status="refunded",
                billing_resolution__action__in=["end_access", "retain_access"]).exists():
            raise ValidationError("Other paid invoices or held periods require separate review before release.")
        agreement.provider_status = provider["status"]
        agreement.verified_at = agreement.closed_at = timezone.now()
        agreement.save(update_fields=["provider_status", "verified_at", "closed_at"])
        return RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
            event_type="reservation.released", detail={"reason": reason.strip(), "revision": revision,
                "provider_status": provider["status"], "paid_count": provider["paid_count"],
                "cycles": [{**row, "refunds": [rid for rid, _ in row["refunds"]]} for row in evidence]})
