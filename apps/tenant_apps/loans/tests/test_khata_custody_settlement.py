import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
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
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import workspace_role_permissions
from apps.tenant_apps.loans.models import KhataAccount, KhataOperation, KhataCollateralSelection, KhataInterestPeriod
from apps.tenant_apps.loans.selectors.khata import held_items, eligible_items
from apps.tenant_apps.loans.services import khata_collateral as custody, khata_settlement as settlement, khata_revisions as revisions, khata_opening as opening
from . import test_khata_revisions as revision_tests, test_khata_foundation as foundation


class CustodyFixture(revision_tests.RevisionFixture):
    def setUp(self):
        super().setUp()
        self.open()
        with workspace_context(self.workspace.pk):
            self.first = self.account.collateral.first()

    def quote(self, value="10000"):
        from apps.tenant_apps.rates.models import Rate
        from apps.tenant_apps.rates.services import record_quote
        moment = timezone.now()
        with workspace_context(self.workspace.pk):
            latest = Rate.objects.order_by("-timestamp").first()
            recorded = max(moment, latest.timestamp + timedelta(microseconds=1)) if latest else moment
            with patch("django.utils.timezone.now", return_value=recorded):
                return record_quote(workspace=self.workspace, actor=self.actor, values=dict(rate_source=self.source,
                    metal="Gold", purity="24k", currency="INR", buying_rate=Decimal(value),
                    selling_rate=Decimal(value), effective_at=moment))

    def replacement(self, grams="20", **changes):
        return self.deposit(gross_weight=grams, net_weight=grams, **changes)

    def exchange(self, outgoing, incoming, **changes):
        args = dict(self.args(), outgoing_ids=[i.pk for i in outgoing], incoming_ids=[i.pk for i in incoming])
        review = custody.preview_exchange(**args)
        command = dict(args, request_key=uuid.uuid4(), business_date=timezone.localdate(), review_hash=review["review_hash"], reason="Borrower exchanged collateral")
        command.update(changes)
        return custody.record_exchange(**command)

    def handover(self, item, source, **changes):
        args = dict(self.args(), item_id=item.pk, parent_id=source.pk)
        review = custody.preview_handover(**args)
        command = dict(args, request_key=uuid.uuid4(), business_date=timezone.localdate(), review_hash=review["review_hash"], recipient="Borrower", reference="Signed handover")
        command.update(changes)
        return custody.record_handover(**command)

    def settle(self, **changes):
        review = settlement.preview_settlement(**self.args())
        args = dict(self.command(), review_hash=review["review_hash"], payment_reference="Settlement received")
        args.update(changes)
        return settlement.record_settlement(**args)

    def reduce_with_return(self, outgoing, repayment="40000", limit="60000"):
        self.proposal(limit)
        review = revisions.preview_revision(**self.args(), principal_repayment=repayment, outgoing_ids=[i.pk for i in outgoing])
        approval = revisions.approve_revision(**self.command(), principal_repayment=repayment, outgoing_ids=[i.pk for i in outgoing],
            review_hash=review["review_hash"], agreement_reference="Borrower signed reduction")
        return self.activate(approval)


@override_settings(STORAGES=revision_tests.collection.opening_tests.STORAGES)
class KhataCustodyTests(CustodyFixture, TestCase):
    def test_grouped_exchange_reserves_and_excludes_old_items_before_handover(self):
        one, two = self.replacement("10"), self.replacement("10")
        op = self.exchange([self.first], [one, two])
        self.assertEqual(self.balance()["principal"], Decimal("100000"))
        with workspace_context(self.workspace.pk):
            self.assertEqual(held_items(self.account).count(), 3)
            self.assertEqual(set(eligible_items(self.account).values_list("pk", flat=True)), {one.pk, two.pk})
            self.assertEqual(op.collateral_selections.count(), 3)
            self.assertTrue(op.evidence["warnings"])
        self.payout("50000")
        with self.assertRaisesMessage(ValueError, "backing"):
            self.payout("0.01")
        self.handover(self.first, op)
        with workspace_context(self.workspace.pk):
            self.assertEqual(held_items(self.account).count(), 2)

    def test_many_to_one_exchange_and_replacement_cannot_be_reused(self):
        extra, replacement = self.replacement("30"), self.replacement("150")
        op = self.exchange([self.first, extra], [replacement])
        self.assertFalse(op.evidence["warnings"])
        another = self.replacement("1")
        with self.assertRaisesMessage(ValueError, "already used"):
            self.exchange([another], [replacement])
        with self.assertRaisesMessage(ValueError, "reserved"):
            self.exchange([self.first], [another])

    def test_warn_allows_value_and_ltv_shortfall_but_no_cash_waiver(self):
        replacement = self.replacement("1")
        op = self.exchange([self.first], [replacement])
        self.assertEqual(op.evidence["exchange_policy"], "WARN")
        self.assertLess(Decimal(op.evidence["backing"]), self.balance()["principal"])
        with self.assertRaisesMessage(ValueError, "backing"):
            self.payout("1")
        # Previously confirmed exchange handover remains valid after policy changes.
        opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="BLOCK", overdue="BLOCK", reason="Changed policy", request_key=uuid.uuid4())
        self.handover(self.first, op)

    def test_strict_policy_blocks_shortfall_and_allows_at_least_equal_value(self):
        opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="BLOCK", overdue="WARN", reason="Strict", request_key=uuid.uuid4())
        small = self.replacement("20")
        with self.assertRaisesMessage(ValueError, "shortfalls"):
            self.exchange([self.first], [small])
        sufficient = self.replacement("100")
        self.exchange([self.first], [sufficient])

    def test_cross_metal_duplicates_overlap_and_foreign_items_are_rejected(self):
        silver = self.replacement("100", metal="SILVER")
        for outgoing, incoming in (([self.first], [silver]), ([self.first, self.first], [silver]), ([self.first], [self.first])):
            with self.assertRaises(ValueError):
                self.exchange(outgoing, incoming)
        with self.assertRaises(ValueError):
            custody.preview_exchange(**self.args(), outgoing_ids=[self.first.pk], incoming_ids=[99999999])

    def test_overdue_policy_and_stale_prices_and_policy_are_rechecked(self):
        replacement = self.replacement("100")
        review = custody.preview_exchange(**self.args(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk])
        self.quote("9900")
        with self.assertRaisesMessage(ValueError, "changed after review"):
            custody.record_exchange(**self.command(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk], review_hash=review["review_hash"], reason="Exchange")
        with self.later(1, 1):
            with self.assertRaises(ValueError):
                self.exchange([self.first], [replacement])
            self.quote()
            opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="WARN", overdue="BLOCK", reason="Overdue policy", request_key=uuid.uuid4())
            with self.assertRaisesMessage(ValueError, "overdue"):
                self.exchange([self.first], [replacement])
            self.pay("100000")
            self.exchange([self.first], [replacement])

    def test_exchange_requires_current_mandatory_photos(self):
        from apps.tenant_apps.loans.services.origination_settings import set_collateral_photo_requirement
        replacement = self.replacement()
        with workspace_context(self.workspace.pk):
            set_collateral_photo_requirement(workspace=self.workspace, actor=self.actor, required=True)
        with self.assertRaisesMessage(ValueError, "photograph"):
            self.exchange([self.first], [replacement])
        self.photo(self.first); self.photo(replacement)
        self.exchange([self.first], [replacement])

    def test_reduction_reserves_return_with_hard_ltv(self):
        retained = self.replacement("100")
        op = self.reduce_with_return([self.first])
        self.assertEqual(self.balance()["principal"], Decimal("60000"))
        self.assertEqual(self.balance()["unused"], 0)
        with workspace_context(self.workspace.pk):
            self.assertEqual(list(eligible_items(self.account).values_list("pk", flat=True)), [retained.pk])
        self.handover(self.first, op)
        with workspace_context(self.workspace.pk):
            self.assertFalse(held_items(self.account).filter(pk=self.first.pk).exists())

    def test_reduction_warning_cannot_waive_retained_ltv_or_due_interest(self):
        self.replacement("1")
        with self.assertRaisesMessage(ValueError, "Retained collateral"):
            self.reduce_with_return([self.first])
        with self.later(1):
            self.quote(); self.replacement("100")
            with self.assertRaisesMessage(ValueError, "due interest"):
                self.reduce_with_return([self.first])
            self.pay("100000")
            self.reduce_with_return([self.first])

    def test_reduction_handover_rechecks_later_dues_and_prices(self):
        self.replacement("100")
        op = self.reduce_with_return([self.first])
        with self.later(1):
            with self.assertRaisesMessage(ValueError, "due interest"):
                self.handover(self.first, op)
            self.pay("100000")
            with self.assertRaises(ValueError):
                self.handover(self.first, op)
            self.quote("100")
            with self.assertRaisesMessage(ValueError, "Retained collateral"):
                self.handover(self.first, op)
            self.quote()
            self.handover(self.first, op)

    def test_failed_exchange_children_roll_back_and_uuid_retry_is_safe(self):
        replacement = self.replacement("100")
        review = custody.preview_exchange(**self.args(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk])
        args = dict(self.command(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk], review_hash=review["review_hash"], reason="Exchange")
        with patch.object(custody, "_reserve", side_effect=ValueError("Injected failure")):
            with self.assertRaises(ValueError):
                custody.record_exchange(**args)
        with workspace_context(self.workspace.pk):
            self.assertFalse(KhataCollateralSelection.objects.exists())
            self.assertFalse(self.account.operations.filter(kind="EXCHANGE").exists())
        op = custody.record_exchange(**args)
        self.assertEqual(custody.record_exchange(**args).pk, op.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            custody.record_exchange(**dict(args, reason="Different"))

    def test_handover_requires_reservation_recipient_and_reference_and_no_double_return(self):
        replacement = self.replacement("100")
        op = self.exchange([self.first], [replacement])
        with self.assertRaises(ValueError):
            self.handover(replacement, op)
        with self.assertRaisesMessage(ValueError, "recipient"):
            self.handover(self.first, op, recipient="")
        review = custody.preview_handover(**self.args(), item_id=self.first.pk, parent_id=op.pk)
        args = dict(self.command(), item_id=self.first.pk, parent_id=op.pk, review_hash=review["review_hash"], recipient="Borrower", reference="Signed")
        returned = custody.record_handover(**args)
        self.assertEqual(custody.record_handover(**args).pk, returned.pk)
        with self.assertRaises(ValueError):
            self.handover(self.first, op)


@override_settings(STORAGES=revision_tests.collection.opening_tests.STORAGES)
class KhataSettlementTests(CustodyFixture, TestCase):
    def test_same_day_settlement_collects_minimum_and_preserves_pending_custody(self):
        op = self.settle()
        self.assertEqual(op.amount, Decimal("100000"))
        self.assertEqual(op.interest_amount, Decimal("100000"))
        balances = self.balance()
        self.assertEqual(balances["principal"], 0)
        self.assertEqual(balances["unused"], 0)
        self.assertEqual(balances["outstanding_interest"], 0)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "SETTLED_RETURN_PENDING")
            p = op.interest_periods.get()
            self.assertEqual(p.charged_through, self.started_on)
            self.assertEqual(p.segments.count(), 0)
            self.assertEqual(held_items(self.account).count(), 1)
        with self.later(3):
            self.assertEqual(self.balance()["calculated_interest"], Decimal("100000"))
            self.handover(self.first, op)
            with workspace_context(self.workspace.pk):
                self.account.refresh_from_db()
                self.assertEqual(self.account.state, "CLOSED")
                self.assertEqual(self.account.settled_on, self.started_on)

    def test_annual_four_month_closure_collects_only_four_months(self):
        # New annual account; the existing fixture account is not converted.
        from apps.tenant_apps.loans.services import khata_accounts as drafts
        self.account = drafts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.open("ANNUAL")
        with self.later(4):
            op = self.settle()
            self.assertEqual(op.interest_amount, Decimal("400000"))
            with workspace_context(self.workspace.pk):
                self.assertEqual(op.interest_periods.count(), 4)
                self.assertEqual(op.interest_allocations.count(), 4)

    def test_later_partial_month_actual_days_and_paid_receipts_are_deducted(self):
        with self.later(1):
            self.pay("25000")
        with self.later(1, 10):
            # November 10 to December 10 has 30 days.
            op = self.settle()
            self.assertEqual(op.interest_amount, Decimal("108333.33"))
            with workspace_context(self.workspace.pk):
                partial = op.interest_periods.get(index=1)
                self.assertEqual(partial.actual_charge, Decimal("33333.33"))
                self.assertEqual(partial.minimum_adjustment, 0)
                self.assertEqual(self.account.interest_periods.get(index=0).charge, Decimal("100000"))

    def test_closing_partial_month_uses_exact_activated_revision_segments(self):
        with self.later(1, 5):
            self.revise("15000000", "2")
        with self.later(1, 10):
            op = self.settle()
            self.assertEqual(op.interest_amount, Decimal("166666.67"))
            with workspace_context(self.workspace.pk):
                partial = op.interest_periods.get(index=1)
                self.assertEqual(partial.actual_charge, Decimal("66666.67"))
                self.assertEqual(list(partial.segments.values_list("start_on", "end_on")),
                    [(self.started_on + timedelta(days=31), self.started_on + timedelta(days=36)),
                     (self.started_on + timedelta(days=36), self.started_on + timedelta(days=41))])

    def test_settlement_with_pending_exchange_preserves_each_original_handover_source(self):
        replacement = self.replacement("1")
        exchange = self.exchange([self.first], [replacement])
        settlement_op = self.settle()
        with workspace_context(self.workspace.pk):
            self.assertEqual(list(settlement_op.collateral_selections.values_list("item_id", flat=True)), [replacement.pk])
        self.handover(self.first, exchange)
        self.handover(replacement, settlement_op)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "CLOSED")

    def test_settled_accounts_block_all_new_financial_and_collateral_operations(self):
        self.settle()
        for action in (lambda: self.payout("1"), lambda: self.deposit(), lambda: self.photo(self.first),
                       lambda: self.revise(rate="2"), lambda: self.pay("1"), lambda: self.settle()):
            with self.assertRaises(ValueError):
                action()

    def test_settlement_failure_rolls_back_money_charges_and_lifecycle(self):
        review = settlement.preview_settlement(**self.args())
        args = dict(self.command(), review_hash=review["review_hash"], payment_reference="Cash")
        with patch.object(settlement, "_reserve", side_effect=ValueError("Injected failure")):
            with self.assertRaises(ValueError):
                settlement.record_settlement(**args)
        self.assertEqual(self.balance()["principal"], Decimal("100000"))
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "ACTIVE")
            self.assertFalse(KhataInterestPeriod.objects.exists())
        op = settlement.record_settlement(**args)
        self.assertEqual(settlement.record_settlement(**args).pk, op.pk)

    def test_settlement_stale_quote_and_separate_payment_handover_permissions(self):
        staff = get_user_model().objects.create_user(username="settlement-cashier")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.workspace, role=role)
        ct = ContentType.objects.get_for_model(Company)
        perms = [Permission.objects.get_or_create(content_type=ct, codename=c, defaults={"name": c})[0] for c in ("data_view", "loan_repay")]
        workspace_role_permissions(role, self.workspace).set(perms)
        review = settlement.preview_settlement(**self.args())
        self.deposit()
        with self.assertRaisesMessage(ValueError, "changed after review"):
            settlement.record_settlement(**self.command(), review_hash=review["review_hash"], payment_reference="Cash")
        op = self.settle(actor=staff)
        with self.assertRaises(PermissionDenied):
            self.handover(self.first, op, actor=staff)
        self.handover(self.first, op)


@override_settings(STORAGES=revision_tests.collection.opening_tests.STORAGES)
class KhataCustodyRaceTests(CustodyFixture, TransactionTestCase):
    def test_concurrent_exchange_cannot_reserve_the_same_outgoing_item_twice(self):
        replacement = self.replacement("100")
        args = dict(self.args(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk])
        review = custody.preview_exchange(**args)
        ready = Barrier(2)
        def exchange(_):
            try:
                ready.wait(timeout=15)
                return custody.record_exchange(**args, request_key=uuid.uuid4(), business_date=timezone.localdate(),
                    review_hash=review["review_hash"], reason="Exchange").pk
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(exchange, range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataCollateralSelection.objects.filter(item=self.first, role="OUT").count(), 1)

    def test_concurrent_settlement_does_not_collect_money_twice(self):
        review = settlement.preview_settlement(**self.args())
        ready = Barrier(2)
        def collect(_):
            try:
                ready.wait(timeout=15)
                return settlement.record_settlement(**self.command(), review_hash=review["review_hash"], payment_reference="Cash").pk
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(collect, range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(self.balance()["principal"], 0)


@override_settings(STORAGES=revision_tests.collection.opening_tests.STORAGES)
class KhataCustodyRLSTests(CustodyFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.runtime_role = "khata_custody_rls_"+uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def test_selection_rows_are_isolated_immutable_and_parent_guarded(self):
        replacement = self.replacement("100")
        op = self.exchange([self.first], [replacement])
        other_ws, actor, borrower = foundation.fixture(uuid.uuid4().hex[:8])
        with self.runtime():
            self.assertFalse(KhataCollateralSelection.objects.exists())
            with workspace_context(other_ws.pk):
                self.assertFalse(KhataCollateralSelection.objects.exists())
            with workspace_context(self.workspace.pk):
                selection = op.collateral_selections.filter(role="OUT").get()
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataCollateralSelection.objects.filter(pk=selection.pk).update(role="IN")
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute("DELETE FROM loans_khatacollateralselection WHERE id=%s", [selection.pk])
                forged = copy.copy(selection)
                forged.pk = None; forged.workspace_id = other_ws.pk
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataCollateralSelection.objects.bulk_create([forged])

    def test_raw_exchange_cannot_omit_reservations_or_bypass_strict_policy(self):
        replacement = self.replacement("1")
        review = custody.preview_exchange(**self.args(), outgoing_ids=[self.first.pk], incoming_ids=[replacement.pk])
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaisesMessage(DatabaseError, "selection children"), transaction.atomic():
                op = opening._operation(self.account, self.actor, uuid.uuid4(), "a"*64, "EXCHANGE", timezone.localdate(),
                    review["snapshot"], agreement_id=review["snapshot"].get("agreement_id") or self.account.operations.filter(kind="WITHDRAW").first().agreement_id)
                opening._save_valuations(op, review["snapshot"])
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

        policy = opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="BLOCK", overdue="WARN",
            reason="Strict", request_key=uuid.uuid4())
        evidence = dict(review["snapshot"], policy_id=policy.pk, exchange_policy="BLOCK")
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaisesMessage(DatabaseError, "Strict exchange policy"), transaction.atomic():
                op = opening._operation(self.account, self.actor, uuid.uuid4(), "c"*64, "EXCHANGE", timezone.localdate(),
                    evidence, agreement_id=self.account.operations.filter(kind="WITHDRAW").first().agreement_id, policy=policy)
                opening._save_valuations(op, evidence)
                custody._reserve(op, evidence["outgoing_ids"], evidence["incoming_ids"])
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_raw_reduction_handover_cannot_bypass_retained_ltv(self):
        self.replacement("100")
        source = self.reduce_with_return([self.first])
        self.quote("100")
        with self.runtime(), workspace_context(self.workspace.pk):
            evidence = dict(schema="khata-custody/1", outgoing_ids=[], recipient="Borrower", reference="Signed",
                valuations=custody._values(self.account, self.workspace, timezone.localdate(), list(eligible_items(self.account))))
            with self.assertRaisesMessage(DatabaseError, "retained collateral LTV"), transaction.atomic():
                op = opening._operation(self.account, self.actor, uuid.uuid4(), "d"*64, "HANDOVER", timezone.localdate(),
                    evidence, item=self.first, parent=source)
                opening._save_valuations(op, evidence)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_raw_settlement_cannot_forgo_interest_or_forge_lifecycle(self):
        review = settlement.preview_settlement(**self.args())
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataAccount.objects.filter(pk=self.account.pk).update(state="CLOSED", settled_on=timezone.localdate())
            with self.assertRaisesMessage(DatabaseError, "finalize interest"), transaction.atomic():
                evidence = dict(review["snapshot"], payment_reference="Cash", periods=[], allocations=[])
                op = opening._operation(self.account, self.actor, uuid.uuid4(), "b"*64, "SETTLE", timezone.localdate(), evidence,
                    amount="100000", interest_amount=0, agreement_id=evidence["agreement_id"])
                custody._reserve(op, evidence["outgoing_ids"])
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
