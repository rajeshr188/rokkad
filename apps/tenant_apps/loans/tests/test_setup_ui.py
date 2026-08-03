import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.tenant_apps.loans.access import assert_loans_setup_access
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
)
from apps.tenant_apps.loans.views import _license_for_workspace
from apps.tenant_apps.party.models import Party
from apps.orgs.models import Membership, Role


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class LoansSetupUiTests(TenantTestCase):
    test_schema_name = f"loans_setup_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-setup-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-setup-owner",
            defaults={"email": "loans-setup-owner@example.com"},
        )
        tenant.name = f"Loans Setup {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        static_url = patch(
            "django.templatetags.static.StaticNode.handle_simple",
            side_effect=lambda path: f"/static/{path}",
        )
        static_url.start()
        self.addCleanup(static_url.stop)
        self.owner = self.tenant.owner
        self.client = TenantClient(self.tenant)
        self.client.force_login(self.owner)

    def tenant_get(self, url):
        return self.client.get(url)

    def tenant_post(self, url, data=None):
        return self.client.post(url, data or {})

    def test_owner_can_complete_license_and_series_setup_without_admin(self):
        response = self.tenant_post(
            reverse("loans:license_create"),
            {
                "name": "Primary Pawn License",
                "license_number": "PBL-UI-1",
                "issuing_authority": "State Authority",
                "issued_on": "2026-01-01",
                "expires_on": "2027-01-01",
                "notes": "",
            },
        )
        license = LoanLicense.objects.get(license_number="PBL-UI-1")
        self.assertRedirects(
            response,
            reverse("loans:license_detail", args=[license.pk]),
            fetch_redirect_response=False,
        )

        response = self.tenant_post(
            reverse("loans:series_create", args=[license.pk]),
            {
                "name": "Main Counter",
                "code": "A",
                "is_active": "on",
                "pawn_loan_prefix": "PL-A-",
                "release_prefix": "RL-A-",
                "number_width": 5,
                "maximum_number": 10000,
            },
        )

        self.assertEqual(response.status_code, 302)
        series = LoanSeries.objects.get(license=license, code="A")
        self.assertEqual(series.number_sequences.count(), 2)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "PL-A-00001")
        self.assertContains(detail, "RL-A-00001")
        self.assertContains(detail, "Ready")
        self.assertContains(detail, "New Loans Setup")

    def test_detail_preview_does_not_consume_a_number(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )

        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        sequence.refresh_from_db()
        self.assertEqual(sequence.next_number, 1)

    def test_expiry_is_post_only_and_blocks_readiness_without_deleting_license(self):
        license, _ = self._configured_setup()
        expire_url = reverse("loans:license_expire", args=[license.pk])

        self.assertEqual(self.tenant_get(expire_url).status_code, 405)
        response = self.tenant_post(expire_url)

        self.assertEqual(response.status_code, 302)
        license.refresh_from_db()
        self.assertFalse(license.is_active)
        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))
        self.assertContains(detail, "new drafts blocked")

    def test_exhausted_sequence_is_visible_and_not_ready(self):
        license, series = self._configured_setup()
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        sequence.next_number = sequence.maximum_number + 1
        sequence.save(update_fields=["next_number"])

        detail = self.tenant_get(reverse("loans:license_detail", args=[license.pk]))

        self.assertContains(detail, "sequence is exhausted")
        self.assertContains(detail, "Not ready")

    def test_non_member_is_denied_setup_access(self):
        user = get_user_model().objects.create_user(
            username=f"setup-outsider-{uuid.uuid4().hex[:8]}",
            email=f"setup-outsider-{uuid.uuid4().hex[:8]}@example.com",
        )
        request = RequestFactory().get("/loans/setup/")
        request.user = user
        request.tenant = self.tenant

        with self.assertRaises(PermissionDenied):
            assert_loans_setup_access(request)

    def test_workspace_filtered_lookup_fails_closed(self):
        request = RequestFactory().get("/loans/setup/licenses/999/")
        request.loans_workspace = self.tenant
        with patch(
            "apps.tenant_apps.loans.views.get_object_or_404"
        ) as get_object_or_404:
            _license_for_workspace(request, 999)

        get_object_or_404.assert_called_once_with(
            LoanLicense, pk=999, workspace=self.tenant
        )

    def test_operations_console_surfaces_mvp_blockers_and_audit_evidence(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-A-00001", state="APPROVED")
        event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="DISBURSAL",
            effective_date=date(2026, 8, 1),
            payload={"values": {"principal": "10000.00"}},
            payload_fingerprint="event-fingerprint",
            idempotency_key="operations-event-1",
            created_by=self.owner,
        )
        outbox = PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key="operations-outbox-1",
            payload={"event": "DISBURSAL"},
            payload_fingerprint="outbox-fingerprint",
            status="FAILED",
            attempt_count=2,
            last_error="DEA posting unavailable",
        )
        stale_event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="INTEREST_ACCRUAL",
            effective_date=date(2026, 8, 2),
            payload={},
            payload_fingerprint="stale-event-fingerprint",
            idempotency_key="operations-event-2",
            created_by=self.owner,
        )
        PawnLoanAccountingOutbox.objects.create(
            event=stale_event,
            idempotency_key="operations-outbox-2",
            payload={},
            payload_fingerprint="stale-outbox-fingerprint",
            status="PROCESSING",
            claimed_at=timezone.now() - timedelta(minutes=30),
        )
        release_sequence = LoanNumberSequence.objects.get(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value,
        )
        release_sequence.next_number = release_sequence.maximum_number + 1
        release_sequence.save(update_fields=["next_number"])
        LoanChangeLog.objects.create(
            loan=loan,
            event_kind="APPROVED",
            from_state="DRAFT",
            to_state="APPROVED",
            actor=self.owner,
        )

        response = self.tenant_get(reverse("loans:pawn_operations_console"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PawnLoan operations console")
        self.assertContains(response, "Ready to allocate")
        self.assertContains(response, "EXHAUSTED")
        self.assertContains(response, "Stale processing claims need support review")
        self.assertContains(response, "DEA posting unavailable")
        self.assertContains(response, loan.loan_number)
        self.assertContains(response, "Accounting setup by serviceable loan")
        self.assertContains(response, "Recent lifecycle audit")
        self.assertContains(response, reverse("loans:pawn_outbox_retry", args=[outbox.pk]))
        self.assertContains(response, reverse("loans:pawn_operations_runbook"))

    def test_operations_retry_returns_to_console(self):
        license, series = self._configured_setup()
        loan = self._loan(license, series, "PL-A-00002")
        event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind="DISBURSAL",
            effective_date=date(2026, 8, 1),
            payload={},
            payload_fingerprint="retry-event-fingerprint",
            idempotency_key="operations-retry-event",
            created_by=self.owner,
        )
        outbox = PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key="operations-retry-outbox",
            payload={},
            payload_fingerprint="retry-outbox-fingerprint",
            status="FAILED",
        )

        with patch(
            "apps.tenant_apps.loans.views.retry_failed_outbox_event"
        ) as retry:
            response = self.tenant_post(
                reverse("loans:pawn_outbox_retry", args=[outbox.pk]),
                {"next": "operations"},
            )

        self.assertRedirects(
            response,
            reverse("loans:pawn_operations_console"),
            fetch_redirect_response=False,
        )
        retry.assert_called_once_with(outbox.pk)

    def test_operations_pages_require_owner_or_admin(self):
        member = get_user_model().objects.create_user(
            username=f"operations-member-{uuid.uuid4().hex[:8]}"
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_console")).status_code,
            403,
        )
        self.assertEqual(
            self.tenant_get(reverse("loans:pawn_operations_runbook")).status_code,
            403,
        )

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Configured License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(
            license=license, name="Main", code="A"
        )
        for kind, prefix in (
            (LoanDocumentKind.PAWN_LOAN.value, "PL-A-"),
            (LoanDocumentKind.PAWN_LOAN_RELEASE.value, "RL-A-"),
        ):
            LoanNumberSequence.objects.create(
                series=series,
                document_kind=kind,
                prefix=prefix,
                width=5,
                maximum_number=10000,
            )
        return license, series

    def _loan(self, license, series, number, *, state="DRAFT"):
        return PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            borrower=Party.objects.create(display_name=f"Borrower {number}"),
            loan_number=number,
            state=state,
            principal_amount=Decimal("10000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            created_by=self.owner,
            updated_by=self.owner,
        )
