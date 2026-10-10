from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.test import TransactionTestCase, override_settings

from .models import Invoice, Payment, RecurringAgreement, RecurringAgreementEvent
from .razorpay_service import BillingProviderError, RazorpayService
from .recurring import create_agreement
from . import test_live_recurring as live_tests
from .test_public_prepaid import SETTINGS
from .unpaid_agreement import release_unused_agreement


@override_settings(**SETTINGS)
class UnpaidAgreementTests(TransactionTestCase):
    created_entity = live_tests.LiveCreationTests.created_entity

    def setUp(self):
        live_tests.LiveCreationTests.setUp(self)
        self.agreement = create_agreement(workspace_id=self.workspace.pk, actor=self.owner,
            binding_id=self.binding.pk, total_count=12, request_key=uuid4())
        self.provider = {**self.agreement.request_snapshot, 'id': self.agreement.provider_subscription_id,
            'entity': 'subscription', 'status': 'cancelled', 'has_scheduled_changes': False,
            'paid_count': 0, 'auth_attempts': 0, 'charge_at': None, 'start_at': None,
            'current_start': None, 'current_end': None}
        self.invoice = {'id': 'inv_unused', 'entity': 'invoice', 'subscription_id': self.provider['id'],
            'order_id': 'order_unused', 'status': 'issued', 'amount_paid': 0, 'payment_id': None, 'paid_at': None}
        self.failed = {'id': 'pay_failed', 'status': 'failed', 'order_id': 'order_unused', 'amount_refunded': 0}
        self.read = patch.object(RazorpayService, 'get_subscription', side_effect=lambda _: deepcopy(self.provider)).start()
        self.listing = patch.object(RazorpayService, 'get_subscription_invoices', side_effect=lambda _, skip=0:
            {'entity': 'collection', 'count': 0 if skip else 1, 'items': [] if skip else [deepcopy(self.invoice)]}).start()
        self.attempts = patch.object(RazorpayService, 'get_order_payments', side_effect=lambda _:
            {'entity': 'collection', 'count': 1, 'items': [deepcopy(self.failed)]}).start()
        def cancel(identity):
            self.assertFalse(connection.in_atomic_block)
            self.assertTrue(self.agreement.events.filter(event_type='unused_invoice.cancel_dispatched').exists())
            self.invoice['status'] = 'cancelled'
            return deepcopy(self.invoice)
        self.cancel = patch.object(RazorpayService, 'cancel_invoice', side_effect=cancel).start()

    def release(self, **changes):
        return release_unused_agreement(**{'workspace_id': self.workspace.pk, 'actor': self.owner,
            'agreement_id': self.agreement.pk, 'reason': 'Owner chose annual prepayment', **changes})

    def test_release_cancels_unpaid_invoice_once_keeps_history_and_no_access(self):
        result = self.release()
        self.assertEqual(self.release().pk, result.pk)
        self.cancel.assert_called_once_with('inv_unused')
        self.agreement.refresh_from_db()
        self.assertIsNotNone(self.agreement.closed_at)
        self.assertEqual(result.detail['invoices'][0]['failed_payments'], ['pay_failed'])
        self.assertFalse(Invoice.objects.exists())
        self.assertFalse(Payment.objects.exists())

    def test_authorized_or_paid_or_scheduled_provider_never_releases(self):
        for changes in ({'auth_attempts': 1}, {'paid_count': 1}, {'status': 'created'},
                        {'charge_at': 1}, {'current_start': 1}, {'start_at': 1}):
            old = deepcopy(self.provider)
            self.provider.update(changes)
            with self.assertRaises(ValidationError): self.release()
            self.provider = old
        self.cancel.assert_not_called()
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.closed_at)

    def test_pending_or_authorized_payment_blocks_invoice_cancellation_and_release(self):
        for status in ('created', 'authorized', 'captured', 'refunded'):
            self.failed['status'] = status
            with self.assertRaises(ValidationError): self.release()
        self.cancel.assert_not_called()

    def test_unknown_cancellation_fetches_only_and_never_reposts(self):
        self.cancel.side_effect = BillingProviderError('Mock timeout')
        with self.assertRaises(BillingProviderError): self.release()
        with self.assertRaises(ValidationError): self.release()
        self.cancel.assert_called_once()
        self.invoice['status'] = 'cancelled'
        self.release()
        self.cancel.assert_called_once()

    def test_incomplete_or_foreign_invoice_listing_keeps_reservation(self):
        self.invoice['subscription_id'] = 'sub_other'
        with self.assertRaises(ValidationError): self.release()
        self.cancel.assert_not_called()
        self.listing.side_effect = None
        self.listing.return_value = {'entity': 'collection', 'count': 2, 'items': []}
        with self.assertRaises(ValidationError): self.release()

    def test_provider_identity_and_mode_rechecked_before_mutation(self):
        self.provider['id'] = 'sub_other'
        with self.assertRaises(ValidationError): self.release()
        self.cancel.assert_not_called()
        with override_settings(RAZORPAY_KEY_ID='rzp_test_wrong'), self.assertRaises(PermissionDenied):
            self.release()

    def test_local_authorization_evidence_or_nonowner_prevents_release(self):
        RecurringAgreementEvent.objects.create(agreement=self.agreement, actor=self.owner,
            event_type='authorization.verified', detail={'payment_id': 'pay_unknown'})
        with self.assertRaises(ValidationError): self.release()
        self.read.assert_not_called()
        self.cancel.assert_not_called()

    def test_provider_status_changes_during_review_prevent_release(self):
        original = self.cancel.side_effect
        def changed(identity):
            result = original(identity)
            self.provider['auth_attempts'] = 1
            return result
        self.cancel.side_effect = changed
        with self.assertRaises(ValidationError): self.release()
        self.agreement.refresh_from_db()
        self.assertIsNone(self.agreement.closed_at)
