"""Selected annual prepayment; durable order intent, no recurring mandate."""
from datetime import timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from .models import (BillingAccount, Invoice, Payment, Plan, RecurringAgreement,
                     Subscription, SubscriptionEvent)
from .access_policy import require_purchase_access_history
from .provider_configuration import provider_mode, require_invoice_mode
from .public_recurring import require_public_owner
from .razorpay_service import RazorpayService
from .recurring import _offer, _outside_transaction, _identity, require_no_recurring_agreement
from .recurring_release import _collection
from .services import build_billing_account_defaults, get_workspace_member_usage

TERMS = 'annual-prepaid-14990-6members-no-autorenew-20261009'
SALT = 'subscriptions.public-prepaid'
KIND = 'annual_prepaid'


def selected_offer(*, workspace=None):
    plan_id = getattr(settings, 'BILLING_PUBLIC_PREPAID_PLAN_ID', 0)
    scope = getattr(settings, 'BILLING_PREPAID_WORKSPACE_IDS', [])
    if (not plan_id or not isinstance(scope, (list, tuple)) or
            any(not str(v).isdigit() or int(v) <= 0 for v in scope) or
            (scope and getattr(workspace, 'pk', None) not in {int(v) for v in scope})):
        raise PermissionDenied('Annual prepaid billing is not enabled for this Workspace yet.')
    mode = provider_mode()
    plan = Plan.objects.filter(pk=plan_id, is_active=True).first()
    if not plan or plan.price != Decimal('1499') or plan.yearly_price != Decimal('14990') or plan.max_users != 6:
        raise ValidationError('The annual offer needs review. Contact support.')
    offer = _offer(plan, 'yearly', mode=mode)
    if offer['amount'] != 1499000 or Decimal(offer['tax_rate']) != 0:
        raise ValidationError('The annual offer must be INR 14,990 total with no GST charged.')
    return {**offer, 'plan_name': 'Rokkad Workspace Annual Prepaid', 'kind': KIND, 'provider_mode': mode, 'terms': TERMS, 'auto_renew': False}


def require_eligible(workspace, *, plan_id, excluding_invoice=None):
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise ValidationError('This Workspace cannot start a paid purchase.')
    require_no_recurring_agreement(workspace)
    for agreement in RecurringAgreement.objects.filter(workspace=workspace):
        if not agreement.events.filter(event_type='reservation.unpaid_released').exists():
            raise ValidationError('Previous recurring billing needs review before annual prepayment.')
    require_purchase_access_history(workspace)
    invoices = Invoice.objects.filter(subscription__company=workspace).exclude(pk=excluding_invoice)
    for invoice in invoices:
        if (invoice.status != 'paid' or invoice.checkout_snapshot.get('kind') != KIND
                or invoice.checkout_snapshot.get('plan_id') != plan_id
                or hasattr(invoice, 'billing_resolution') or
                not Payment.objects.filter(invoice=invoice, status='captured', refund_amount=0).exists()):
            raise ValidationError('An existing purchase needs review. Do not create another payment.')
    subscription = Subscription.objects.filter(company=workspace).first()
    if subscription:
        if subscription.razorpay_subscription_id:
            raise ValidationError('An existing payment mandate needs review.')
        if subscription.status == 'trial':
            if not subscription.trial_end_date or subscription.trial_end_date > timezone.now():
                raise ValidationError('Your free trial must end before annual prepayment.')
        elif not (subscription.status in ('active', 'past_due', 'expired') and
                  subscription.plan_id == plan_id and not subscription.auto_renew and
                  (invoices.exists() or subscription.status == 'past_due')):
            raise ValidationError('Your existing subscription needs review before paying.')
    if get_workspace_member_usage(workspace=workspace, include_pending_invitations=True) > 6:
        raise ValidationError('This offer allows the owner plus five staff, including pending invitations.')


def offer_context(*, workspace, actor):
    try:
        offer = selected_offer(workspace=workspace)
        require_public_owner(workspace=workspace, actor=actor)
    except (ValidationError, PermissionDenied):
        return {}
    context = {'annual_offer': offer, 'annual_terms': TERMS}
    pending = Invoice.objects.filter(subscription__company=workspace,
        checkout_snapshot__kind=KIND, status='issued').order_by('pk').first()
    try:
        require_eligible(workspace, plan_id=offer['plan_id'], excluding_invoice=getattr(pending, 'pk', None))
        if pending and pending.checkout_snapshot.get('offer') != offer:
            raise ValidationError('Your pending annual order needs review before continuing.')
    except ValidationError as exc:
        context['annual_unavailable_reason'] = exc.messages[0]
    else:
        context['annual_consent'] = signing.dumps({'workspace_id': workspace.pk,
            'actor_id': actor.pk, 'offer': offer,
            'request_key': str(pending.checkout_key if pending else uuid4())}, salt=SALT, compress=True)
        context['annual_pending'] = pending
    return context


def read_consent(token, actor):
    try:
        consent = signing.loads(token, salt=SALT, max_age=1800)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValidationError('The annual review expired. Reload the annual payment page.') from exc
    if not isinstance(consent, dict) or consent.get('actor_id') != actor.pk:
        raise PermissionDenied('This annual review belongs to another owner.')
    return consent


def _verify_order(invoice, order):
    snapshot = invoice.checkout_snapshot
    if (not isinstance(order, dict) or order.get('entity') != 'order'
            or order.get('receipt') != invoice.invoice_number
            or type(order.get('amount')) is not int or order['amount'] != snapshot['amount']
            or order.get('currency') != 'INR' or order.get('notes') != {'workspace_id': str(snapshot['workspace_id'])}
            or (invoice.razorpay_order_id and order.get('id') != invoice.razorpay_order_id)):
        raise ValidationError('Provider order does not match this saved purchase. Contact support.')
    return _identity(order.get('id'), 'order_')


def prepare_purchase(*, workspace_id, actor, consent):
    _outside_transaction()
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        require_public_owner(workspace=workspace, actor=actor)
        offer = selected_offer(workspace=workspace)
        try:
            key = UUID(consent['request_key'])
        except (KeyError, ValueError, TypeError, AttributeError) as exc:
            raise ValidationError('Invalid annual purchase review.') from exc
        if consent != {'workspace_id': workspace.pk, 'actor_id': actor.pk, 'offer': offer, 'request_key': str(key)}:
            raise ValidationError('The annual offer has changed. Review it again.')
        if not settings.RAZORPAY_WEBHOOK_SECRET:
            raise ValidationError('Payment callbacks must be configured before taking payment.')
        if offer['provider_mode'] == 'live':
            from .readiness import billing_evidence_inventory
            blockers = billing_evidence_inventory()['blockers']
            if blockers:
                raise ValidationError(blockers)
        invoice = Invoice.objects.filter(checkout_key=key).first()
        if invoice:
            require_invoice_mode(invoice)
            if (invoice.subscription.company_id != workspace.pk or
                    invoice.checkout_snapshot.get('offer') != offer or
                    invoice.checkout_snapshot.get('actor_id') != actor.pk):
                raise ValidationError('This review belongs to another purchase.')
            if not invoice.razorpay_order_id:
                raise ValidationError('The order outcome needs reconciliation. Do not start another purchase.')
            return invoice
        require_eligible(workspace, plan_id=offer['plan_id'])
        subscription, _ = Subscription.objects.get_or_create(company=workspace,
            defaults={'plan_id': offer['plan_id'], 'status': 'past_due', 'auto_renew': False})
        defaults = build_billing_account_defaults(subscription)
        defaults.pop('company')
        account, _ = BillingAccount.objects.get_or_create(company=workspace, defaults=defaults)
        snapshot = {**offer, 'offer': offer, 'workspace_id': workspace.pk, 'actor_id': actor.pk,
            'accepted_at': timezone.now().isoformat(),
            'subscription_revision': subscription.updated_at.isoformat(),
            'prior_subscription': {'plan_id': subscription.plan_id, 'status': subscription.status,
                'trial_end_date': subscription.trial_end_date.isoformat() if subscription.trial_end_date else None},
            'contact_name': account.contact_name or workspace.name, 'billing_email': account.billing_email or ''}
        invoice = Invoice.objects.create(subscription=subscription, checkout_key=key,
            checkout_snapshot=snapshot, invoice_number=f'CHK-{key.hex}', base_amount=Decimal('14990'),
            gst_rate=0, invoice_date=timezone.localdate(), due_date=timezone.localdate() + timedelta(days=7))
        SubscriptionEvent.objects.create(subscription=subscription, event_type='prepaid.requested',
            payload={'invoice_id': invoice.pk, 'actor_id': actor.pk, 'terms': TERMS, 'request_key': str(key)})
    # Persist the reservation BEFORE provider I/O. Failure never rolls it back or reposts.
    order = RazorpayService.create_order(amount=1499000, currency='INR',
        receipt=invoice.invoice_number, workspace_id=workspace_id)
    order_id = _verify_order(invoice, order)
    with workspace_context(workspace_id):
        Company.all_objects.select_for_update().get(pk=workspace_id)
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        if invoice.razorpay_order_id and invoice.razorpay_order_id != order_id:
            raise ValidationError('Order identity changed; reconcile this purchase.')
        invoice.razorpay_order_id = order_id
        invoice.save(update_fields=['razorpay_order_id', 'updated_at'])
    return invoice


def payment_options(*, workspace_id, actor, invoice_id):
    """Authorize no charge; return only an unused verified order for owner checkout."""
    _outside_transaction()
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        require_public_owner(workspace=workspace, actor=actor)
        invoice = Invoice.objects.select_related('subscription').get(pk=invoice_id, subscription__company=workspace)
        require_invoice_mode(invoice)
        if invoice.status == 'paid':
            return {'paid': True}
        offer = selected_offer(workspace=workspace)
        if invoice.status != 'issued' or invoice.checkout_snapshot.get('offer') != offer:
            raise ValidationError('This purchase needs review before payment.')
        require_eligible(workspace, plan_id=offer['plan_id'], excluding_invoice=invoice.pk)
        if invoice.subscription.updated_at.isoformat() != invoice.checkout_snapshot['subscription_revision']:
            raise ValidationError('Billing changed after this review. Contact support.')
    order = RazorpayService.get_order(invoice.razorpay_order_id)
    _verify_order(invoice, order)
    attempts = _collection(RazorpayService.get_order_payments(invoice.razorpay_order_id))
    if attempts or order.get('status') != 'created' or order.get('amount_paid') != 0 or order.get('attempts') != 0:
        raise ValidationError('A payment was already attempted. Check Billing or contact support to verify it before paying again.')
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        require_public_owner(workspace=workspace, actor=actor)
        current = Invoice.objects.select_related('subscription').get(pk=invoice.pk)
        if (current.status != 'issued' or selected_offer(workspace=workspace) != offer or
                current.subscription.updated_at.isoformat() != current.checkout_snapshot['subscription_revision']):
            raise ValidationError('Billing changed during payment verification. Reload Billing.')
        require_eligible(workspace, plan_id=offer['plan_id'], excluding_invoice=invoice.pk)
    return {'key': settings.RAZORPAY_KEY_ID, 'order_id': invoice.razorpay_order_id,
        'amount': invoice.checkout_snapshot['amount'], 'currency': 'INR',
        'name': 'Rokkad TEST' if offer['provider_mode'] == 'test' else 'Rokkad',
        'description': '12 months prepaid — no automatic renewal'}


def validate_capture(*, company, invoice):
    """Recovery depends on frozen evidence, never today's publication switches."""
    snapshot = invoice.checkout_snapshot
    if (snapshot.get('terms') != TERMS or snapshot.get('amount') != 1499000
            or snapshot.get('billing_cycle') != 'yearly' or snapshot.get('auto_renew') is not False):
        raise ValidationError('Annual payment terms need review.')
    require_eligible(company, plan_id=snapshot['plan_id'], excluding_invoice=invoice.pk)


def reconcile_order(*, workspace_id, actor, invoice_id, order_id, reason):
    """Bind a provider-located order after an uncertain POST; never creates an order."""
    from .checkout import require_billing_owner
    _outside_transaction()
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError('An order recovery reason is required.')
    order_id = _identity(order_id, 'order_')
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        require_billing_owner(workspace=workspace, actor=actor)
        if not actor.is_active:
            raise PermissionDenied('An active billing actor is required.')
        invoice = Invoice.objects.get(pk=invoice_id, subscription__company=workspace)
        require_invoice_mode(invoice)
        if invoice.checkout_snapshot.get('kind') != KIND:
            raise ValidationError('Only a saved annual prepaid purchase can recover this order.')
    order = RazorpayService.get_order(order_id)
    _verify_order(invoice, order)
    with workspace_context(workspace_id):
        workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
        require_billing_owner(workspace=workspace, actor=actor)
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id, subscription__company=workspace)
        require_invoice_mode(invoice)
        _verify_order(invoice, order)
        if invoice.razorpay_order_id:
            return invoice
        invoice.razorpay_order_id = order_id
        invoice.save(update_fields=['razorpay_order_id', 'updated_at'])
        SubscriptionEvent.objects.create(subscription=invoice.subscription, event_type='prepaid.order_reconciled',
            payload={'invoice_id': invoice.pk, 'order_id': order_id, 'actor_id': actor.pk, 'reason': reason.strip()})
        return invoice
