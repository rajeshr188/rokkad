from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.dea.facades.payments import (
    create_and_post_payment,
    reverse_payment_by_marker,
)


class CreateAndPostPaymentIdempotencyTests(SimpleTestCase):
    def _call(self):
        return create_and_post_payment(
            SimpleNamespace(pk=10),
            direction="PAYMENT",
            payment_type="DISBURSAL",
            total_amount="1000 INR",
            amount_in_base_currency="1000 INR",
            payment_date="2026-06-16",
            reference_number="DISBURSAL-GIVENLOAN-10",
            description="Disbursal",
            created_by=SimpleNamespace(id=1),
        )

    @patch("apps.tenant_apps.dea.facades.payments.DjangoPostingEngine")
    @patch("apps.tenant_apps.dea.facades.payments.create_and_post_voucher_for_doc")
    @patch("apps.tenant_apps.dea.facades.payments.PaymentVoucher")
    @patch("apps.tenant_apps.dea.facades.payments.ContentType")
    def test_existing_unposted_payment_is_posted_on_retry(
        self,
        mock_content_type,
        mock_payment_voucher,
        mock_post,
        mock_engine,
    ):
        existing = MagicMock(posted=False)
        existing.get_voucher_type.return_value = "GIVENLOAN_PAYMENT"
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = existing

        payment, created = self._call()

        self.assertEqual(payment, existing)
        self.assertFalse(created)
        mock_post.assert_called_once()
        self.assertTrue(existing.posted)
        existing.save.assert_called_once_with(update_fields=["posted"])

    @patch("apps.tenant_apps.dea.facades.payments.create_and_post_voucher_for_doc")
    @patch("apps.tenant_apps.dea.facades.payments.PaymentVoucher")
    @patch("apps.tenant_apps.dea.facades.payments.ContentType")
    def test_existing_posted_payment_is_returned_without_reposting(
        self,
        mock_content_type,
        mock_payment_voucher,
        mock_post,
    ):
        existing = MagicMock(posted=True)
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = existing

        payment, created = self._call()

        self.assertEqual(payment, existing)
        self.assertFalse(created)
        mock_post.assert_not_called()


class ReversePaymentByMarkerTests(SimpleTestCase):
    @patch("apps.tenant_apps.dea.facades.payments.reverse_posted_voucher")
    @patch("apps.tenant_apps.dea.facades.payments.Voucher")
    @patch("apps.tenant_apps.dea.facades.payments.PaymentVoucher")
    @patch("apps.tenant_apps.dea.facades.payments.ContentType")
    def test_reverse_payment_by_marker_uses_reversal_service(
        self,
        mock_content_type,
        mock_payment_voucher,
        mock_voucher,
        mock_reverse,
    ):
        source = SimpleNamespace(pk=10)
        user = SimpleNamespace(id=1)
        payment = MagicMock(pk=20, posted=True)
        accounting_voucher = MagicMock(pk=30)
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = payment
        mock_voucher.objects.get.return_value = accounting_voucher

        result = reverse_payment_by_marker(source, "marker-1", user)

        self.assertEqual(result, payment)
        mock_reverse.assert_called_once_with(
            voucher=accounting_voucher,
            actor=user,
            reason="Reverse payment marker marker-1",
            source_action="payment_marker_reversal",
        )
        self.assertFalse(payment.posted)
        payment.save.assert_called_once_with(update_fields=["posted"])

    @patch("apps.tenant_apps.dea.facades.payments.Voucher")
    @patch("apps.tenant_apps.dea.facades.payments.PaymentVoucher")
    @patch("apps.tenant_apps.dea.facades.payments.ContentType")
    def test_reverse_payment_by_marker_requires_posted_accounting_voucher(
        self,
        mock_content_type,
        mock_payment_voucher,
        mock_voucher,
    ):
        source = SimpleNamespace(pk=10)
        payment = MagicMock(pk=20, posted=True)
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = payment
        mock_voucher.DoesNotExist = Exception
        mock_voucher.objects.get.side_effect = mock_voucher.DoesNotExist

        with self.assertRaisesRegex(ValueError, "No POSTED accounting voucher"):
            reverse_payment_by_marker(source, "marker-1", SimpleNamespace(id=1))
