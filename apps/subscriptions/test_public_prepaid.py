"""Fictional annual orders: real transaction boundaries, no provider or mail traffic."""
import hashlib
import hmac
import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from allauth.account.models import EmailAddress
from dateutil.relativedelta import relativedelta
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership
from apps.platform_mail.models import Delivery
from apps.tenancy.context import current_workspace_id, workspace_context
from . import public_prepaid as prepaid
from .checkout import _apply_capture, confirm_checkout
from .models import Invoice, Payment, Plan, Subscription, SubscriptionEvent
from .razorpay_service import BillingProviderError, RazorpayService
from . import test_live_recurring as live_tests
from .test_live_recurring import LIVE_SETTINGS


SETTINGS = {**LIVE_SETTINGS, 'BILLING_RECURRING_ENABLED': True, 'BILLING_TAX_RATE': '0',
    'BILLING_SELLER_NAME': 'Fictional Seller', 'BILLING_SELLER_ADDRESS': '1 Example Street',
    'BILLING_SELLER_TAX_STATUS': 'unregistered', 'BILLING_PREPAID_WORKSPACE_IDS': []}


@override_settings(**SETTINGS)
class AnnualPrepaidTests(TransactionTestCase):
    created_entity = live_tests.LiveCreationTests.created_entity

    def setUp(self):
        live_tests.LiveCreationTests.setUp(self)
        self.owner.email = 'annual-owner@example.test'
        self.owner.save(update_fields=['email'])
        EmailAddress.objects.create(user=self.owner, email=self.owner.email, verified=True, primary=True)
        setting = override_settings(BILLING_PUBLIC_PREPAID_PLAN_ID=self.plan.pk)
        setting.enable()
        self.addCleanup(setting.disable)
        self.orders = {}
        def create(**kw):
            self.assertFalse(connection.in_atomic_block)
            self.assertIsNone(current_workspace_id())
            self.assertTrue(Invoice.objects.filter(invoice_number=kw['receipt']).exists())
            order = {'id': 'order_' + uuid4().hex, 'entity': 'order', 'receipt': kw['receipt'],
                'amount': kw['amount'], 'currency': kw['currency'], 'status': 'created',
                'amount_paid': 0, 'attempts': 0, 'notes': {'workspace_id': str(kw['workspace_id'])}}
            self.orders[order['id']] = order
            return order
        self.create_order = patch.object(RazorpayService, 'create_order', side_effect=create).start()
        self.order_read = patch.object(RazorpayService, 'get_order', side_effect=lambda pk: self.orders[pk]).start()
        self.attempts = patch.object(RazorpayService, 'get_order_payments', return_value={
            'entity': 'collection', 'count': 0, 'items': []}).start()
        self.client.force_login(self.owner)
        self.url = reverse('workspace_subscriptions:annual-prepaid', kwargs={'workspace_slug': self.workspace.slug})
        self.start_url = reverse('public-prepaid-start')

    def token(self):
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        return page.context['annual_consent']

    def submit(self, token=None, **changes):
        return self.client.post(self.start_url, json.dumps({'offer_token': token or self.token(),
            'accepted_terms': prepaid.TERMS, **changes}), content_type='application/json')

    def payment(self, invoice, **changes):
        return {'id': 'pay_' + str(invoice.pk), 'entity': 'payment', 'order_id': invoice.razorpay_order_id,
            'amount': 1499000, 'currency': 'INR', 'status': 'captured', 'amount_refunded': 0, **changes}

    def trial(self, *, active=False):
        trial_plan = Plan.objects.create(name='Trial fixture', tier='starter', price=0, max_users=6, trial_days=30)
        subscription = Subscription.objects.create(company=self.workspace, plan=trial_plan, status='trial')
        Subscription.objects.filter(pk=subscription.pk).update(trial_end_date=timezone.now() +
            timedelta(days=1 if active else -1))
        subscription.refresh_from_db()
        return subscription

    def test_http_expired_trial_order_capture_and_duplicate_callback(self):
        subscription = self.trial()
        before = subscription.trial_end_date
        token = self.token()
        self.assertContains(self.client.get(self.url), 'No automatic renewal')
        self.assertEqual(self.submit(token).status_code, 200)
        self.assertEqual(self.submit(token).status_code, 200)
        invoice = Invoice.objects.get()
        self.assertEqual(invoice.total_amount, 14990)
        self.assertEqual(invoice.checkout_snapshot['actor_id'], self.owner.pk)
        self.assertEqual(invoice.checkout_snapshot['prior_subscription']['plan_id'], subscription.plan_id)
        self.create_order.assert_called_once()
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, 'trial')
        self.assertFalse(Payment.objects.exists())
        at = timezone.now()
        with patch('apps.subscriptions.checkout.timezone.now', return_value=at):
            _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
            _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
        subscription.refresh_from_db()
        self.assertEqual(subscription.end_date, at + relativedelta(years=1))
        self.assertEqual(subscription.trial_end_date, before)
        self.assertEqual(subscription.plan_id, self.plan.pk)
        self.assertFalse(subscription.auto_renew)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(SubscriptionEvent.objects.filter(event_type='checkout.completed').count(), 1)
        self.assertEqual(Delivery.objects.count(), 1)
        page = self.client.get(reverse('workspace_subscriptions:dashboard', kwargs={'workspace_slug': self.workspace.slug}))
        self.assertContains(page, 'Rokkad Workspace Annual Prepaid')
        self.assertContains(page, 'Annual prepayment — no automatic renewal')
        self.assertNotContains(page, 'Self-service plan purchases are unavailable')

    def test_unknown_order_is_durable_and_fresh_token_cannot_repost(self):
        token, second = self.token(), self.token()
        self.create_order.side_effect = BillingProviderError('Mock timeout')
        for value in (token, token, second):
            self.assertEqual(self.submit(value).status_code, 400)
        self.create_order.assert_called_once()
        self.assertEqual(Invoice.objects.count(), 1)
        self.assertIsNone(Invoice.objects.get().razorpay_order_id)
        self.assertFalse(Payment.objects.exists())

    def test_two_reviews_reserve_only_one_invoice_and_monthly_cannot_overlap(self):
        token, second = self.token(), self.token()
        self.assertEqual(self.submit(token).status_code, 200)
        self.assertEqual(self.submit(second).status_code, 400)
        from .recurring import create_agreement
        with self.assertRaises(ValidationError):
            create_agreement(workspace_id=self.workspace.pk, actor=self.owner, binding_id=self.binding.pk,
                total_count=12, request_key=uuid4())
        self.provider_create.assert_not_called()
        self.create_order.assert_called_once()

    def test_saved_consent_rechecks_publication_scope_owner_and_offer(self):
        token = self.token()
        for config in ({'BILLING_PUBLIC_PREPAID_PLAN_ID': 0}, {'BILLING_PREPAID_WORKSPACE_IDS': ['bad']},
                       {'BILLING_PREPAID_WORKSPACE_IDS': [str(self.workspace.pk + 1)]},
                       {'BILLING_SELLER_NAME': 'Changed'}, {'BILLING_TAX_RATE': '18'},
                       {'RAZORPAY_KEY_ID': 'rzp_test_wrong'}):
            with self.subTest(config=config), override_settings(**config):
                self.assertIn(self.submit(token).status_code, (400, 403))
        self.client.force_login(self.admin)
        self.assertEqual(self.submit(token).status_code, 403)
        self.client.force_login(self.owner)
        EmailAddress.objects.filter(user=self.owner).update(verified=False)
        self.assertEqual(self.submit(token).status_code, 400)
        self.create_order.assert_not_called()
        self.assertFalse(Invoice.objects.exists())

    def test_consent_csrf_expiry_tampering_and_post_only(self):
        token = self.token()
        self.assertEqual(self.submit(token, accepted_terms='').status_code, 400)
        self.assertEqual(self.submit(token + 'tampered').status_code, 400)
        with patch('django.core.signing.time.time', return_value=timezone.now().timestamp() + 1801):
            self.assertEqual(self.submit(token).status_code, 400)
        self.assertEqual(self.client.get(self.start_url).status_code, 405)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.owner)
        self.assertEqual(browser.post(self.start_url, {}).status_code, 403)
        self.create_order.assert_not_called()

    def test_live_trial_cannot_be_shortened_and_lifecycle_capacity_rechecked(self):
        token = self.token()
        subscription = self.trial(active=True)
        before = subscription.trial_end_date
        self.assertEqual(self.submit(token).status_code, 400)
        subscription.refresh_from_db()
        self.assertEqual(subscription.trial_end_date, before)
        Subscription.objects.filter(pk=subscription.pk).update(trial_end_date=timezone.now() - timedelta(days=1))
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state='SUSPENDED')
        self.assertEqual(self.submit(token).status_code, 400)
        Company.all_objects.filter(pk=self.workspace.pk).update(lifecycle_state='ACTIVE')
        with patch('apps.subscriptions.public_prepaid.get_workspace_member_usage', return_value=7):
            self.assertEqual(self.submit(token).status_code, 400)
        self.create_order.assert_not_called()

    def test_unsettled_failed_or_captured_attempt_cannot_open_checkout_again(self):
        token = self.token()
        self.assertEqual(self.submit(token).status_code, 200)
        for status in ['created', 'authorized', 'captured', 'failed']:
            self.attempts.return_value = {'entity': 'collection', 'count': 1, 'items': [{'status': status}]}
            self.assertEqual(self.submit(token).status_code, 400)
        self.create_order.assert_called_once()

    def test_recovery_while_paused_and_annual_renewal_preserves_paid_time(self):
        self.assertEqual(self.submit().status_code, 200)
        invoice = Invoice.objects.get()
        with override_settings(BILLING_PUBLIC_PREPAID_PLAN_ID=0):
            _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
        end = Subscription.objects.get().end_date
        self.assertEqual(self.submit().status_code, 200)
        next_invoice = Invoice.objects.order_by('-pk').first()
        _apply_capture(invoice_id=next_invoice.pk, payment=self.payment(next_invoice))
        self.assertEqual(Subscription.objects.get().end_date, end + relativedelta(years=1))
        self.assertEqual(Payment.objects.count(), 2)

    def test_wrong_amount_order_signature_or_revision_never_grants_access(self):
        self.submit()
        invoice = Invoice.objects.get()
        for changes in ({'amount': 149900}, {'currency': 'USD'}, {'order_id': 'order_other'},
                        {'status': 'authorized'}, {'amount_refunded': 1}):
            with self.assertRaises(ValidationError):
                _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice, **changes))
        with workspace_context(self.workspace.pk), self.assertRaises(ValidationError):
            confirm_checkout(workspace=self.workspace, actor=self.owner, order_id=invoice.razorpay_order_id,
                payment_id='pay_fake', signature='forged')
        Subscription.objects.filter(pk=invoice.subscription_id).update(updated_at=timezone.now())
        with self.assertRaises(ValidationError):
            _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
        self.assertFalse(Payment.objects.exists())

    def test_signed_webhook_and_browser_confirmation_share_one_paid_year(self):
        self.submit()
        invoice = Invoice.objects.get()
        payment = self.payment(invoice)
        body = json.dumps({'event': 'payment.captured', 'payload': {'payment': {'entity': payment}}}).encode()
        signature = hmac.new(b'webhook-fixture', body, hashlib.sha256).hexdigest()
        for event_id in ['evt_annual', 'evt_annual', 'evt_annual2']:
            response = self.client.post('/subscriptions/webhook/razorpay/', body, content_type='application/json',
                HTTP_X_RAZORPAY_SIGNATURE=signature, HTTP_X_RAZORPAY_EVENT_ID=event_id)
            self.assertEqual(response.status_code, 200)
        signature = hmac.new(b'fixture', (invoice.razorpay_order_id + '|' + payment['id']).encode(), hashlib.sha256).hexdigest()
        with patch.object(RazorpayService, 'get_payment_status', return_value=payment), workspace_context(self.workspace.pk):
            confirm_checkout(workspace=self.workspace, actor=self.owner, order_id=invoice.razorpay_order_id,
                payment_id=payment['id'], signature=signature)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(Delivery.objects.count(), 1)

    def test_cross_workspace_owner_transfer_and_membership_removal(self):
        token = self.token()
        data = signing.loads(token, salt=prepaid.SALT)
        other = Company.all_objects.create(name='Other', schema_name='annual_other', owner=self.admin, creator=self.admin)
        wrong = signing.dumps({**data, 'workspace_id': other.pk}, salt=prepaid.SALT)
        self.assertEqual(self.submit(wrong).status_code, 403)
        Membership.objects.filter(company=self.workspace, user=self.owner).delete()
        self.assertEqual(self.submit(token).status_code, 403)
        self.create_order.assert_not_called()

    def test_cohort_controls_navigation_without_enabling_generic_checkout(self):
        urls = [self.url, reverse('workspace_subscriptions:plan-list', kwargs={'workspace_slug': self.workspace.slug}),
            reverse('workspace_subscriptions:dashboard', kwargs={'workspace_slug': self.workspace.slug}),
            reverse('workspace_subscriptions:recurring', kwargs={'workspace_slug': self.workspace.slug})]
        with override_settings(BILLING_PREPAID_WORKSPACE_IDS=[str(self.workspace.pk)]):
            for url in urls:
                self.assertContains(self.client.get(url), '14,990')
        with override_settings(BILLING_PREPAID_WORKSPACE_IDS=[str(self.workspace.pk + 1)]):
            for url in urls:
                self.assertNotContains(self.client.get(url), '14,990')

    def test_capture_atomic_rollback_then_retry(self):
        self.submit()
        invoice = Invoice.objects.get()
        with patch('apps.subscriptions.checkout.ensure_entitlements_for_subscription', side_effect=ValidationError('mock')):
            with self.assertRaises(ValidationError):
                _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
        self.assertFalse(Payment.objects.exists())
        self.assertFalse(Delivery.objects.exists())
        _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
        self.assertEqual(Payment.objects.count(), 1)

    def test_unknown_order_can_be_bound_by_read_only_provider_recovery(self):
        original = self.create_order.side_effect
        def timeout(**kw):
            original(**kw)
            raise BillingProviderError('Response lost')
        self.create_order.side_effect = timeout
        self.assertEqual(self.submit().status_code, 400)
        invoice = Invoice.objects.get()
        order_id = next(iter(self.orders))
        for _ in range(2):
            recovered = prepaid.reconcile_order(workspace_id=self.workspace.pk, actor=self.admin,
                invoice_id=invoice.pk, order_id=order_id, reason='Located unique saved receipt in provider')
            self.assertEqual(recovered.razorpay_order_id, order_id)
        self.create_order.assert_called_once()
        self.assertEqual(SubscriptionEvent.objects.filter(event_type='prepaid.order_reconciled').count(), 1)
        self.assertFalse(Payment.objects.exists())

    def test_public_annual_pricing_only_after_scope_is_removed(self):
        self.client.logout()
        for scope, visible in (([str(self.workspace.pk)], False), ([], True)):
            with override_settings(BILLING_PREPAID_WORKSPACE_IDS=scope):
                for url in ('/', reverse('pricing'), reverse('faq')):
                    page = self.client.get(url)
                    if visible: self.assertContains(page, '14,990')
                    else: self.assertNotContains(page, '14,990')

    def test_restricted_runtime_can_create_and_capture_without_workspace_leak(self):
        role = connection.ops.quote_name('annual_test_' + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}')
        try:
            with connection.cursor() as cursor: cursor.execute(f'SET ROLE {role}')
            self.assertEqual(self.submit().status_code, 200)
            invoice = Invoice.objects.get()
            _apply_capture(invoice_id=invoice.pk, payment=self.payment(invoice))
            self.assertIsNone(current_workspace_id())
            self.assertFalse(connection.in_atomic_block)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute(f'DROP OWNED BY {role}')
                cursor.execute(f'DROP ROLE {role}')

    def test_simultaneous_reviews_reserve_one_provider_order(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import close_old_connections, connections
        reviews = [signing.loads(self.token(), salt=prepaid.SALT) for _ in range(2)]
        barrier = Barrier(2)
        def submit(consent):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                try:
                    return prepaid.prepare_purchase(workspace_id=self.workspace.pk,
                        actor=self.owner, consent=consent).pk
                except ValidationError:
                    return None
            finally: connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, reviews))
        self.assertEqual(sum(result is not None for result in results), 1)
        self.assertEqual(Invoice.objects.count(), 1)
        self.create_order.assert_called_once()
