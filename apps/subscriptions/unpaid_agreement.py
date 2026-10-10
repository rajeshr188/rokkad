"""Explicitly retire an unauthorised, unpaid mandate before another purchase.

Own short transactions; provider cancellation intent is committed before a single
POST. Unknown results stay reserved. No paid/refunded/scheduled agreement qualifies.
"""
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from .models import Invoice, RecurringAgreement, RecurringAgreementEvent, Subscription
from .razorpay_service import RazorpayService
from .recurring import (_outside_transaction, _locked_owner, _identity,
                        recurring_provider_mode, verify_agreement_observation)
from .recurring_release import _collection


def _unused(agreement, provider):
    verify_agreement_observation(agreement, provider)
    if (provider['status'] != 'cancelled' or type(provider.get('paid_count')) is not int
            or provider['paid_count'] != 0 or type(provider.get('auth_attempts')) is not int
            or provider['auth_attempts'] != 0 or any(provider.get(k) is not None
                for k in ('charge_at', 'start_at', 'current_start', 'current_end'))):
        raise ValidationError('Only a cancelled, never-authorized agreement with no charge can be released.')


def _local(agreement):
    if (agreement.state != 'verified' or 'start_at' in agreement.request_snapshot
            or agreement.cycles.exists() or agreement.events.filter(
                event_type__in=['authorization.verified', 'authorization.observed']).exists()
            or Invoice.objects.filter(subscription__company_id=agreement.workspace_id).exists()):
        raise ValidationError('Payment or authorization history requires a separate billing review.')
    subscription = Subscription.objects.filter(company_id=agreement.workspace_id).first()
    if subscription and (subscription.status != 'trial' or subscription.razorpay_subscription_id):
        raise ValidationError('Only an unpaid trial or new Workspace can release this unused agreement.')
    return subscription.updated_at.isoformat() if subscription else None


def _invoices(agreement):
    result = {}
    for _ in range(102):
        rows = _collection(RazorpayService.get_subscription_invoices(
            agreement.provider_subscription_id, skip=len(result)))
        if not rows:
            return result
        for row in rows:
            identity = _identity(row.get('id'), 'inv_')
            if (identity in result or row.get('subscription_id') != agreement.provider_subscription_id
                    or row.get('payment_id') or row.get('paid_at') or row.get('amount_paid') not in (0, None)
                    or row.get('status') not in ('issued', 'cancelled', 'expired')):
                raise ValidationError('Provider invoices are not completely unpaid; keep the reservation.')
            result[identity] = row
    raise ValidationError('Provider invoice listing is incomplete; keep the reservation.')


def _failed_attempts(invoice):
    order_id = _identity(invoice.get('order_id'), 'order_')
    rows = _collection(RazorpayService.get_order_payments(order_id))
    identities = set()
    for row in rows:
        identity = _identity(row.get('id'), 'pay_')
        if (identity in identities or row.get('order_id') != order_id
                or row.get('status') != 'failed' or row.get('amount_refunded', 0) != 0):
            raise ValidationError('An unsettled payment attempt prevents switching payment options.')
        identities.add(identity)
    return sorted(identities)


def release_unused_agreement(*, workspace_id, actor, agreement_id, reason):
    _outside_transaction()
    mode = recurring_provider_mode()
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError('An explicit release reason of up to 1000 characters is required.')
    with workspace_context(workspace_id):
        _locked_owner(workspace_id, actor)
        agreement = RecurringAgreement.objects.select_related('binding').get(
            pk=agreement_id, workspace_id=workspace_id, binding__mode=mode)
        if agreement.closed_at:
            return agreement.events.get(event_type='reservation.unpaid_released')
        revision = _local(agreement)
    _unused(agreement, RazorpayService.get_subscription(agreement.provider_subscription_id))
    invoices = _invoices(agreement)
    for identity, invoice in invoices.items():
        _failed_attempts(invoice)
        if invoice['status'] == 'issued':
            with workspace_context(workspace_id):
                _locked_owner(workspace_id, actor)
                current = RecurringAgreement.objects.select_for_update().get(pk=agreement.pk)
                if current.closed_at or _local(current) != revision:
                    raise ValidationError('Billing changed during release review.')
                dispatched = current.events.filter(event_type='unused_invoice.cancel_dispatched',
                    detail__invoice_id=identity).exists()
                if not dispatched:
                    RecurringAgreementEvent.objects.create(agreement=current, actor=actor,
                        event_type='unused_invoice.cancel_dispatched',
                        detail={'invoice_id': identity, 'reason': reason.strip()})
            if not dispatched:
                RazorpayService.cancel_invoice(identity)
            # Retry fetches only. A lost response cannot trigger another cancellation.
    settled = _invoices(agreement)
    if set(settled) != set(invoices):
        raise ValidationError('Provider invoice set changed during review.')
    evidence = []
    for identity, invoice in settled.items():
        if invoice['status'] not in ('cancelled', 'expired'):
            raise ValidationError('The unpaid invoice is still payable; keep the reservation and contact support.')
        evidence.append({'invoice_id': identity, 'order_id': invoice['order_id'],
                         'status': invoice['status'], 'failed_payments': _failed_attempts(invoice)})
    provider = RazorpayService.get_subscription(agreement.provider_subscription_id)
    _unused(agreement, provider)
    with workspace_context(workspace_id):
        _locked_owner(workspace_id, actor)
        agreement = RecurringAgreement.objects.select_for_update().get(pk=agreement.pk)
        if agreement.closed_at:
            return agreement.events.get(event_type='reservation.unpaid_released')
        if _local(agreement) != revision:
            raise ValidationError('Billing changed during release review.')
        _unused(agreement, provider)
        agreement.provider_status = 'cancelled'
        agreement.verified_at = agreement.closed_at = timezone.now()
        agreement.save(update_fields=['provider_status', 'verified_at', 'closed_at'])
        return RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
            event_type='reservation.unpaid_released', detail={'reason': reason.strip(),
                'revision': revision, 'provider_status': 'cancelled', 'paid_count': 0,
                'auth_attempts': 0, 'invoices': evidence})
