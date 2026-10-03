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
from apps.tenant_apps.loans.models import KhataOperation, KhataCollateralSelection, KhataInterestAllocation
from apps.tenant_apps.loans.selectors.khata import eligible_items, held_items
from apps.tenant_apps.loans.services import khata_corrections as corrections, khata_opening as opening
from . import test_khata_custody_settlement as custody, test_khata_foundation as foundation


class CorrectionFixture(custody.CustodyFixture):
    def correct(self, source, **changes):
        review = corrections.preview_correction(**self.args(), source_id=source.pk)
        args = dict(self.command(), source_id=source.pk, review_hash=review["review_hash"],
            reason="Incorrect original entry", resolution_reference="Signed correction confirmation",
            cash_resolution="NOT_RECEIVED" if source.kind == "INTEREST" else "")
        args.update(changes)
        return corrections.record_correction(**args)

    def staff(self, *codes):
        user = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=user, company=self.workspace, role=role)
        ct = ContentType.objects.get_for_model(Company)
        permissions = [Permission.objects.get_or_create(content_type=ct, codename=code,
            defaults={"name": code})[0] for code in ("data_view", *codes)]
        workspace_role_permissions(role, self.workspace).set(permissions)
        return user


@override_settings(STORAGES=custody.revision_tests.collection.opening_tests.STORAGES)
class KhataCorrectionTests(CorrectionFixture, TestCase):
    def test_receipt_correction_restores_dues_without_changing_charges_or_principal(self):
        with self.later(1, 1):
            receipt = self.pay("25000")
            original = copy.deepcopy(receipt.evidence)
            op = self.correct(receipt)
            balances = self.balance()
            self.assertEqual(balances["paid_interest"], 0)
            self.assertEqual(balances["due_interest"], Decimal("100000"))
            self.assertEqual(balances["overdue_interest"], Decimal("100000"))
            self.assertEqual(balances["principal"], Decimal("100000"))
            self.assertEqual(balances["unused"], Decimal("9900000"))
            with workspace_context(self.workspace.pk):
                receipt.refresh_from_db()
                self.assertEqual(receipt.evidence, original)
                self.assertEqual(receipt.corrected_by.pk, op.pk)
                self.assertEqual(receipt.interest_allocations.get().amount, Decimal("25000"))
                self.assertEqual(self.account.interest_periods.count(), 1)
                self.assertEqual(self.account.interest_periods.get().charge, Decimal("100000"))
            self.pay("100000")
            self.assertEqual(self.balance()["due_interest"], 0)

    def test_refunded_receipt_requires_full_actual_cash_resolution(self):
        with self.later(1):
            receipt = self.pay("100000")
            for value in ("", "PARTIAL", "PROMISED"):
                with self.assertRaisesMessage(ValueError, "actually refunded"):
                    self.correct(receipt, cash_resolution=value)
            for changes in ({"reason": ""}, {"resolution_reference": ""}):
                with self.assertRaisesMessage(ValueError, "reason"):
                    self.correct(receipt, **changes)
            op = self.correct(receipt, cash_resolution="REFUNDED")
            self.assertEqual(op.amount, Decimal("100000"))
            self.assertEqual(op.evidence["cash_resolution"], "REFUNDED")

    def test_later_receipts_must_be_corrected_newest_first(self):
        with self.later(1):
            first, second = self.pay("25000"), self.pay("50000")
            with self.assertRaisesMessage(ValueError, str(second.pk)):
                self.correct(first)
            self.correct(second)
            self.correct(first)
            self.assertEqual(self.balance()["due_interest"], Decimal("100000"))
            self.pay("100000")
            self.assertEqual(self.balance()["paid_interest"], Decimal("100000"))

    def test_corrected_receipt_reinstates_overdue_block_and_settlement_collects_it(self):
        with self.later(1, 1):
            receipt = self.pay("100000")
            self.correct(receipt)
            self.quote()
            opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="WARN", overdue="BLOCK",
                reason="Block overdue", request_key=uuid.uuid4())
            with self.assertRaisesMessage(ValueError, "overdue"):
                self.payout("1")
            op = self.settle()
            self.assertEqual(op.interest_amount, Decimal("103333.33"))
            self.assertEqual(self.balance()["outstanding_interest"], 0)

    def test_annual_receipt_correction_preserves_monthly_charge_history(self):
        from apps.tenant_apps.loans.services import khata_accounts as drafts
        self.account = drafts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.open("ANNUAL")
        with self.later(12):
            receipt = self.pay("1200000")
            self.correct(receipt)
            self.assertEqual(self.balance()["due_interest"], Decimal("1200000"))
            with workspace_context(self.workspace.pk):
                self.assertEqual(self.account.interest_periods.count(), 12)
            self.pay("1200000")

    def test_exchange_cancellation_restores_old_items_and_reserves_actual_replacement_returns(self):
        one, two = self.replacement("10"), self.replacement("10")
        source = self.exchange([self.first], [one, two])
        original = copy.deepcopy(source.evidence)
        op = self.correct(source)
        with workspace_context(self.workspace.pk):
            self.assertEqual(held_items(self.account).count(), 3)
            self.assertEqual(set(eligible_items(self.account).values_list("pk", flat=True)), {self.first.pk})
            self.assertEqual(set(op.collateral_selections.values_list("item_id", flat=True)), {one.pk, two.pk})
            self.assertEqual(source.collateral_selections.count(), 3)
            source.refresh_from_db()
            self.assertEqual(source.evidence, original)
        with self.assertRaisesMessage(ValueError, "reservation"):
            self.handover(self.first, source)
        self.handover(one, op); self.handover(two, op)
        with workspace_context(self.workspace.pk):
            self.assertEqual(list(held_items(self.account).values_list("pk", flat=True)), [self.first.pk])
        self.assertEqual(self.balance()["principal"], Decimal("100000"))

    def test_released_original_item_can_be_exchanged_again_without_reusing_history(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        correction = self.correct(source)
        self.handover(replacement, correction)
        another = self.replacement("100")
        second = self.exchange([self.first], [another])
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.first.selections.filter(role="OUT").count(), 2)
            self.assertEqual(second.collateral_selections.filter(role="OUT").get().item_id, self.first.pk)
            self.assertEqual(list(eligible_items(self.account).values_list("pk", flat=True)), [another.pk])

    def test_actual_outgoing_handover_blocks_exchange_cancellation(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        returned = self.handover(self.first, source)
        with self.assertRaisesMessage(ValueError, str(returned.pk)):
            self.correct(source)
        with workspace_context(self.workspace.pk):
            self.assertEqual(held_items(self.account).count(), 1)

    def test_later_draw_or_revision_blocks_correction_with_identifiers(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        draw = self.payout("1")
        with self.assertRaisesMessage(ValueError, str(draw.pk)):
            self.correct(source)

    def test_cancellation_hard_ltv_and_actual_handover_due_checks_cannot_be_waived(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        self.quote("100")
        with self.assertRaisesMessage(ValueError, "LTV"):
            self.correct(source)
        self.quote()
        with self.later(1):
            self.quote()
            op = self.correct(source)
            with self.assertRaisesMessage(ValueError, "due interest"):
                self.handover(replacement, op)
            self.pay("100000")
            self.handover(replacement, op)

    def test_exchange_correction_stale_price_review_and_cash_inputs_rejected(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        review = corrections.preview_correction(**self.args(), source_id=source.pk)
        self.quote("9900")
        with self.assertRaisesMessage(ValueError, "changed after review"):
            corrections.record_correction(**self.command(), source_id=source.pk, review_hash=review["review_hash"],
                reason="Cancel", resolution_reference="Signed")
        with self.assertRaisesMessage(ValueError, "exchanges do not reverse cash"):
            self.correct(source, cash_resolution="REFUNDED")

    def test_uuid_retry_double_correction_and_foreign_source_rejected(self):
        with self.later(1):
            receipt = self.pay("25000")
            review = corrections.preview_correction(**self.args(), source_id=receipt.pk)
            args = dict(self.command(), source_id=receipt.pk, review_hash=review["review_hash"], reason="Wrong entry",
                resolution_reference="Verified", cash_resolution="NOT_RECEIVED")
            op = corrections.record_correction(**args)
            self.assertEqual(corrections.record_correction(**args).pk, op.pk)
            with self.assertRaisesMessage(ValueError, "different instructions"):
                corrections.record_correction(**dict(args, reason="Changed"))
            with self.assertRaisesMessage(ValueError, "already been corrected"):
                self.correct(receipt)
            with self.assertRaisesMessage(ValueError, "does not belong"):
                corrections.preview_correction(**self.args(), source_id=99999999)

    def test_administration_does_not_confer_money_or_custody_permissions(self):
        with self.later(1):
            receipt = self.pay("100000")
            admin = self.staff("workspace_settings")
            with self.assertRaises(PermissionDenied):
                self.correct(receipt, actor=admin)
            cashier = self.staff("loan_repay")
            with self.assertRaises(PermissionDenied):
                corrections.preview_correction(**dict(self.args(), actor=cashier), source_id=receipt.pk)
            authorized = self.staff("workspace_settings", "loan_repay")
            self.correct(receipt, actor=authorized)

    def test_exchange_child_failure_rolls_back_original_eligibility(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        with patch.object(corrections, "_reserve", side_effect=ValueError("Injected failure")):
            with self.assertRaises(ValueError):
                self.correct(source)
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.operations.filter(kind="CORRECT").exists())
            self.assertEqual(list(eligible_items(self.account).values_list("pk", flat=True)), [replacement.pk])
        self.correct(source)

    def test_exchange_correction_requires_release_and_edit_capabilities(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        for codes in (("workspace_settings", "data_edit"), ("workspace_settings", "loan_release")):
            admin = self.staff(*codes)
            with self.assertRaises(PermissionDenied):
                self.correct(source, actor=admin)
        authorized = self.staff("workspace_settings", "data_edit", "loan_release")
        self.correct(source, actor=authorized)

    def test_corrections_obey_workspace_write_restriction(self):
        from apps.subscriptions.models import Subscription
        with self.later(1):
            receipt = self.pay("100000")
            review = corrections.preview_correction(**self.args(), source_id=receipt.pk)
            Subscription.objects.filter(company=self.workspace).update(trial_end_date=timezone.now()-timedelta(days=8))
            with self.assertRaises(PermissionDenied):
                corrections.record_correction(**self.command(), source_id=receipt.pk, review_hash=review["review_hash"],
                    reason="Wrong", resolution_reference="Verified", cash_resolution="NOT_RECEIVED")
            with workspace_context(self.workspace.pk):
                self.assertFalse(self.account.operations.filter(kind="CORRECT").exists())

    def test_payout_charge_revision_and_physical_corrections_fail_closed(self):
        with workspace_context(self.workspace.pk):
            unsupported = list(self.account.operations.exclude(kind__in=("INTEREST", "EXCHANGE")))
        for source in unsupported:
            with self.assertRaisesMessage(ValueError, "not supported"):
                self.correct(source)
        self.revise(rate="2")
        with workspace_context(self.workspace.pk):
            revision = self.account.operations.get(kind="REVISE")
        with self.assertRaisesMessage(ValueError, "not supported"):
            self.correct(revision)
        settled = self.settle()
        with self.assertRaisesMessage(ValueError, "active"):
            self.correct(settled)


@override_settings(STORAGES=custody.revision_tests.collection.opening_tests.STORAGES)
class KhataCorrectionRaceTests(CorrectionFixture, TransactionTestCase):
    def test_concurrent_exchange_corrections_commit_once(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        review = corrections.preview_correction(**self.args(), source_id=source.pk)
        ready = Barrier(2)
        def cancel(_):
            try:
                ready.wait(timeout=15)
                return corrections.record_correction(**self.command(), source_id=source.pk, review_hash=review["review_hash"],
                    reason="Cancel", resolution_reference="Signed").pk
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(cancel, range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)


@override_settings(STORAGES=custody.revision_tests.collection.opening_tests.STORAGES)
class KhataCorrectionRLSTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.runtime_role = "khata_correction_rls_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def raw(self, source, evidence, amount=None):
        return opening._operation(self.account, self.actor, uuid.uuid4(), "a"*64, "CORRECT", timezone.localdate(),
            evidence, amount=source.amount if amount is None else amount, agreement=source.agreement, correction_of=source)

    def test_receipt_correction_evidence_math_dependencies_and_scope_enforced(self):
        with self.later(1):
            receipt = self.pay("25000")
            review = corrections.preview_correction(**self.args(), source_id=receipt.pk)
            evidence = dict(review["snapshot"], reason="Wrong", resolution_reference="Verified", cash_resolution="NOT_RECEIVED")
            with self.runtime(), workspace_context(self.workspace.pk):
                for changes in ({"reason": ""}, {"cash_resolution": "PROMISED"}, {"allocations": []}, {"account_id": 999999},
                                {"amount": "1"}, {"principal": "1"}, {"source_sequence": 999999}):
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        self.raw(receipt, dict(evidence, **changes))
                with self.assertRaises(DatabaseError), transaction.atomic():
                    self.raw(receipt, evidence, amount="1")
            later = self.pay("1000")
            with self.runtime(), workspace_context(self.workspace.pk):
                with self.assertRaisesMessage(DatabaseError, "dependencies"), transaction.atomic():
                    self.raw(receipt, dict(evidence, last_sequence=later.sequence))

    def test_correction_and_original_evidence_are_isolated_and_immutable(self):
        with self.later(1):
            receipt = self.pay("25000")
            correction = self.correct(receipt)
            other, _, _ = foundation.fixture(uuid.uuid4().hex[:8])
            with self.runtime():
                self.assertFalse(KhataOperation.objects.exists())
                with workspace_context(other.pk):
                    self.assertFalse(KhataOperation.objects.filter(pk=correction.pk).exists())
                with workspace_context(self.workspace.pk):
                    for op in (receipt, correction):
                        with self.assertRaises(DatabaseError), transaction.atomic():
                            KhataOperation.objects.filter(pk=op.pk).update(evidence={})
                        with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                            cursor.execute("DELETE FROM loans_khataoperation WHERE id=%s", [op.pk])
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        KhataInterestAllocation.objects.create(workspace=self.workspace, operation=correction,
                            period=receipt.interest_allocations.get().period, amount="1")

    def test_exchange_correction_cannot_omit_returns_or_waive_retained_ltv(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        review = corrections.preview_correction(**self.args(), source_id=source.pk)
        evidence = dict(review["snapshot"], reason="Cancel", resolution_reference="Signed", cash_resolution="")
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaisesMessage(DatabaseError, "complete valuations"), transaction.atomic():
                op = self.raw(source, evidence)
                opening._save_valuations(op, evidence)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        self.quote("100")
        with self.runtime(), workspace_context(self.workspace.pk):
            ids = set(eligible_items(self.account).values_list("pk", flat=True)) | {self.first.pk}
            evidence["valuations"] = custody.custody._values(self.account, self.workspace, timezone.localdate(), list(held_items(self.account).filter(pk__in=ids)))
            with self.assertRaisesMessage(DatabaseError, "retained collateral LTV"), transaction.atomic():
                op = self.raw(source, evidence)
                opening._save_valuations(op, evidence)
                custody.custody._reserve(op, evidence["outgoing_ids"])
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_direct_selection_insert_cannot_bypass_active_role_uniqueness(self):
        replacement = self.replacement("100")
        source = self.exchange([self.first], [replacement])
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataCollateralSelection.objects.create(workspace=self.workspace, operation=source, item=self.first, role="OUT")
