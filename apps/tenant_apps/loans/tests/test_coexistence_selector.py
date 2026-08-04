import uuid
from dataclasses import replace
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import GivenLoan, License, LoanItem, Series
from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanSeries,
    PawnCollateralItem,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
)
from apps.tenant_apps.loans.selectors import (
    UnifiedLoanReadRow,
    build_loan_coexistence_comparison,
    build_unified_loan_portfolio,
    get_loan_coexistence_comparison,
    get_unified_loan_portfolio,
)
from apps.tenant_apps.party.models import Party


class UnifiedLoanContractTests(SimpleTestCase):
    as_of = date(2026, 8, 4)

    def test_source_totals_reconcile_to_their_rows_and_combined_total(self):
        girvi = self._row(
            source="GIRVI",
            owner="girvi",
            source_id=1,
            principal="800",
            interest="100",
            bucket="ACTIVE",
            action_name="girvi:girvi_loan_detail",
        )
        loans = self._row(
            source="LOANS",
            owner="loans",
            source_id=2,
            principal="1200",
            interest="50",
            bucket="CLOSED",
            action_name="loans:pawn_loan_detail",
        )

        portfolio = build_unified_loan_portfolio(
            girvi_rows=(girvi,), loans_rows=(loans,), as_of_date=self.as_of
        )

        girvi_totals, loans_totals = portfolio.source_totals
        self.assertEqual(girvi_totals.principal_outstanding, Decimal("800"))
        self.assertEqual(girvi_totals.total_due, Decimal("900"))
        self.assertEqual(girvi_totals.active_count, 1)
        self.assertEqual(loans_totals.principal_outstanding, Decimal("1200"))
        self.assertEqual(loans_totals.total_due, Decimal("1250"))
        self.assertEqual(loans_totals.closed_count, 1)
        self.assertEqual(portfolio.total_principal_outstanding, Decimal("2000"))
        self.assertEqual(portfolio.total_due, Decimal("2150"))

    def test_wrong_owner_namespace_is_rejected(self):
        girvi_with_loans_action = self._row(
            source="GIRVI",
            owner="girvi",
            source_id=1,
            principal="800",
            interest="100",
            bucket="ACTIVE",
            action_name="loans:pawn_loan_detail",
        )

        with self.assertRaisesMessage(ValueError, "owning app namespace"):
            build_unified_loan_portfolio(
                girvi_rows=(girvi_with_loans_action,),
                loans_rows=(),
                as_of_date=self.as_of,
            )

    def test_comparison_reports_zero_mismatches_for_matching_fixture(self):
        row = self._row(
            source="LOANS",
            owner="loans",
            source_id=1,
            principal="800",
            interest="100",
            bucket="ACTIVE",
            action_name="loans:pawn_loan_detail",
        )

        comparison = build_loan_coexistence_comparison(
            expected_rows=(row,),
            actual_rows=(row,),
            as_of_date=self.as_of,
        )

        self.assertTrue(comparison.is_match)
        self.assertEqual(comparison.mismatch_count, 0)

    def test_comparison_categorizes_deliberate_mismatches(self):
        expected = self._row(
            source="LOANS",
            owner="loans",
            source_id=1,
            principal="800",
            interest="100",
            bucket="ACTIVE",
            action_name="loans:pawn_loan_detail",
        )
        actual = replace(
            expected,
            lifecycle_bucket="CLOSED",
            principal_outstanding=Decimal("700"),
            total_due=Decimal("800"),
            custody_summary="0 vault / 1 customer",
            release_status="FULL",
            dea_visibility="MISSING",
        )

        comparison = build_loan_coexistence_comparison(
            expected_rows=(expected,),
            actual_rows=(actual,),
            as_of_date=self.as_of,
        )

        self.assertFalse(comparison.is_match)
        self.assertEqual(
            {mismatch.category for mismatch in comparison.mismatches},
            {"LIFECYCLE", "MONEY", "CUSTODY", "RELEASE", "DEA_VISIBILITY"},
        )

    def _row(
        self,
        *,
        source,
        owner,
        source_id,
        principal,
        interest,
        bucket,
        action_name,
    ):
        principal = Decimal(principal)
        interest = Decimal(interest)
        return UnifiedLoanReadRow(
            source_system=source,
            source_label=source.title(),
            owner_app=owner,
            source_id=source_id,
            source_key=f"{source}:PAWN:{source_id}",
            loan_kind="PAWN",
            loan_number=f"L-{source_id}",
            loan_date=self.as_of,
            party_id=source_id,
            party_name="Borrower",
            stored_status=bucket,
            lifecycle_status=bucket,
            lifecycle_bucket=bucket,
            original_principal=principal,
            principal_outstanding=principal,
            interest_outstanding=interest,
            total_due=principal + interest,
            collateral_count=1,
            custody_summary="1 vault",
            owner_action_name=action_name,
            owner_action_url=f"/{owner}/{source_id}/",
            financial_data_available=True,
        )


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class UnifiedLoanTenantReadTests(TenantTestCase):
    test_schema_name = f"loans_coexist_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-coexist-{uuid.uuid4().hex[:8]}.test.com"

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
            username="loans-coexist-owner",
            defaults={"email": "loans-coexist-owner@example.com"},
        )
        tenant.name = f"Loans Coexist {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner, company=tenant, defaults={"role": owner_role}
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
        self._create_girvi_loan()
        self.pawn_loan = self._create_pawn_loan()

    def test_tenant_portfolio_contains_both_sources_with_owner_urls(self):
        portfolio = get_unified_loan_portfolio(as_of_date=date(2026, 8, 4))

        self.assertEqual(portfolio.row_count, 2)
        rows = {row.source_system: row for row in portfolio.rows}
        self.assertEqual(rows["GIRVI"].owner_app, "girvi")
        self.assertEqual(rows["GIRVI"].owner_action_name, "girvi:girvi_loan_detail")
        self.assertEqual(rows["GIRVI"].owner_action_url, reverse("girvi:girvi_loan_detail", args=[self.girvi_loan.pk]))
        self.assertEqual(rows["LOANS"].owner_app, "loans")
        self.assertEqual(rows["LOANS"].owner_action_name, "loans:pawn_loan_detail")
        self.assertEqual(rows["LOANS"].owner_action_url, reverse("loans:pawn_loan_detail", args=[self.pawn_loan.pk]))
        self.assertEqual(portfolio.total_principal_outstanding, Decimal("1800.00"))

    def test_read_only_view_labels_sources_and_uses_owner_links(self):
        response = self.client.get(reverse("loans:unified_loan_portfolio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Girvi + Loans portfolio")
        self.assertContains(response, "G-00001")
        self.assertContains(response, "PL-U-00001")
        self.assertContains(response, "Open in Girvi")
        self.assertContains(response, "Open in Loans")
        self.assertContains(
            response,
            reverse("girvi:girvi_loan_detail", args=[self.girvi_loan.pk]),
        )
        self.assertContains(
            response,
            reverse("loans:pawn_loan_detail", args=[self.pawn_loan.pk]),
        )

    def test_tenant_comparison_and_command_report_zero_mismatches(self):
        comparison = get_loan_coexistence_comparison(as_of_date=date(2026, 8, 4))
        output = StringIO()

        call_command(
            "compare_loan_coexistence",
            as_of="2026-08-04",
            stdout=output,
        )

        self.assertTrue(comparison.is_match)
        self.assertIn("Comparison passed: zero mismatches.", output.getvalue())
        self.assertIn("GIRVI: rows=1", output.getvalue())
        self.assertIn("LOANS: rows=1", output.getvalue())

    def _create_girvi_loan(self):
        borrower = Customer.objects.create(firstname="Legacy Borrower")
        license = License.objects.create(
            name="Legacy License", license_number=f"GL-{uuid.uuid4().hex[:8]}"
        )
        series = Series.objects.create(
            license=license,
            name="Legacy",
            prefix="G",
            max_limit=5,
            loan_type="Given",
        )
        self.girvi_loan = GivenLoan.objects.create(
            loan_id="G-00001",
            series=series,
            borrower=borrower,
            loan_date=timezone.now(),
            status="Draft",
        )
        LoanItem.objects.create(
            loan=self.girvi_loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("91.60"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Legacy ring",
        )
        GivenLoan.objects.filter(pk=self.girvi_loan.pk).update(status="ActiveCurrent")
        self.girvi_loan.refresh_from_db()

    def _create_pawn_loan(self):
        borrower = Party.objects.create(display_name="New Borrower")
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="New License",
            license_number=f"NL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.owner,
        )
        series = LoanSeries.objects.create(license=license, name="Unified", code="U")
        loan = PawnLoan.objects.create(
            workspace=self.tenant,
            license=license,
            series=series,
            borrower=borrower,
            loan_number="PL-U-00001",
            state=PawnLoanState.ACTIVE.value,
            principal_amount=Decimal("800.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 2, 1),
            tenure_months=6,
            created_by=self.owner,
        )
        PawnCollateralItem.objects.create(
            loan=loan,
            description="New chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("8.0000"),
            net_weight=Decimal("7.5000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("30000.00"),
        )
        payload = {"values": {"principal": "800.00", "interest": "0", "fees": "0"}}
        event = PawnLoanAccountingEvent.objects.create(
            loan=loan,
            event_kind=TransactionKind.DISBURSAL.value,
            effective_date=date(2026, 2, 1),
            payload=payload,
            payload_fingerprint="unified-disbursal",
            idempotency_key="unified-disbursal",
            created_by=self.owner,
        )
        PawnLoanAccountingOutbox.objects.create(
            event=event,
            idempotency_key=event.idempotency_key,
            payload=payload,
            payload_fingerprint=event.payload_fingerprint,
            status="POSTED",
            dea_voucher_id=1001,
            dea_journal_entry_id=1002,
        )
        return loan
