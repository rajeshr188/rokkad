import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.subscriptions.models import Subscription
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import workspace_role_permissions
from apps.tenant_apps.loans.domain.khata import anniversary
from apps.tenant_apps.loans.models import (
    KhataInterestPeriod, KhataInterestSegment, KhataInterestAllocation, KhataOperation,
)
from apps.tenant_apps.loans.services import khata_servicing as servicing, khata_opening as opening, khata_accounts as drafts
from . import test_khata_opening as opening_tests, test_khata_foundation as foundation


class InterestFixture(opening_tests.OpeningFixture):
    def setUp(self):
        super().setUp()
        self.started_at = timezone.now()
        self.started_on = timezone.localdate()
        Subscription.objects.filter(company=self.workspace).update(trial_end_date=self.started_at + timedelta(days=1200))

    def open(self, frequency="MONTHLY", monthly_rate="1"):
        if frequency != "MONTHLY" or monthly_rate != "1":
            args = foundation.draft_args(self.workspace, self.actor, self.borrower, self.series)
            args.pop("series_id"); args.pop("borrower_id")
            args.update(account_id=self.account.pk, expected_revision=1, reason="Agreed collection terms",
                frequency=frequency, monthly_rate=monthly_rate)
            drafts.propose_revision(**args)
        self.deposit(); self.approve(); self.payout()

    @contextmanager
    def later(self, months, days=0):
        day = anniversary(self.started_on, months) + timedelta(days=days)
        moment = self.started_at + (day - self.started_on)
        with patch("django.utils.timezone.now", return_value=moment):
            yield

    def pay(self, value):
        review = servicing.preview_interest_payment(**self.args(), value=value)
        return servicing.record_interest_payment(**self.command(), value=value,
            review_hash=review["review_hash"], payment_reference="Cash received")


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataInterestCollectionTests(InterestFixture, TestCase):
    def test_monthly_due_date_partial_payment_and_oldest_first(self):
        self.open()
        with self.later(1):
            self.assertEqual(self.balance()["due_interest"], Decimal("100000"))
            self.assertEqual(self.balance()["overdue_interest"], 0)
            receipt = self.pay("25000")
            self.assertEqual(self.balance()["due_interest"], Decimal("75000"))
            with workspace_context(self.workspace.pk):
                allocation = receipt.interest_allocations.select_related("period").get()
                self.assertEqual(allocation.period.index, 0)
                self.assertEqual(allocation.period.segments.get().agreement_id,
                    self.account.operations.filter(kind="WITHDRAW").first().agreement_id)
        with self.later(2, 1):
            receipt = self.pay("100000")
            with workspace_context(self.workspace.pk):
                self.assertEqual(list(receipt.interest_allocations.order_by("period__index")
                    .values_list("period__index", "amount")), [(0, Decimal("75000")), (1, Decimal("25000"))])
            balances = self.balance()
            self.assertEqual(balances["paid_interest"], Decimal("125000"))
            self.assertEqual(balances["overdue_interest"], Decimal("75000"))
            self.assertEqual(balances["principal"], Decimal("100000"))
            self.assertEqual(balances["unused"], Decimal("9900000"))

    def test_annual_due_is_anniversary_and_months_do_not_compound(self):
        self.open("ANNUAL")
        with self.later(4):
            op = servicing.finalize_interest(**self.command())
            with workspace_context(self.workspace.pk):
                self.assertEqual(op.interest_periods.count(), 4)
                self.assertEqual(set(op.interest_periods.values_list("due_on", flat=True)),
                    {anniversary(self.started_on, 12)})
            self.assertEqual(self.balance()["due_interest"], 0)
            with self.assertRaisesMessage(ValueError, "advance or excess"):
                self.pay("1")
        with self.later(12):
            self.assertEqual(self.balance()["due_interest"], Decimal("1200000"))
            self.assertEqual(self.balance()["overdue_interest"], 0)
            self.pay("100000")
        with self.later(24, 1):
            self.assertEqual(self.balance()["overdue_interest"], Decimal("2300000"))
            self.pay("2300000")
            self.assertEqual(self.balance()["due_interest"], 0)
            self.assertEqual(self.balance()["principal"], Decimal("100000"))
            with workspace_context(self.workspace.pk):
                self.assertEqual(self.account.interest_periods.count(), 24)

    def test_no_advance_excess_zero_or_lossy_money_and_no_side_effects(self):
        self.open()
        for value in ("1", "0", "-1", "NaN", "1.001", 1.0):
            with self.assertRaises(ValueError):
                self.pay(value)
        with self.assertRaisesMessage(ValueError, "no completed"):
            servicing.finalize_interest(**self.command())
        with self.later(1):
            with self.assertRaisesMessage(ValueError, "exceeds"):
                self.pay("100000.01")
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataInterestPeriod.objects.exists())
            self.assertFalse(KhataOperation.objects.filter(kind__in=("ACCRUE", "INTEREST")).exists())

    def test_zero_rate_completed_months_can_finalize_without_money_receipt(self):
        self.open(monthly_rate="0")
        with self.later(2):
            servicing.finalize_interest(**self.command())
            self.assertEqual(self.balance()["calculated_interest"], 0)
            with self.assertRaises(ValueError):
                self.pay("0.01")
            with workspace_context(self.workspace.pk):
                self.assertEqual(self.account.interest_periods.count(), 2)
                self.assertEqual(KhataInterestSegment.objects.first().exact_numerator, 0)

    def test_receipt_uuid_retry_conflict_and_stale_review(self):
        self.open()
        with self.later(1):
            review = servicing.preview_interest_payment(**self.args(), value="40000")
            args = dict(self.command(), value="40000", review_hash=review["review_hash"], payment_reference="Cash")
            receipt = servicing.record_interest_payment(**args)
            self.assertEqual(servicing.record_interest_payment(**dict(args, value=Decimal("40000.00"))).pk, receipt.pk)
            with self.assertRaisesMessage(ValueError, "different instructions"):
                servicing.record_interest_payment(**dict(args, payment_reference="Different bank receipt"))
            with self.assertRaisesMessage(ValueError, "changed after review"):
                servicing.record_interest_payment(**dict(args, request_key=uuid.uuid4()))
            self.assertEqual(self.balance()["paid_interest"], Decimal("40000"))
            with workspace_context(self.workspace.pk):
                self.assertEqual(self.account.interest_periods.count(), 1)
        with self.later(1, 1):
            # A confirmed receipt retry remains a retry, not an illegal backdated new receipt.
            self.assertEqual(servicing.record_interest_payment(**args).pk, receipt.pk)

    def test_finalization_retry_does_not_duplicate_months(self):
        self.open()
        with self.later(3):
            args = self.command()
            first = servicing.finalize_interest(**args)
            self.assertEqual(servicing.finalize_interest(**args).pk, first.pk)
            with self.assertRaisesMessage(ValueError, "no completed"):
                servicing.finalize_interest(**self.command())
            with workspace_context(self.workspace.pk):
                self.assertEqual(list(first.interest_periods.values_list("index", flat=True)), [0, 1, 2])
        with self.later(4):
            next_op = servicing.finalize_interest(**self.command())
            with workspace_context(self.workspace.pk):
                self.assertEqual(next_op.interest_periods.get().index, 3)

    def test_failed_allocation_rolls_back_cash_and_automatic_accrual(self):
        self.open()
        with self.later(1):
            review = servicing.preview_interest_payment(**self.args(), value="100000")
            args = dict(self.command(), value="100000", review_hash=review["review_hash"], payment_reference="Cash")
            with patch.object(servicing, "_save_allocations", side_effect=ValueError("Injected write failure")):
                with self.assertRaises(ValueError):
                    servicing.record_interest_payment(**args)
            with workspace_context(self.workspace.pk):
                self.assertFalse(KhataInterestPeriod.objects.exists())
                self.assertFalse(KhataOperation.objects.filter(kind__in=("ACCRUE", "INTEREST")).exists())
            servicing.record_interest_payment(**args)
            self.assertEqual(self.balance()["due_interest"], 0)

    def test_interest_payment_unblocks_overdue_withdrawal(self):
        self.open()
        opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="WARN", overdue="BLOCK",
            reason="Owner selected blocking", request_key=uuid.uuid4())
        with self.later(1, 1):
            self.quote()
            with self.assertRaisesMessage(ValueError, "overdue"):
                self.payout("1")
            self.pay("99999")
            with self.assertRaisesMessage(ValueError, "overdue"):
                self.payout("1")
            self.pay("1")
            self.payout("1")
            self.assertEqual(self.balance()["principal"], Decimal("100001"))

    def test_collection_does_not_require_active_series_borrower_or_current_prices(self):
        self.open()
        from apps.tenant_apps.loans.services import khata_series
        review = khata_series.preview(workspace=self.workspace, actor=self.actor, series_id=self.series.pk)
        khata_series.change_status(workspace=self.workspace, actor=self.actor, series_id=self.series.pk, to_status="PAUSED",
            reason="Pause new lending", request_key=uuid.uuid4(), review_hash=review["review_hash"])
        with workspace_context(self.workspace.pk):
            type(self.borrower).objects.filter(pk=self.borrower.pk).update(status="INACTIVE")
        with self.later(1):
            self.pay("100000")
            self.assertEqual(self.balance()["due_interest"], 0)

    def test_collection_requires_repayment_authority_independently_of_approval(self):
        self.open()
        staff = get_user_model().objects.create_user(username="interest-approver")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.workspace, role=role)
        ct = ContentType.objects.get_for_model(Company)
        perms = [Permission.objects.get_or_create(content_type=ct, codename=c, defaults={"name": c})[0]
            for c in ("data_view", "loan_approve")]
        workspace_role_permissions(role, self.workspace).set(perms)
        with self.later(1):
            review = servicing.preview_interest_payment(**dict(self.args(), actor=staff), value="1")
            with self.assertRaises(PermissionDenied):
                servicing.record_interest_payment(**dict(self.command(), actor=staff), value="1",
                    review_hash=review["review_hash"], payment_reference="Cash")
            with self.assertRaises(PermissionDenied):
                servicing.finalize_interest(**dict(self.command(), actor=staff))
            repay, _ = Permission.objects.get_or_create(content_type=ct, codename="loan_repay", defaults={"name": "loan_repay"})
            workspace_role_permissions(role, self.workspace).add(repay)
            servicing.record_interest_payment(**dict(self.command(), actor=staff), value="1",
                review_hash=review["review_hash"], payment_reference="Cash")

    def test_receipt_needs_reference_and_current_date_and_review(self):
        self.open()
        with self.later(1):
            review = servicing.preview_interest_payment(**self.args(), value="1")
            args = dict(self.command(), value="1", review_hash=review["review_hash"], payment_reference="Cash")
            with self.assertRaisesMessage(ValueError, "reference"):
                servicing.record_interest_payment(**dict(args, payment_reference=" "))
        with self.later(1, 1):
            with self.assertRaisesMessage(ValueError, "today"):
                servicing.record_interest_payment(**args)
            with self.assertRaisesMessage(ValueError, "changed after review"):
                servicing.record_interest_payment(**dict(args, business_date=timezone.localdate()))

    def test_unopened_account_has_no_collectible_interest(self):
        with self.assertRaisesMessage(ValueError, "active khata"):
            self.pay("1")
        self.deposit(); self.approve()
        with self.assertRaisesMessage(ValueError, "active khata"):
            servicing.finalize_interest(**self.command())
        self.assertEqual(self.balance()["due_interest"], 0)

    def test_saved_charge_is_authoritative_after_finalization(self):
        self.open()
        with self.later(1):
            servicing.finalize_interest(**self.command())
            from apps.tenant_apps.loans.selectors import khata as selectors
            with workspace_context(self.workspace.pk):
                original = selectors.calculated_interest_periods(self.account, timezone.localdate())
            changed = tuple(replace(p, charge=Decimal("1")) for p in original)
            with patch.object(selectors, "calculated_interest_periods", return_value=changed):
                self.assertEqual(self.balance()["due_interest"], Decimal("100000"))
                self.pay("100000")
                self.assertEqual(self.balance()["due_interest"], 0)

    def test_collection_obeys_workspace_write_restriction(self):
        self.open()
        with self.later(1):
            review = servicing.preview_interest_payment(**self.args(), value="1")
            Subscription.objects.filter(company=self.workspace).update(trial_end_date=timezone.now()-timedelta(days=8))
            with self.assertRaises(PermissionDenied):
                servicing.record_interest_payment(**self.command(), value="1", review_hash=review["review_hash"], payment_reference="Cash")
            with workspace_context(self.workspace.pk):
                self.assertFalse(KhataInterestAllocation.objects.exists())


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataShortMonthCollectionTests(InterestFixture, TestCase):
    def setUp(self):
        clock = patch("django.utils.timezone.now", return_value=datetime(2028, 1, 31, 12, tzinfo=dt_timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        super().setUp()

    def test_persisted_months_clamp_and_restore_original_day(self):
        self.open()
        with self.later(3):
            self.pay("300000")
            with workspace_context(self.workspace.pk):
                periods = list(self.account.interest_periods.order_by("index"))
                self.assertEqual([p.due_on for p in periods], [date(2028, 2, 29), date(2028, 3, 31), date(2028, 4, 30)])
                self.assertEqual([p.segments.get().period_days for p in periods], [29, 31, 30])
            self.assertEqual(self.balance()["due_interest"], 0)


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataInterestRaceTests(InterestFixture, TransactionTestCase):
    def test_two_cashiers_cannot_collect_the_same_reviewed_dues(self):
        self.open()
        with self.later(1):
            review = servicing.preview_interest_payment(**self.args(), value="60000")
            ready = Barrier(2)
            def collect(_):
                try:
                    ready.wait(timeout=15)
                    return servicing.record_interest_payment(**self.command(), value="60000",
                        review_hash=review["review_hash"], payment_reference="Cash").pk
                except ValueError:
                    return None
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(collect, range(2)))
            self.assertEqual(sum(r is not None for r in results), 1)
            self.assertEqual(self.balance()["paid_interest"], Decimal("60000"))
            self.assertEqual(self.balance()["due_interest"], Decimal("40000"))


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataInterestRLSTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        foundation.KhataRLSBoundaryTests.setUpTestData.__func__(cls)

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def populate(self, workspace, actor, account):
        opening_tests.KhataOpeningRLSTests.populate(self, workspace, actor, account)
        args = dict(workspace=workspace, actor=actor, account_id=account.pk)
        preview = opening.preview_withdrawal(**args, value="100000")
        opening.record_withdrawal(**args, value="100000", business_date=timezone.localdate(),
            request_key=uuid.uuid4(), review_hash=preview["review_hash"], payment_reference="Cash")
        later = timezone.now()+timedelta(days=65)
        Subscription.objects.filter(company=workspace).update(trial_end_date=later+timedelta(days=20))
        with patch("django.utils.timezone.now", return_value=later):
            preview = servicing.preview_interest_payment(**args, value="100")
            op = servicing.record_interest_payment(**args, value="100", business_date=timezone.localdate(),
                request_key=uuid.uuid4(), review_hash=preview["review_hash"], payment_reference="Cash")
        with workspace_context(workspace.pk):
            allocation = op.interest_allocations.get()
            period = allocation.period
            return period, period.segments.get(), allocation

    def test_interest_rows_are_forced_isolated_immutable_and_parent_guarded(self):
        own = self.populate(self.workspace, self.actor, self.account)
        foreign = self.populate(self.other_workspace, self.other_actor, self.other_account)
        with self.runtime():
            for row in own:
                self.assertEqual(type(row).objects.count(), 0)
            with workspace_context(self.workspace.pk):
                for row, other in zip(own, foreign):
                    model = type(row)
                    self.assertTrue(model.objects.filter(pk=row.pk).exists())
                    self.assertFalse(model.objects.filter(pk=other.pk).exists())
                    self.assertEqual(model.objects.filter(pk=other.pk).update(workspace_id=self.workspace.pk), 0)
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.filter(pk=row.pk).update(workspace_id=self.other_workspace.pk)
                    with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(f'DELETE FROM {connection.ops.quote_name(model._meta.db_table)} WHERE id=%s', [row.pk])
                    forged = copy.copy(row)
                    forged.pk = None
                    forged._state = copy.copy(row._state)
                    forged._state.adding = True
                    if isinstance(forged, KhataInterestPeriod):
                        forged.account_id = self.other_account.pk
                    else:
                        forged.period_id = foreign[0].pk
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.bulk_create([forged])

    def raw_receipt(self, allocations, amount, day):
        previous = self.account.operations.order_by("-sequence").first()
        return KhataOperation.objects.create(workspace=self.workspace, account=self.account,
            sequence=previous.sequence+1, kind="INTEREST", amount=amount, business_date=day,
            request_key=uuid.uuid4(), request_sha256="b"*64, created_by=self.actor,
            evidence={"schema": "khata-interest/1", "amount": str(amount), "payment_reference": "Cash", "allocations": allocations})

    def test_raw_receipts_cannot_skip_old_dues_overallocate_or_omit_children(self):
        period, _, allocation = self.populate(self.workspace, self.actor, self.account)
        with self.runtime(), workspace_context(self.workspace.pk):
            second = self.account.interest_periods.get(index=1)
            with self.assertRaisesMessage(DatabaseError, "oldest"), transaction.atomic():
                row = dict(period_id=second.pk, index=1, amount="1")
                op = self.raw_receipt([row], "1", second.due_on)
                KhataInterestAllocation.objects.create(workspace=self.workspace, operation=op, period=second, amount="1")
            with self.assertRaisesMessage(DatabaseError, "exceeds"), transaction.atomic():
                row = dict(period_id=period.pk, index=0, amount="99901")
                op = self.raw_receipt([row], "99901", second.due_on)
                KhataInterestAllocation.objects.create(workspace=self.workspace, operation=op, period=period, amount="99901")
            with self.assertRaisesMessage(DatabaseError, "fully allocated"), transaction.atomic():
                self.raw_receipt([dict(period_id=period.pk, index=0, amount="1")], "1", second.due_on)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with self.assertRaisesMessage(DatabaseError, "finalized due period"), transaction.atomic():
                row = dict(period_id=period.pk, index=0, amount="1")
                op = self.raw_receipt([row], "1", period.due_on-timedelta(days=1))
                KhataInterestAllocation.objects.create(workspace=self.workspace, operation=op, period=period, amount="1")

    def test_late_allocation_cannot_extend_original_receipt(self):
        period, _, allocation = self.populate(self.workspace, self.actor, self.account)
        with self.runtime(), workspace_context(self.workspace.pk):
            second = self.account.interest_periods.get(index=1)
            with self.assertRaisesMessage(DatabaseError, "exceeds"), transaction.atomic():
                KhataInterestAllocation.objects.create(workspace=self.workspace, operation=allocation.operation,
                    period=second, amount="1")

    def test_raw_accrual_cannot_forge_charges_or_drop_exact_segments(self):
        self.populate(self.workspace, self.actor, self.account)
        with self.runtime(), workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            first = self.account.operations.filter(kind="WITHDRAW").select_related("agreement").first()
            end = anniversary(self.account.opened_on, 3)
            from apps.tenant_apps.loans.selectors.khata import calculated_interest_periods
            period = calculated_interest_periods(self.account, end)[2]
            for wrong_charge in (True, False):
                row = servicing._period_evidence(period, {first.agreement.number: first.agreement})
                if wrong_charge:
                    row.update(actual_charge="1.00", charge="1.00")
                message = "Invalid completed" if wrong_charge else "every period and exact segment"
                with self.assertRaisesMessage(DatabaseError, message), transaction.atomic():
                    op = KhataOperation.objects.create(workspace=self.workspace, account=self.account,
                        sequence=self.account.operations.order_by("-sequence").first().sequence+1,
                        kind="ACCRUE", business_date=end, request_key=uuid.uuid4(), request_sha256="c"*64,
                        created_by=self.actor, evidence={"schema": "khata-interest/1", "periods": [row]})
                    KhataInterestPeriod.objects.create(workspace=self.workspace, account=self.account, operation=op,
                        **{k: v for k, v in row.items() if k != "segments"})
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
