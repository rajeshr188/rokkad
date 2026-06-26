from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from decimal import Decimal
from datetime import datetime

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.integrations import dea_adapter


class GirviDeaAdapterTests(SimpleTestCase):
    def tearDown(self):
        dea_adapter.dea_facade = None

    def _source_document(self, *, app="girvi", model="givenloan", pk=42):
        return SimpleNamespace(
            pk=pk,
            _meta=SimpleNamespace(app_label=app, model_name=model),
        )

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

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.apps.get_model")
    def test_get_payment_voucher_model_uses_lazy_model_lookup(self, mock_get_model):
        payment_voucher = MagicMock()
        mock_get_model.return_value = payment_voucher

        result = dea_adapter.get_payment_voucher_model()

        self.assertIs(result, payment_voucher)
        mock_get_model.assert_called_once_with("dea", "PaymentVoucher")

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.get_payment_voucher_model")
    def test_payment_voucher_posting_counts_use_adapter_model(self, mock_get_model):
        payment_voucher = MagicMock()
        payment_voucher.objects.count.return_value = 12
        payment_voucher.objects.filter.side_effect = [
            SimpleNamespace(count=lambda: 9),
            SimpleNamespace(count=lambda: 3),
        ]
        mock_get_model.return_value = payment_voucher

        result = dea_adapter.get_payment_voucher_posting_counts()

        self.assertEqual(result, {"total": 12, "posted": 9, "pending": 3})
        payment_voucher.objects.filter.assert_any_call(posted=True)
        payment_voucher.objects.filter.assert_any_call(posted=False)

    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.ContentType.objects.get_for_model")
    @patch("apps.tenant_apps.girvi.integrations.dea_adapter.get_payment_voucher_model")
    def test_source_posting_status_reports_pending_payment(self, mock_get_model, mock_content_type):
        source = self._source_document(model="givenloan", pk=42)
        mock_content_type.return_value = SimpleNamespace(pk=5)
        payment_qs = MagicMock()
        payment_qs.filter.side_effect = [
            SimpleNamespace(count=lambda: 0),
            SimpleNamespace(count=lambda: 1),
        ]
        payment_qs.count.return_value = 1
        payment_voucher = MagicMock()
        payment_voucher.objects.filter.return_value = payment_qs
        mock_get_model.return_value = payment_voucher

        status = dea_adapter.get_source_posting_status(source)

        self.assertEqual(status["label"], "Pending")
        self.assertEqual(status["badge_class"], "bg-warning text-dark")
        self.assertEqual(status["posted_payment_count"], 0)
        self.assertEqual(status["pending_payment_count"], 1)
        payment_voucher.objects.filter.assert_called_once_with(
            source_content_type=mock_content_type.return_value,
            source_object_id=42,
        )

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

    def test_reversal_delegates_to_dea_facade(self):
        facade = MagicMock()
        facade.reverse_payment_by_marker.return_value = "reversal"
        dea_adapter.dea_facade = facade
        source = self._source_document()
        user = SimpleNamespace(username="auditor")

        result = dea_adapter.reverse_payment_by_marker(source, "marker-1", user)

        self.assertEqual(result, "reversal")
        facade.reverse_payment_by_marker.assert_called_once_with(
            source,
            "marker-1",
            user,
        )

    def test_build_posting_event_payload_contains_contract_shape(self):
        source_document = self._source_document(model="givenloan", pk=42)

        payload = dea_adapter.build_posting_event_payload(
            event_key="disbursal",
            source_document=source_document,
            payload={
                "principal_amount": "1000.00",
                "posting_date": "2026-06-22",
            },
        )

        self.assertEqual(payload["contract_version"], dea_adapter.EVENT_CONTRACT_VERSION)
        self.assertEqual(payload["event_type"], "DISBURSAL")
        self.assertEqual(payload["event_key"], "disbursal")
        self.assertEqual(
            payload["idempotency_key"],
            "girvi:2:DISBURSAL:girvi:givenloan:42",
        )
        self.assertEqual(
            payload["source"],
            {
                "app": "girvi",
                "model": "givenloan",
                "pk": "42",
                "expected_model": "GivenLoan",
            },
        )
        self.assertEqual(payload["expected_dea_rule"], "given_loan_disbursal")
        self.assertEqual(payload["economic_payload"], payload["payload"])
        self.assertIn("principal_amount", payload["required_economic_fields"])
        self.assertIn("period locks", payload["posting_boundary"]["dea_owns"])

    def test_build_source_document_economic_payload_for_disbursal(self):
        loan = self._source_document(model="givenloan", pk=42)
        loan.loan_id = "GL-42"
        loan.loan_date = datetime(2026, 6, 22, 10, 30)
        loan.borrower = SimpleNamespace(pk=9)
        loan.get_loan_amount = lambda: Decimal("1000.00")
        loan.get_interest_amount = lambda: Decimal("20.00")

        payload = dea_adapter.build_source_document_economic_payload(
            event_key="disbursal",
            source_document=loan,
        )

        self.assertEqual(payload["source_ref"]["pk"], "42")
        self.assertEqual(payload["loan_id"], "GL-42")
        self.assertEqual(payload["principal_amount"], "1000.00")
        self.assertEqual(payload["interest_amount"], "20.00")
        self.assertEqual(payload["posting_date"], "2026-06-22T10:30:00")
        self.assertEqual(payload["party_id"], "9")

    def test_build_source_document_economic_payload_for_repayment(self):
        payment = self._source_document(app="dea", model="paymentvoucher", pk=8)
        payment.payment_id = "RCP-8"
        payment.direction = "RECEIPT"
        payment.amount_in_base_currency = Decimal("1100.00")
        payment.principal_amount = Decimal("1000.00")
        payment.interest_amount = Decimal("100.00")
        payment.payment_date = datetime(2026, 6, 22, 11, 0)
        payment.source_document = self._source_document(model="givenloan", pk=42)

        payload = dea_adapter.build_source_document_economic_payload(
            event_key="repayment",
            source_document=payment,
        )

        self.assertEqual(payload["payment_id"], "RCP-8")
        self.assertEqual(payload["direction"], "RECEIPT")
        self.assertEqual(payload["total_amount"], "1100.00")
        self.assertEqual(payload["principal_amount"], "1000.00")
        self.assertEqual(payload["interest_amount"], "100.00")
        self.assertEqual(payload["source_document_ref"]["model"], "givenloan")

    def test_build_source_document_economic_payload_for_release(self):
        loan = self._source_document(model="givenloan", pk=42)
        release = self._source_document(model="release", pk=3)
        release.release_id = "REL-3"
        release.loan = loan
        release.release_date = datetime(2026, 6, 22, 12, 0)
        settlement = SimpleNamespace(
            total_outstanding=Decimal("0.00"),
            principal_due=Decimal("0.00"),
            interest_due=Decimal("0.00"),
        )

        with patch(
            "apps.tenant_apps.girvi.selectors.build_loan_settlement_balance",
            return_value=settlement,
        ):
            payload = dea_adapter.build_source_document_economic_payload(
                event_key="release",
                source_document=release,
            )

        self.assertEqual(payload["release_id"], "REL-3")
        self.assertEqual(payload["loan_ref"]["model"], "givenloan")
        self.assertEqual(payload["settlement_amount"], "0.00")
        self.assertEqual(payload["release_date"], "2026-06-22T12:00:00")

    def test_build_posting_event_payload_can_derive_economic_payload(self):
        source_document = self._source_document(model="givenloan", pk=42)
        source_document.loan_id = "GL-42"
        source_document.get_loan_amount = lambda: Decimal("1000.00")
        source_document.get_interest_amount = lambda: Decimal("0.00")

        payload = dea_adapter.build_posting_event_payload(
            event_key="disbursal",
            source_document=source_document,
            payload=None,
        )

        self.assertEqual(payload["economic_payload"]["loan_id"], "GL-42")
        self.assertEqual(payload["economic_payload"]["principal_amount"], "1000.00")

    def test_build_posting_idempotency_key_rejects_unknown_event(self):
        with self.assertRaises(ValidationError):
            dea_adapter.build_posting_idempotency_key(
                event_key="unknown",
                source_document=self._source_document(),
            )

    def test_all_phase_five_event_contracts_have_dea_rule_and_economic_fields(self):
        expected_keys = {
            "disbursal",
            "taken_loan_activation",
            "repayment",
            "taken_loan_repayment",
            "release",
            "accrual",
            "auction_recovery",
            "sale_recovery",
            "renewal",
            "write_off",
            "reversal",
        }

        self.assertEqual(set(dea_adapter.GIRVI_POSTING_EVENT_TYPES), expected_keys)
        self.assertEqual(set(dea_adapter.GIRVI_POSTING_EVENT_CONTRACTS), expected_keys)
        for event_key, contract in dea_adapter.GIRVI_POSTING_EVENT_CONTRACTS.items():
            self.assertTrue(contract["source_model"], event_key)
            self.assertTrue(contract["expected_dea_rule"], event_key)
            self.assertTrue(contract["economic_fields"], event_key)

    @patch("apps.tenant_apps.girvi.integrations.outbox.enqueue_posting_event")
    def test_enqueue_posting_event_uses_contract_payload_and_dedupe_key(self, mock_enqueue):
        mock_enqueue.return_value = SimpleNamespace(pk=99)
        source_document = self._source_document(model="release", pk=7)

        result = dea_adapter.enqueue_posting_event(
            event_key="release",
            source_document=source_document,
            dedupe_key="release-7",
            payload={"release_date": "2026-06-22", "settlement_amount": "0.00"},
        )

        self.assertEqual(result.pk, 99)
        kwargs = mock_enqueue.call_args.kwargs
        self.assertEqual(kwargs["event_type"], "RELEASE")
        self.assertEqual(kwargs["dedupe_key"], "release-7")
        self.assertEqual(kwargs["payload"]["idempotency_key"], "release-7")
        self.assertEqual(kwargs["payload"]["expected_dea_rule"], "given_loan_release")
        self.assertEqual(kwargs["source_model"], "release")
        self.assertEqual(kwargs["source_pk"], "7")
