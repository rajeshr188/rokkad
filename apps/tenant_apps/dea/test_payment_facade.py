from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.dea.facades.payments import create_and_post_payment


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
