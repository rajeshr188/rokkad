import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import CollateralMetal, LoanDocumentKind, LoanOutboxStatus, TransactionKind
from apps.tenant_apps.loans.models import LoanLicense, LoanNumberSequence, LoanSeries, PawnLoanAccountingEvent, PawnLoanAccountingOutbox
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    DeliveryReceipt,
    LoanAccountingOutboxError,
    create_pawn_draft,
    deliver_outbox_event,
    record_loan_accounting_event,
    retry_failed_outbox_event,
)
from apps.tenant_apps.party.models import Party


class AccountingOutboxServiceTests(TenantTestCase):
    test_schema_name = f"loans_outbox_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-outbox-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-outbox-owner",
            defaults={"email": "loans-outbox-owner@example.com"},
        )
        tenant.name = f"Loans Outbox {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = get_user_model().objects.create_user(
            username=f"outbox-{uuid.uuid4().hex[:8]}",
            email=f"outbox-{uuid.uuid4().hex[:8]}@example.com",
        )
        borrower = Party.objects.create(display_name="Outbox Borrower")
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Outbox License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
        LoanNumberSequence.objects.create(series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value, prefix="PL-A-", width=5, maximum_number=10000)
        self.loan = create_pawn_draft(
            CreatePawnDraftCommand(
                workspace_id=self.tenant.pk, borrower_id=borrower.pk,
                license_id=license.pk, series_id=series.pk,
                principal_amount=Decimal("50000.00"), monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 7, 30), tenure_months=3,
                collateral=(CollateralDraftInput(description="Gold", metal=CollateralMetal.GOLD, gross_weight=Decimal("10"), net_weight=Decimal("9"), purity_percentage=Decimal("91.6"), latest_appraised_value=Decimal("50000")),),
            ), actor=self.actor,
        )
        self.payload = {"loan_number": self.loan.loan_number, "principal_amount": "50000.00"}

    def test_source_event_and_outbox_are_created_atomically_with_deterministic_key(self):
        event, outbox = record_loan_accounting_event(
            self.loan.pk, event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 7, 30), payload=self.payload, actor=self.actor,
        )
        repeat_event, repeat_outbox = record_loan_accounting_event(
            self.loan.pk, event_kind="DISBURSAL",
            effective_date=date(2026, 7, 30), payload=dict(reversed(list(self.payload.items()))), actor=self.actor,
        )

        self.assertEqual(event.pk, repeat_event.pk)
        self.assertEqual(outbox.pk, repeat_outbox.pk)
        self.assertEqual(PawnLoanAccountingEvent.objects.count(), 1)
        self.assertEqual(PawnLoanAccountingOutbox.objects.count(), 1)
        self.assertEqual(event.idempotency_key, outbox.idempotency_key)
        self.assertEqual(event.payload_fingerprint, outbox.payload_fingerprint)

    @patch(
        "apps.tenant_apps.loans.services.accounting_outbox.is_dea_integration_enabled",
        return_value=False,
    )
    @patch("apps.tenant_apps.loans.services.accounting_outbox.deliver_outbox_event")
    def test_deferred_mode_retains_pending_event_without_delivery_attempt(
        self,
        deliver,
        _integration_enabled,
    ):
        _event, outbox = record_loan_accounting_event(
            self.loan.pk,
            event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 7, 30),
            payload=self.payload,
            actor=self.actor,
        )

        outbox.refresh_from_db()
        self.assertEqual(outbox.status, LoanOutboxStatus.PENDING.value)
        self.assertEqual(outbox.attempt_count, 0)
        self.assertIsNone(outbox.dea_voucher_id)
        self.assertIsNone(outbox.dea_journal_entry_id)
        deliver.assert_not_called()

    @patch(
        "apps.tenant_apps.loans.services.accounting_outbox.is_dea_integration_enabled",
        return_value=False,
    )
    @patch("apps.tenant_apps.loans.services.accounting_outbox._default_delivery")
    def test_deferred_mode_blocks_direct_default_delivery(self, default_delivery, _enabled):
        _event, outbox = record_loan_accounting_event(
            self.loan.pk,
            event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 7, 30),
            payload=self.payload,
            actor=self.actor,
        )

        delivered = deliver_outbox_event(outbox.pk)

        self.assertEqual(delivered.status, LoanOutboxStatus.PENDING.value)
        self.assertEqual(delivered.attempt_count, 0)
        default_delivery.assert_not_called()

    def test_failed_delivery_is_observable_and_admin_retry_can_post_once(self):
        _event, outbox = record_loan_accounting_event(
            self.loan.pk, event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 7, 30), payload=self.payload,
        )
        failed = deliver_outbox_event(outbox.pk, delivery_handler=lambda event: (_ for _ in ()).throw(RuntimeError("DEA unavailable")))
        self.assertEqual(failed.status, LoanOutboxStatus.FAILED.value)
        self.assertEqual(failed.attempt_count, 1)
        self.assertIn("DEA unavailable", failed.last_error)

        retry_failed_outbox_event(
            outbox.pk,
        )
        deliver_outbox_event(
            outbox.pk,
            delivery_handler=lambda event: DeliveryReceipt(
                dea_voucher_id=17, dea_journal_entry_id=23
            ),
        )
        outbox.refresh_from_db()
        self.assertEqual(outbox.status, LoanOutboxStatus.POSTED.value)
        self.assertEqual(outbox.attempt_count, 2)
        self.assertEqual((outbox.dea_voucher_id, outbox.dea_journal_entry_id), (17, 23))
        self.assertEqual(deliver_outbox_event(outbox.pk).attempt_count, 2)

    def test_invalid_payload_and_non_failed_retry_fail_closed(self):
        with self.assertRaises(LoanAccountingOutboxError):
            record_loan_accounting_event(
                self.loan.pk, event_kind=TransactionKind.DISBURSAL,
                effective_date=date(2026, 7, 30), payload={},
            )
        _event, outbox = record_loan_accounting_event(
            self.loan.pk, event_kind=TransactionKind.DISBURSAL,
            effective_date=date(2026, 7, 30), payload=self.payload,
        )
        with self.assertRaises(LoanAccountingOutboxError):
            retry_failed_outbox_event(outbox.pk)

    def test_outbox_persistence_failure_rolls_back_source_event(self):
        with patch(
            "apps.tenant_apps.loans.services.accounting_outbox.PawnLoanAccountingOutbox.objects.get_or_create",
            side_effect=RuntimeError("outbox unavailable"),
        ):
            with self.assertRaises(RuntimeError):
                record_loan_accounting_event(
                    self.loan.pk,
                    event_kind=TransactionKind.DISBURSAL,
                    effective_date=date(2026, 7, 30),
                    payload=self.payload,
                )
        self.assertEqual(PawnLoanAccountingEvent.objects.count(), 0)
        self.assertEqual(PawnLoanAccountingOutbox.objects.count(), 0)
