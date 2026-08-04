import uuid
from datetime import date, timedelta
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.core.management import call_command
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import (
    LoanOutboxStatus,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanNoticeStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import PawnNoticeDeliveryReceipt
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanSeries,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanNotice,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_notice_rows
from apps.tenant_apps.loans.services import (
    PawnLoanNoticeError,
    create_pawn_loan_notice,
    dispatch_due_pawn_loan_notices,
    dispatch_pawn_loan_notice,
)
from apps.tenant_apps.notify_v2.models import NotificationEvent, NotificationJob
from apps.tenant_apps.party.models import Party


class PawnLoanNoticeTests(TenantTestCase):
    test_schema_name = f"loans_notices_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-notices-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-notice-owner",
            defaults={"email": "loans-notice-owner@example.com"},
        )
        tenant.name = f"Loans Notices {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = get_user_model().objects.create_user(
            username=f"notice-{uuid.uuid4().hex[:8]}",
            email=f"notice-{uuid.uuid4().hex[:8]}@example.com",
        )
        borrower = Party.objects.create(
            display_name="Notice Borrower",
            primary_email="borrower@example.com",
            primary_phone="+919999999999",
        )
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Notice License",
            license_number=f"NOTICE-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="N")
        self.loan = PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            borrower=borrower,
            loan_number=f"PL-N-{uuid.uuid4().hex[:6]}",
            state=PawnLoanState.ACTIVE.value,
            principal_amount=Decimal("50000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=timezone.localdate() - timedelta(days=10),
            tenure_months=3,
            created_by=self.actor,
            updated_by=self.actor,
        )
        event = PawnLoanAccountingEvent.objects.create(
            loan=self.loan,
            event_kind=TransactionKind.DISBURSAL.value,
            effective_date=self.loan.loan_date,
            payload={"values": {"principal": "50000", "interest": "0", "fees": "0"}},
            payload_fingerprint="d" * 64,
            idempotency_key=f"notice-disbursal-{uuid.uuid4().hex}",
            created_by=self.actor,
        )
        PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key=f"notice-outbox-{uuid.uuid4().hex}",
            payload=event.payload,
            payload_fingerprint=event.payload_fingerprint,
            status=LoanOutboxStatus.POSTED.value,
        )

    def test_notice_intent_creates_notify_job_without_duplicating_delivery_state(self):
        notice = self._create_notice()

        self.assertTrue(NotificationEvent.objects.filter(pk=notice.notification_event_id).exists())
        job = NotificationJob.objects.get(pk=notice.notification_job_id)
        self.assertEqual(job.status, NotificationJob.Status.QUEUED)
        self.assertEqual(job.event.source_app, "loans")
        self.assertEqual(job.event.source_model, "PawnLoan")
        self.assertEqual(job.event.source_pk, str(self.loan.pk))
        self.assertEqual(notice.payload_snapshot["loans"][0]["total_due"], "50000.00")
        model_fields = {field.name for field in PawnLoanNotice._meta.fields}
        self.assertFalse(
            {"status", "sent_at", "failure_reason", "external_reference"} & model_fields
        )

    def test_request_key_is_idempotent_and_conflicting_reuse_fails(self):
        first = self._create_notice(request_key="same-request")
        repeat = self._create_notice(request_key="same-request")

        self.assertEqual(repeat.pk, first.pk)
        self.assertEqual(PawnLoanNotice.objects.count(), 1)
        self.assertEqual(NotificationJob.objects.count(), 1)
        with self.assertRaises(PawnLoanNoticeError):
            self._create_notice(
                request_key="same-request",
                channel=PawnLoanNoticeChannel.SMS,
            )

    def test_auction_and_ineligible_overdue_notice_fail_closed(self):
        with self.assertRaisesRegex(PawnLoanNoticeError, "source auction"):
            self._create_notice(notice_kind=PawnLoanNoticeKind.AUCTION_NOTICE)
        with self.assertRaisesRegex(PawnLoanNoticeError, "not overdue"):
            self._create_notice(notice_kind=PawnLoanNoticeKind.OVERDUE_NOTICE)

        self.assertFalse(PawnLoanNotice.objects.exists())
        self.assertFalse(NotificationJob.objects.exists())

    def test_dispatch_result_and_detail_row_derive_status_from_notify(self):
        notice = self._create_notice()
        sent_at = timezone.now()
        result = dispatch_pawn_loan_notice(
            notice.pk,
            delivery_handler=lambda _job_id: PawnNoticeDeliveryReceipt(
                status=PawnLoanNoticeStatus.SENT.value,
                external_reference="mock-123",
                sent_at=sent_at,
            ),
        )

        self.assertEqual(result.notice.pk, notice.pk)
        self.assertEqual(result.delivery.external_reference, "mock-123")
        job = NotificationJob.objects.get(pk=notice.notification_job_id)
        job.provider_message_id = "notify-456"
        job.status = NotificationJob.Status.SENT
        job.sent_at = sent_at
        job.save(update_fields=["provider_message_id", "status", "sent_at", "modified"])
        row = get_pawn_loan_notice_rows(self.loan)[0]
        self.assertEqual(row.status, PawnLoanNoticeStatus.SENT.value)
        self.assertEqual(row.external_reference, "notify-456")
        duplicate_handler = Mock()
        repeated = dispatch_pawn_loan_notice(
            notice.pk,
            delivery_handler=duplicate_handler,
        )
        self.assertEqual(repeated.delivery.status, PawnLoanNoticeStatus.SENT.value)
        duplicate_handler.assert_not_called()

    def test_scheduler_uses_as_of_and_only_dispatches_notify_queued_jobs(self):
        future = timezone.now() + timedelta(days=2)
        notice = self._create_notice(scheduled_for=future)

        with patch(
            "apps.tenant_apps.loans.services.pawn_notices.deliver_pawn_notice_job",
            return_value=PawnNoticeDeliveryReceipt(
                status=PawnLoanNoticeStatus.SENT.value,
                external_reference="scheduled-1",
                sent_at=future,
            ),
        ) as delivery:
            summary = dispatch_due_pawn_loan_notices(as_of=future, limit=10)

        self.assertEqual(summary.due_count, 1)
        self.assertEqual(summary.sent_count, 1)
        self.assertEqual(summary.failed_count, 0)
        delivery.assert_called_once_with(notice.notification_job_id)

    def test_dispatch_command_reports_tenant_scheduler_summary(self):
        output = StringIO()
        with patch(
            "apps.tenant_apps.loans.management.commands.dispatch_pawn_loan_notices.dispatch_due_pawn_loan_notices",
            return_value=SimpleNamespace(due_count=2, sent_count=1, failed_count=1),
        ) as scheduler:
            call_command(
                "dispatch_pawn_loan_notices",
                as_of="2026-08-06T10:00:00+05:30",
                limit=25,
                stdout=output,
            )

        self.assertIn("due=2, sent=1, failed=1", output.getvalue())
        scheduler.assert_called_once()
        self.assertEqual(scheduler.call_args.kwargs["limit"], 25)

    def _create_notice(
        self,
        *,
        request_key=None,
        notice_kind=PawnLoanNoticeKind.REPAYMENT_REMINDER,
        channel=PawnLoanNoticeChannel.EMAIL,
        scheduled_for=None,
    ):
        return create_pawn_loan_notice(
            self.loan.pk,
            notice_kind=notice_kind,
            channel=channel,
            request_key=request_key or uuid.uuid4().hex,
            scheduled_for=scheduled_for,
            actor=self.actor,
            dispatch_due=False,
        )
