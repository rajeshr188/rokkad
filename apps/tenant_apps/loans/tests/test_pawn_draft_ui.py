import uuid
from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    PawnLoan,
)
from apps.tenant_apps.party.models import Party


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class PawnDraftUiTests(TenantTestCase):
    test_schema_name = f"loans_draft_ui_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-draft-ui-{uuid.uuid4().hex[:8]}.test.com"

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
            username="pawn-draft-ui-owner",
            defaults={"email": "pawn-draft-ui-owner@example.com"},
        )
        tenant.name = f"Pawn Draft UI {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(user=owner, company=tenant, defaults={"role": owner_role})

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
        self.party = Party.objects.create(display_name="Draft Borrower")

    def test_create_is_blocked_with_clear_setup_action(self):
        response = self.client.get(reverse("loans:pawn_loan_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PawnLoan setup required")
        self.assertContains(response, "Open Loan Setup")
        self.assertContains(response, reverse("loans:license_list"))

    def test_staff_can_create_view_and_correct_a_draft_only(self):
        license, series = self._configured_setup()
        response = self.client.post(
            reverse("loans:pawn_loan_create"),
            self._payload(license, series),
        )

        loan = PawnLoan.objects.get()
        self.assertRedirects(
            response,
            reverse("loans:pawn_loan_detail", args=[loan.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(loan.collateral_items.count(), 1)

        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        self.assertContains(detail, loan.loan_number)
        self.assertContains(detail, "Disbursal is not available yet")

        payload = self._payload(license, series)
        payload["principal_amount"] = "12500.00"
        payload["collateral-0-description"] = "Corrected gold chain"
        response = self.client.post(reverse("loans:pawn_loan_update", args=[loan.pk]), payload)
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(str(loan.principal_amount), "12500.00")
        self.assertEqual(loan.collateral_items.get().description, "Corrected gold chain")
        self.assertEqual(loan.change_log.count(), 2)

    def test_invalid_create_rerenders_without_consuming_number(self):
        license, series = self._configured_setup()
        payload = self._payload(license, series)
        payload["collateral-0-net_weight"] = "12.0000"
        response = self.client.post(reverse("loans:pawn_loan_create"), payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(PawnLoan.objects.count(), 0)
        sequence = LoanNumberSequence.objects.get(
            series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value
        )
        self.assertEqual(sequence.next_number, 1)

    def test_internal_routes_are_not_added_to_primary_navigation(self):
        response = self.client.get(reverse("loans:license_list"))
        self.assertNotContains(response, reverse("loans:pawn_loan_list"))

    def test_workspace_member_can_use_internal_draft_ui_but_not_setup(self):
        User = get_user_model()
        member = User.objects.create_user(
            username=f"pawn-staff-{uuid.uuid4().hex[:8]}",
            email=f"pawn-staff-{uuid.uuid4().hex[:8]}@example.com",
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=member, company=self.tenant, role=member_role)
        self.client.force_login(member)

        self.assertEqual(self.client.get(reverse("loans:pawn_loan_list")).status_code, 200)
        self.assertEqual(self.client.get(reverse("loans:license_list")).status_code, 403)

    def test_staff_can_approve_reopen_reapprove_and_cancel_through_ui(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "APPROVED")
        self.assertEqual(loan.approval_snapshots.count(), 1)

        response = self.client.post(
            reverse("loans:pawn_loan_reopen", args=[loan.pk]),
            {"reason": "Correct collateral valuation"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.client.post(reverse("loans:pawn_loan_approve", args=[loan.pk]))
        self.assertEqual(loan.approval_snapshots.count(), 2)

        response = self.client.post(
            reverse("loans:pawn_loan_cancel", args=[loan.pk]),
            {"reason": "Borrower withdrew"},
        )
        self.assertEqual(response.status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CANCELLED")

    def test_reason_form_does_not_transition_when_reason_is_missing(self):
        license, series = self._configured_setup()
        self.client.post(reverse("loans:pawn_loan_create"), self._payload(license, series))
        loan = PawnLoan.objects.get()

        response = self.client.post(reverse("loans:pawn_loan_cancel", args=[loan.pk]), {"reason": ""})
        self.assertEqual(response.status_code, 200)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")

    def _configured_setup(self):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="UI License",
            license_number=f"PBL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(license=license, name="Main", code="A")
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

    def _payload(self, license, series):
        return {
            "borrower": self.party.pk,
            "license": license.pk,
            "series": series.pk,
            "principal_amount": "10000.00",
            "monthly_interest_rate": "2.000000",
            "loan_date": "2026-07-18",
            "tenure_months": "3",
            "collateral-TOTAL_FORMS": "1",
            "collateral-INITIAL_FORMS": "0",
            "collateral-MIN_NUM_FORMS": "1",
            "collateral-MAX_NUM_FORMS": "1000",
            "collateral-0-description": "Gold chain",
            "collateral-0-metal": "GOLD",
            "collateral-0-gross_weight": "10.0000",
            "collateral-0-net_weight": "9.0000",
            "collateral-0-purity_percentage": "91.6000",
            "collateral-0-latest_appraised_value": "50000.00",
        }
