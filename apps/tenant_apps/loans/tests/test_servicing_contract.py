from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.db import connection
from django.test import SimpleTestCase
from django.test.utils import CaptureQueriesContext

from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.servicing_contract import (
    ServicingContractError, get_servicing_position, resolve_servicing_contract,
)
from apps.tenant_apps.loans.services.event_recording import record_loan_event
from apps.tenant_apps.loans.services.notice_delivery_readiness import notice_balance
from apps.tenant_apps.loans.services.pawn_repayment import preview_pawn_loan_repayment
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from .test_opening_release import OpeningReleaseFixture
from . import test_recorded_origination as origins, test_recorded_history as histories


class ServicingPositionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "servicing-position"

    def setUp(self):
        self.prepare_history()

    def test_recorded_profile_one_shared_amounts_and_no_writes(self):
        loan, _, _ = self.admit()
        before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        contracts = list(loan.policy_snapshots.values_list("pk", "interest_method"))
        schedules = list(loan.repayment_schedules.values_list("pk", "source_event_id"))
        with CaptureQueriesContext(connection) as queries:
            position = get_servicing_position(loan, as_of_date=self.today, include_coverage=True)
        self.assertEqual(position.contract.profile, "recorded-anniversary/3")
        self.assertEqual(position.contract.anniversary_rule, "DAY_AFTER_ORIGINAL_ANNIVERSARY")
        self.assertEqual(position.contract.currency_quantum, Decimal("0.01"))
        self.assertEqual(position.balance.total_due, Decimal("10200"))
        self.assertTrue(position.transaction_coverage.complete)
        self.assertEqual(position.balance, notice_balance(loan, self.today))
        self.assertEqual(position.balance, collection_balance(loan, self.today))
        allocation = preview_pawn_loan_repayment(loan.pk, amount="2000").allocation
        self.assertEqual((allocation.interest, allocation.principal), (Decimal("200"), Decimal("1800")))
        self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
        self.assertEqual(contracts, list(loan.policy_snapshots.values_list("pk", "interest_method")))
        self.assertEqual(schedules, list(loan.repayment_schedules.values_list("pk", "source_event_id")))
        self.assertTrue(all(q["sql"].lstrip().upper().startswith("SELECT") for q in queries))
        # A position resolves facts once, not separately for each displayed amount.
        self.assertLess(len(queries), 35)

    def test_item_profile_three_rounds_each_item_and_changes_after_anniversary(self):
        first = {key: self.data[key] for key in (
            "description", "metal", "quantity", "gross_weight", "net_weight", "purity", "principal", "rate")}
        first.update(principal="0.25", rate="2")
        self.data.update(collateral=[first, dict(first, description="Second ring")], principal="0.50",
                         rate="2", advance_months=1, cash_paid="0.48")
        loan, _, _ = self.admit()
        anniversary = loan.loan_date + relativedelta(months=1)
        before = get_servicing_position(loan, as_of_date=anniversary-timedelta(days=1))
        on_day = get_servicing_position(loan, as_of_date=anniversary)
        self.assertEqual(on_day.contract.profile, "recorded-anniversary/3")
        self.assertEqual(on_day.contract.rounding_scope, "PER_ITEM_PER_ANNIVERSARY")
        self.assertEqual(before.balance.interest_outstanding, Decimal("0"))
        self.assertEqual(on_day.balance.interest_outstanding, 0)
        self.assertEqual(get_servicing_position(loan, as_of_date=anniversary+timedelta(days=1)).balance.interest_outstanding, Decimal("0.02"))

    def test_native_unitemized_fold_does_not_collect_projected_interest(self):
        loan = m.PawnLoan.objects.create(workspace=self.tenant, license=self.series.license,
            series=self.series, borrower_id=self.data["borrower_id"],
            product_version_id=self.data["product_version_id"], loan_number="N-1", loan_date=self.day,
            principal_amount="10000", monthly_interest_rate="2", tenure_months=3, state="ACTIVE")
        payload = disbursal_payload(loan, effective_date=self.day, principal_amount=10000,
            net_cash_amount=10000, advance_interest_amount=0, deducted_fee_amount=0).to_dict()
        record_loan_event(loan.pk, event_kind="DISBURSAL", effective_date=self.day,
                          payload=payload, actor=self.actor)
        position = get_servicing_position(loan, as_of_date=self.today, include_coverage=True)
        self.assertEqual(position.contract.profile, "native-event-fold/1")
        self.assertIsNone(position.contract.currency_quantum)
        self.assertEqual(position.balance.interest_outstanding, 0)
        self.assertEqual(position.balance.total_due, 10000)
        self.assertEqual(position.balance, get_pawn_loan_balance(loan, as_of_date=self.today))
        self.assertEqual(position.balance, notice_balance(loan, self.today))
        self.assertFalse(position.transaction_coverage.required)

    def test_unknown_profile_rejected_by_both_consumers_not_native_fallback(self):
        loan, _, _ = self.admit()
        events = list(loan.loan_events.all())
        origin = next(e for e in events if e.event_kind == "DISBURSAL")
        origin.payload = deepcopy(origin.payload)
        origin.payload["recording"]["collection_profile"] = "unknown/999"
        with patch.object(type(loan.loan_events), "all", return_value=events):
            with self.assertRaisesMessage(ServicingContractError, "no supported collection profile"):
                notice_balance(loan, self.today)
            with patch("apps.tenant_apps.loans.services.pawn_repayment._tenant_loan", return_value=loan):
                with self.assertRaisesMessage(ValueError, "no supported collection profile"):
                    preview_pawn_loan_repayment(loan.pk, amount="100")

    def test_foreign_object_and_missing_context_fail_before_calculation(self):
        from apps.orgs.models import Company
        loan, _, _ = self.admit()
        other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        with without_workspace_context():
            with self.assertRaisesMessage(ServicingContractError, "active Workspace"):
                get_servicing_position(loan, as_of_date=self.today)
            with workspace_context(other.pk):
                with self.assertRaisesMessage(ServicingContractError, "active Workspace"):
                    get_servicing_position(loan, as_of_date=self.today)

    def test_original_date_and_operation_errors_are_explicit(self):
        loan, _, _ = self.admit()
        with self.assertRaisesMessage(ServicingContractError, "original loan date"):
            get_servicing_position(loan, as_of_date=loan.loan_date-timedelta(days=1))
        with self.assertRaisesMessage(ServicingContractError, "Unsupported servicing"):
            get_servicing_position(loan, as_of_date=self.today, operation="POST")

    def test_import_provenance_does_not_change_the_same_supported_contract(self):
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        first, _, _ = self.admit()
        self.data.update(number="P-0011", source_reference="Book B / loan 11")
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        second, _, _ = self.admit()
        # Admission-independent provenance fixture, not an importer acceptance test.
        m.HistoricalLoanImport.objects.create(workspace=self.tenant, loan=second,
            source_namespace=uuid4(), source_id="synthetic-provenance-11", source_sha256="a"*64,
            document={"fixture": "same supported recorded contract"}, references={}, imported_by=self.actor)
        a = get_servicing_position(first, as_of_date=self.today)
        b = get_servicing_position(second, as_of_date=self.today)
        self.assertEqual(a.contract.profile, b.contract.profile)
        for field in ("principal_outstanding", "interest_outstanding", "fees_outstanding", "total_due", "due_date"):
            self.assertEqual(getattr(a.balance, field), getattr(b.balance, field))
        self.assertEqual(preview_pawn_loan_repayment(first.pk, amount=2000).allocation,
                         preview_pawn_loan_repayment(second.pk, amount=2000).allocation)

    def test_restricted_role_reads_only_its_workspace(self):
        from apps.orgs.models import Company
        loan, _, _ = self.admit()
        other = Company.objects.create(name="Foreign", schema_name=uuid4().hex,
                                       owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("servicing_read_"+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            self.assertEqual(get_servicing_position(loan, as_of_date=self.today).balance.total_due, 10200)
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnLoan.objects.filter(pk=loan.pk).exists())
                with self.assertRaisesMessage(ServicingContractError, "active Workspace"):
                    get_servicing_position(loan, as_of_date=self.today)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_closed_recorded_balance_stays_settled(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200",
                                                              number="R-0009", recipient="Borrower")])
        loan, _, _ = self.admit()
        balance = notice_balance(loan, self.today+timedelta(days=35))
        self.assertEqual(balance.total_due, 0)

    def test_closed_label_without_financial_origin_is_not_a_zero_balance(self):
        loan, _, _ = self.admit()
        loan.state = "CLOSED"
        with patch.object(type(loan.loan_events), "all", return_value=[]):
            with self.assertRaisesMessage(ServicingContractError, "no supported financial origin"):
                notice_balance(loan, self.today)


class OpeningServicingPositionTests(OpeningReleaseFixture):
    def test_boundary_baseline_and_read_only_shared_position(self):
        self.day = date(2021, 2, 1)
        on_day = get_servicing_position(self.loan, as_of_date=self.day, include_coverage=True)
        after = get_servicing_position(self.loan, as_of_date=date(2021, 2, 2))
        self.assertEqual(on_day.contract.anniversary_rule, "DAY_AFTER_ORIGINAL_ANNIVERSARY")
        self.assertEqual(on_day.contract.rounding_mode, "HALF_EVEN")
        self.assertEqual(on_day.contract.currency_quantum, Decimal("1"))
        self.assertEqual(on_day.contract.financial_history_from, date(2021, 1, 20))
        self.assertEqual(on_day.balance.total_due, 1000)
        self.assertEqual(after.balance.total_due, 1010)
        self.assertEqual(after.balance, notice_balance(self.loan, date(2021, 2, 2)))
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(self.loan.interest_accruals.exists())
        self.assertEqual(on_day.transaction_coverage.status, "UNCONFIRMED")

    def test_before_and_on_cutover_preserve_precise_blockers(self):
        with self.assertRaisesMessage(ServicingContractError, "before the migration cutover"):
            get_servicing_position(self.loan, as_of_date=date(2021, 1, 19))
        with self.assertRaisesMessage(ValueError, "after cutover"):
            get_servicing_position(self.loan, as_of_date=date(2021, 1, 20))
        self.assertEqual(resolve_servicing_contract(self.loan, as_of_date=date(2021, 1, 20)).
                         recognized_interest_at_cutover, Decimal("0"))

    def test_partial_payment_and_reversal_keep_old_continuation(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        payment = record_pawn_loan_repayment(self.loan.pk, amount=210, request_key="read-parity", actor=self.actor)
        self.assertEqual(get_servicing_position(self.loan, as_of_date=date(2021, 3, 2)).balance.total_due, 808)
        self.day = date(2021, 3, 3)
        reverse_pawn_loan_event(payment.loan_event.pk, actor=self.actor, reason="Wrong receipt")
        self.assertEqual(get_servicing_position(self.loan, as_of_date=self.day).balance.total_due, 1020)

    def test_closed_opening_notice_uses_recorded_fold(self):
        self.release()
        self.loan.refresh_from_db()
        position = get_servicing_position(self.loan, as_of_date=self.day, operation="NOTICE")
        self.assertEqual(position.balance_basis, "RECORDED_DEBT")
        self.assertEqual(position.balance.total_due, 0)

    def test_mixed_origins_fail_before_calculator(self):
        events = list(self.loan.loan_events.all())
        events.append(SimpleNamespace(pk=999999, event_kind="DISBURSAL", reversal_of_id=None))
        with patch.object(type(self.loan.loan_events), "all", return_value=events):
            with self.assertRaisesMessage(ServicingContractError, "exactly one"):
                get_servicing_position(self.loan, as_of_date=self.day)


class ServicingRoundingExamples(SimpleTestCase):
    def test_existing_whole_rupee_half_even_and_item_half_up_are_distinct(self):
        from decimal import ROUND_HALF_UP
        from apps.tenant_apps.loans.services.legacy_interest import aggregate_collection_interest
        one = aggregate_collection_interest(date(2026, 4, 5), date(2026, 5, 6), Decimal("100.50"))
        two = aggregate_collection_interest(date(2026, 4, 5), date(2026, 6, 6), Decimal("100.50"))
        self.assertEqual(Decimal(one["additional_interest"]), Decimal("100"))
        self.assertEqual(Decimal(two["additional_interest"]), Decimal("201"))
        raw = Decimal("10.005")
        self.assertEqual(2 * raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("20.02"))
        self.assertEqual((2 * raw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), Decimal("20.01"))
