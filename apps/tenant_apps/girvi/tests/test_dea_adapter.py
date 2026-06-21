from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.integrations import dea_adapter


class GirviDeaAdapterTests(SimpleTestCase):
    def tearDown(self):
        dea_adapter.dea_facade = None

    def test_payment_posting_delegates_to_dea_facade(self):
        facade = MagicMock()
        facade.create_and_post_payment.return_value = ("payment", True)
        dea_adapter.dea_facade = facade
        loan = SimpleNamespace(pk=1)

        result = dea_adapter.create_and_post_voucher_for_doc(
            loan,
            direction="RECEIPT",
            total_amount=100,
        )

        self.assertEqual(result, ("payment", True))
        facade.create_and_post_payment.assert_called_once_with(
            loan,
            direction="RECEIPT",
            total_amount=100,
        )

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.apps.get_model")
    def test_create_payment_voucher_uses_dea_payment_model(self, mock_get_model):
        payment_voucher = MagicMock()
        created_payment = SimpleNamespace(payment_id="PAY-001")
        payment_voucher.objects.create.return_value = created_payment
        mock_get_model.return_value = payment_voucher
        loan = SimpleNamespace(pk=1)

        result = dea_adapter.create_payment_voucher(
            loan,
            direction="RECEIPT",
            total_amount=100,
        )

        self.assertEqual(result, created_payment)
        mock_get_model.assert_called_once_with("dea", "PaymentVoucher")
        payment_voucher.objects.create.assert_called_once_with(
            source_document=loan,
            direction="RECEIPT",
            total_amount=100,
        )

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.apps.get_model")
    def test_payment_voucher_counts_use_dea_payment_model(self, mock_get_model):
        payment_voucher = MagicMock()
        payment_voucher.objects.count.return_value = 7
        payment_voucher.objects.filter.return_value.count.return_value = 2
        mock_get_model.return_value = payment_voucher

        result = dea_adapter.get_payment_voucher_counts()

        self.assertEqual(result, {"total_payments": 7, "pending_payments": 2})
        mock_get_model.assert_called_once_with("dea", "PaymentVoucher")
        payment_voucher.objects.filter.assert_called_once_with(posted=False)

    def test_interest_accrual_delegates_to_dea_facade(self):
        facade = MagicMock()
        facade.post_interest_accrual_batch.return_value = ("journal", "voucher", "entry")
        dea_adapter.dea_facade = facade
        command = SimpleNamespace()
        preview = SimpleNamespace()
        rows = [SimpleNamespace(pk=1)]

        result = dea_adapter.post_interest_accrual_batch(
            command,
            preview,
            rows,
            posted_status_value="POSTED",
        )

        self.assertEqual(result, ("journal", "voucher", "entry"))
        facade.post_interest_accrual_batch.assert_called_once_with(
            command,
            preview,
            rows,
            posted_status_value="POSTED",
        )
