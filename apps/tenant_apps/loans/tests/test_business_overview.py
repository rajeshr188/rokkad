from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch
import uuid

from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import PawnLoanEvent
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.business_overview import get_business_overview
from apps.tenant_apps.loans.tests import test_dashboard_batch as fixtures
from apps.tenant_apps.loans.web.dashboard_forms import DashboardActivityForm


class BusinessOverviewTests(TestCase):
    setUp = fixtures.DashboardBatchTests.setUp
    loan = fixtures.DashboardBatchTests.loan

    def event(self, loan, kind, values, *, day=None, original=None):
        payload = {"values": {key: str(value) for key, value in values.items()}}
        if original:
            payload["reversal"] = {"original_event_kind": original.event_kind}
        return PawnLoanEvent.objects.create(workspace_id=loan.workspace_id, loan=loan,
            event_kind=kind, effective_date=day or timezone.localdate(), payload=payload,
            reversal_of=original, payload_fingerprint=uuid.uuid4().hex,
            idempotency_key=uuid.uuid4().hex)

    def overview(self):
        today = timezone.localdate()
        return get_business_overview(workspace=self.workspace,
            activity_start=today.replace(day=1), activity_end=today)

    def test_balances_match_canonical_fold_with_capitalization_and_reversals(self):
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            self.event(loan, "DISBURSAL", {"principal": 1000, "net_cash": 990})
            self.event(loan, "INTEREST_ACCRUAL", {"interest": 100})
            self.event(loan, "INTEREST_CAPITALIZATION", {"interest": 40})
            paid = self.event(loan, "REPAYMENT", {"principal": 100, "interest": 20,
                "capitalized_interest_principal": 40})
            self.event(loan, "REVERSAL", paid.payload["values"], original=paid)
            self.event(loan, "INTEREST_ACCRUAL", {"interest": 900}, day=timezone.localdate()+timedelta(days=1))
            result = self.overview()
            balance = get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
            self.assertEqual(result["principal_outstanding"], balance.principal_outstanding)
            self.assertEqual(result["principal_outstanding"], Decimal("1040"))
            self.assertEqual(result["interest_outstanding"], balance.interest_outstanding)
            self.assertEqual(result["interest_outstanding"], Decimal("60"))
            self.assertEqual(result["activity"]["new_loan_cash"], Decimal("990"))

    def test_counts_distinguish_customers_borrowers_states_and_renewals(self):
        from apps.tenant_apps.party.models import Party, PartyRole, PartyRoleType
        with workspace_context(self.workspace.pk):
            customer = Party.objects.create(display_name="Customer without loans")
            role_type = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
            PartyRole.objects.create(party=customer, role_type=role_type, status="ACTIVE")
            Party.objects.create(display_name="Unrelated supplier")
            first = self.loan(self.workspace)
            second = self.loan(self.workspace)
            second.borrower = first.borrower
            second.save(update_fields=["borrower"])
            closed = self.loan(self.workspace)
            closed.state = "CLOSED"
            closed.save(update_fields=["state"])
            draft = self.loan(self.workspace)
            draft.borrower, draft.state = first.borrower, "DRAFT"
            draft.save(update_fields=["borrower", "state"])
            for loan in (first, closed):
                self.event(loan, "DISBURSAL", {"principal": 1000})
            self.event(second, "RENEWAL_OPENING", {"principal": 1000})
            result = self.overview()
            self.assertEqual(result["total_customers"], 3)
            self.assertEqual(result["active_borrowers"], 1)
            self.assertEqual(result["active_loans"], 2)
            self.assertEqual(result["principal_outstanding"], Decimal("2000"))
            self.assertEqual(result["activity"]["new_loans"], 2)
            self.assertEqual(result["activity"]["renewals"], 1)
            self.assertEqual(result["activity"]["new_loan_cash"], Decimal("2000"))

    def test_reversal_outside_period_removes_original_issue_but_future_reversal_does_not(self):
        today = timezone.localdate()
        with workspace_context(self.workspace.pk):
            for offset in (0, 1):
                loan = self.loan(self.workspace)
                original = self.event(loan, "DISBURSAL", {"principal": 1000}, day=today-timedelta(days=2))
                self.event(loan, "REVERSAL", {"principal": 1000}, original=original, day=today+timedelta(days=offset))
            result = get_business_overview(workspace=self.workspace,
                activity_start=today-timedelta(days=2), activity_end=today-timedelta(days=1))
            self.assertEqual(result["activity"]["new_loans"], 1)
            self.assertEqual(result["activity"]["average_per_day"], Decimal("0.5"))
            self.assertEqual(result["activity"]["new_loan_cash"], Decimal("1000"))

    def test_invalid_balance_and_cash_never_become_partial_totals(self):
        with workspace_context(self.workspace.pk):
            good, bad = self.loan(self.workspace), self.loan(self.workspace)
            self.event(good, "DISBURSAL", {"principal": 1000})
            self.event(bad, "DISBURSAL", {"principal": 1000, "net_cash": "NaN"})
            self.event(bad, "REPAYMENT", {"principal": 2000})
            result = self.overview()
            self.assertEqual(result["active_loans"], 2)
            self.assertEqual(result["unavailable_balance_count"], 1)
            self.assertIsNone(result["principal_outstanding"])
            self.assertIsNone(result["interest_outstanding"])
            self.assertIsNone(result["activity"]["new_loan_cash"])
            self.assertEqual(result["activity"]["unavailable_cash_count"], 1)

    def test_empty_portfolio_is_zero_and_missing_opening_is_unavailable(self):
        with workspace_context(self.workspace.pk):
            result = self.overview()
            self.assertEqual(result["principal_outstanding"], Decimal("0"))
            self.assertEqual(result["activity"]["new_loan_cash"], Decimal("0"))
            self.loan(self.workspace)
            self.assertIsNone(self.overview()["principal_outstanding"])

    def test_queries_are_batched_instead_of_per_loan(self):
        with workspace_context(self.workspace.pk):
            for size in (1, 10):
                for _ in range(size):
                    loan = self.loan(self.workspace)
                    self.event(loan, "DISBURSAL", {"principal": 1000})
                with self.assertNumQueries(6):
                    self.overview()
            with patch("apps.tenant_apps.loans.selectors.business_overview.BALANCE_BATCH_SIZE", 4):
                with self.assertNumQueries(8):
                    self.assertEqual(self.overview()["active_loans"], 11)

    def test_restricted_role_and_wrong_context(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            self.overview()
        other = Company.objects.create(name="Other overview", schema_name="overview-other", owner=self.owner, creator=self.owner)
        with workspace_context(other.pk):
            self.event(self.loan(other), "DISBURSAL", {"principal": 99999})
        with workspace_context(self.workspace.pk):
            self.event(self.loan(self.workspace), "DISBURSAL", {"principal": 1000})
            with self.assertNumQueries(0), self.assertRaises(ValueError):
                get_business_overview(workspace=other)
            role = connection.ops.quote_name("overview_read_" + uuid.uuid4().hex)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
                cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
                cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
                cursor.execute(f"SET LOCAL ROLE {role}")
            try:
                result = self.overview()
                self.assertEqual(result["total_customers"], 1)
                self.assertEqual(result["principal_outstanding"], Decimal("1000"))
                self.assertEqual(result["activity"]["new_loan_cash"], Decimal("1000"))
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")


class DashboardActivityFormTests(SimpleTestCase):
    def test_presets_and_inclusive_custom_days(self):
        today = date(2026, 9, 12)
        for period, start in (("today", today), ("month", date(2026, 9, 1)), ("30days", date(2026, 8, 14))):
            form = DashboardActivityForm({"period": period}, today=today)
            self.assertTrue(form.is_valid(), form.errors)
            self.assertEqual(form.cleaned_data["start"], start)
            self.assertEqual(form.cleaned_data["end"], today)

    def test_invalid_custom_ranges_are_not_silently_replaced(self):
        for data in ({"period": "invalid"}, {"period": "custom"},
                     {"period": "custom", "start": "2026-09-12", "end": "2026-09-11"},
                     {"period": "custom", "start": "2025-01-01", "end": "2026-09-12"},
                     {"period": "custom", "start": "2026-09-12", "end": "2026-09-13"}):
            form = DashboardActivityForm(data, today=date(2026, 9, 12))
            self.assertFalse(form.is_valid())
