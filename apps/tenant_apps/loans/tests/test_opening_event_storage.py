import hashlib
import json
import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, transaction
from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import PawnLoan, PawnCollateralItem, PawnLoanEvent, LoanSeries, LoanProduct, LoanProductVersion, PawnLoanRepaymentAllocationLine
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.services.license_series import create_license
from apps.tenant_apps.loans.services.opening_evidence import opening_event_payload
from apps.tenant_apps.loans.services.event_recording import record_loan_event, LoanEventRecordingError
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances, PawnTrancheBalanceError
from apps.tenant_apps.loans.services.pawn_disbursal import assert_pawn_loan_financial_actions_allowed
from apps.tenant_apps.loans.services.pawn_interest import preview_pawn_loan_accruals
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.reports import build_pawn_loan_reports, get_pawn_party_statement
from apps.tenant_apps.loans.tests.test_opening_validation import reviewed_opening


class OpeningEventFixture(WorkspaceTestCase):
    product_grace_days = 3

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="opening-foundation")
        tenant.owner = tenant.creator = cls.actor
        tenant.name = "Opening evidence tests"
        tenant.save()
        Membership.objects.create(company=tenant, user=cls.actor, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        super().setUp()
        borrower = Party.objects.create(display_name="Opening borrower")
        license = create_license(workspace=self.tenant, actor=self.actor, name="Historic", license_number="OPEN-L",
                                 issued_on=date(2020, 1, 1), expires_on=date(2022, 1, 1))
        series = LoanSeries.objects.create(license=license, name="Historic", code="O")
        product = LoanProduct.objects.create(workspace=self.tenant, code="O", name="Opening")
        version = LoanProductVersion.objects.create(product=product, version=1, status="RETIRED",
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
            extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12, operational_grace_days=self.product_grace_days, calculation_contract_version="SYNTHETIC-ORIGINAL-1")
        self.loan = PawnLoan.objects.create(workspace=self.tenant, borrower=borrower, license=license,
            license_revision=license.revisions.get(), series=series, product_version=version,
            loan_number="O-1", loan_date=date(2021, 1, 1), tenure_months=3, principal_amount=1000,
            monthly_interest_rate=1, state="ACTIVE")
        review = self.review_document()
        physical = review["collateral"][0]
        self.item = PawnCollateralItem.objects.create(loan=self.loan, description="Ring", metal=physical["metal"],
            gross_weight=physical["gross_weight"], net_weight=physical["net_weight"], purity_percentage=physical["purity"], allocated_principal=1000, monthly_interest_rate=1,
            latest_appraised_value=2000, custody_state="IN_VAULT")
        review["mapping"].update(workspace_id=self.tenant.pk, borrower_id=borrower.pk,
                                licence_revision_id=self.loan.license_revision_id, series_id=series.pk, product_version_id=version.pk)
        self.payload = opening_event_payload(self.loan, review=review, item_mapping={"girvi_loanitem:1": self.item.pk})
        # Fixture insertion exercises existing RLS/immutability, not an import writer.
        self.origin = self.event("MIGRATION_OPENING", date.fromisoformat(review["cutover"]["date"]), self.payload)

    def event(self, kind, day, payload, **kwargs):
        return PawnLoanEvent.objects.create(loan=self.loan, event_kind=kind, effective_date=day, payload=payload,
            payload_fingerprint=hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest(),
            idempotency_key=uuid.uuid4().hex, created_by=self.actor, **kwargs)

    def review_document(self):
        return reviewed_opening()


class OpeningEventStorageTests(OpeningEventFixture):

    def test_stored_opening_drives_balance_and_item_principal_without_disbursal(self):
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=date(2021, 1, 20))
        self.assertEqual((balance.principal_disbursed, balance.opening_principal, balance.total_due), (0, 900, 924))
        tranche = get_pawn_principal_tranche_balances(self.loan)[0]
        self.assertEqual((tranche.initial_principal, tranche.principal_outstanding), (900, 900))
        with self.assertRaisesMessage(PawnTrancheBalanceError, "before migration cutover"):
            get_pawn_principal_tranche_balances(self.loan, as_of_date=date(2021, 1, 19))

    def test_post_opening_repayment_allocation_uses_remaining_principal(self):
        event = self.event("REPAYMENT", date(2021, 1, 21), {"values": {"principal": "100", "interest": "10"}})
        PawnLoanRepaymentAllocationLine.objects.create(loan_event=event, collateral_item=self.item,
            allocation_order=1, monthly_interest_rate=1, balance_before=900, principal_applied=100, balance_after=800)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 800)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan, as_of_date=date(2021, 1, 20))[0].principal_outstanding, 900)
        self.event("REVERSAL", date(2021, 1, 22), {
            "values": {"principal": "100", "interest": "10"},
            "reversal": {"original_event_kind": "REPAYMENT"}}, reversal_of=event)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 900)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan, as_of_date=date(2021, 1, 21))[0].principal_outstanding, 800)
        self.assertEqual(get_pawn_loan_balance(self.loan.pk, as_of_date=date(2021, 1, 22)).principal_outstanding, 900)

    def test_reports_show_imported_debt_without_daily_lending_or_collection(self):
        report = build_pawn_loan_reports((self.loan,), as_of_date=date(2021, 1, 20))
        self.assertEqual((report.total_principal_outstanding, report.total_due), (900, 924))
        self.assertEqual((report.daily_disbursals, report.daily_repayments, report.daily_activity), ((), (), ()))
        statement = get_pawn_party_statement(party_id=self.loan.borrower_id, as_of_date=date(2021, 1, 20))
        row = statement.transaction_rows[0]
        self.assertEqual((row.activity, row.amount, row.principal, row.interest), ("Migration Opening", 0, 900, 24))

    def test_operational_commands_cannot_activate_unimplemented_interest_continuation(self):
        with self.assertRaisesMessage(ValueError, "servicing is not enabled"):
            assert_pawn_loan_financial_actions_allowed(self.loan.pk)
        with self.assertRaisesMessage(ValueError, "historical periods cannot be replayed"):
            preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2021, 2, 20))
        for kind in ("MIGRATION_OPENING", "REPAYMENT", "DISBURSAL"):
            with self.subTest(kind=kind), self.assertRaises(LoanEventRecordingError):
                record_loan_event(self.loan.pk, event_kind=kind, effective_date=date(2021, 1, 21), payload={"values": {"principal": "900"}}, actor=self.actor)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_opening_is_unique_immutable_and_rls_scoped(self):
        other = Company.objects.create(name="Other opening workspace", schema_name="other-opening", owner=self.actor, creator=self.actor)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.event("MIGRATION_OPENING", date(2021, 1, 20), self.payload)
        quoted = connection.ops.quote_name("opening_rls_" + uuid.uuid4().hex)
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, UPDATE, DELETE ON loans_pawnloanevent TO {quoted}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {quoted}")
            self.assertEqual(PawnLoanEvent.objects.count(), 1)
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnLoanEvent.objects.filter(pk=self.origin.pk).update(payload={})
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM loans_pawnloanevent")
            with without_workspace_context():
                self.assertFalse(PawnLoanEvent.objects.exists())
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(PawnLoanEvent.objects.filter(pk=self.origin.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {quoted}")
                cursor.execute(f"DROP ROLE {quoted}")
