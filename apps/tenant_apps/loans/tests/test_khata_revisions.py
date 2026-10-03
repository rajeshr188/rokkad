import copy
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone as dt_timezone
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

from apps.orgs.models import Company, Role, Membership
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import workspace_role_permissions
from apps.tenant_apps.loans.models import KhataOperation, KhataAgreementRevision, KhataInterestSegment, LoanLicense
from apps.tenant_apps.loans.selectors.khata import account_position, effective_agreement
from apps.tenant_apps.loans.services import khata_revisions as revisions, khata_accounts as drafts, khata_opening as opening, khata_servicing as servicing
from . import test_khata_interest_collection as collection, test_khata_foundation as foundation


class RevisionFixture(collection.InterestFixture):
    def setUp(self):
        clock = patch("django.utils.timezone.now", return_value=datetime(2026, 10, 10, 12, tzinfo=dt_timezone.utc))
        clock.start()
        self.addCleanup(clock.stop)
        super().setUp()

    def proposal(self, limit=None, rate=None, **changes):
        with workspace_context(self.workspace.pk):
            active = effective_agreement(self.account)
            latest = self.account.agreement_revisions.order_by("-number").first()
            values = {f: getattr(active, f) for f in ("agreed_limit", "monthly_rate", "ltv", "frequency", "lender_name", "lender_address")}
        values.update(self.args(), expected_revision=latest.number, request_key=uuid.uuid4(),
            intended_on=timezone.localdate(), reason="Borrower agreed to revised terms")
        if limit is not None:
            values["agreed_limit"] = limit
        if rate is not None:
            values["monthly_rate"] = rate
        values.update(changes)
        return drafts.propose_revision(**values)

    def approve_change(self, repayment="0", actor=None):
        actor = actor or self.actor
        preview = revisions.preview_revision(**dict(self.args(), actor=actor), principal_repayment=repayment)
        return revisions.approve_revision(**dict(self.command(), actor=actor), principal_repayment=repayment,
            review_hash=preview["review_hash"], agreement_reference="Signed borrower agreement")

    def activate(self, approval, actor=None, **changes):
        actor = actor or self.actor
        preview = revisions.preview_activation(**dict(self.args(), actor=actor), approval_id=approval.pk)
        values = dict(self.command(), actor=actor, approval_id=approval.pk, review_hash=preview["review_hash"], payment_reference="Cash received")
        values.update(changes)
        return revisions.activate_revision(**values)

    def revise(self, limit=None, rate=None, repayment="0"):
        self.proposal(limit, rate)
        return self.activate(self.approve_change(repayment))

    def position(self):
        with workspace_context(self.workspace.pk):
            return account_position(self.account)


@override_settings(STORAGES=collection.opening_tests.STORAGES)
class KhataRevisionTests(RevisionFixture, TestCase):
    def test_proposal_and_approval_do_not_change_interest_or_availability(self):
        self.open()
        with self.later(1):
            proposal = self.proposal("15000000", "2")
            self.approve_change()
            self.assertEqual(self.position().limit, Decimal("10000000"))
            self.assertEqual(self.balance()["due_interest"], Decimal("100000"))
            # Pending terms do not accidentally govern or block ordinary draws.
            self.quote(); payout = self.payout("1")
            self.assertNotEqual(payout.agreement_id, proposal.pk)
        with self.later(2):
            self.assertEqual(self.balance()["due_interest"], Decimal("200000"))

    def test_mid_month_limit_increase_splits_interest_without_paying_cash(self):
        self.open()
        number = self.account.account_number
        with self.later(1, 15):
            activation = self.revise("15000000")
            self.assertEqual(activation.amount, 0)
            self.assertEqual(self.position().principal, Decimal("100000"))
            self.assertEqual(self.position().unused, Decimal("14900000"))
            self.quote()
            draw = self.payout("600000")
            self.assertEqual(draw.agreement_id, activation.agreement_id)
            self.assertEqual(draw.approval_id, activation.approval_id)
            with self.assertRaisesMessage(ValueError, "backing"):
                self.payout("50000.01")
        with self.later(2):
            self.assertEqual(self.balance()["due_interest"], Decimal("225000"))
            self.pay("225000")
            with workspace_context(self.workspace.pk):
                month = self.account.interest_periods.get(index=1)
                self.assertEqual(month.charge, Decimal("125000"))
                self.assertEqual(list(month.segments.values_list("agreement_id", flat=True))[-1], activation.agreement_id)
                self.assertEqual(month.segments.count(), 2)
                self.account.refresh_from_db()
                self.assertEqual(self.account.account_number, number)
                self.assertEqual(self.account.opened_on, self.started_on)

    def test_rate_change_preserves_limit_entitlement_and_annual_due_date(self):
        self.open("ANNUAL")
        with self.later(1, 15):
            self.revise(rate="2")
            self.assertEqual(self.position().unused, Decimal("9900000"))
        with self.later(2):
            servicing.finalize_interest(**self.command())
            self.assertEqual(self.balance()["calculated_interest"], Decimal("250000"))
            self.assertEqual(self.balance()["due_interest"], 0)
        with self.later(12):
            self.assertEqual(self.balance()["due_interest"], Decimal("2250000"))
            self.pay("2250000")

    def test_first_month_floor_is_original_and_never_restarts(self):
        self.open()
        with self.later(0, 10):
            self.revise(rate="0.5")
        with self.later(1):
            self.pay("100000")
            with workspace_context(self.workspace.pk):
                period = self.account.interest_periods.get(index=0)
                self.assertEqual(period.actual_charge, Decimal("66129.03"))
                self.assertEqual(period.minimum_adjustment, Decimal("33870.97"))
        with self.later(2):
            self.assertEqual(self.balance()["due_interest"], Decimal("50000"))
            self.pay("50000")

    def test_same_day_changes_use_last_activated_terms_and_original_minimum(self):
        self.open()
        self.revise(rate="2")
        self.revise(rate="0.25")
        with self.later(1):
            self.pay("100000")
            with workspace_context(self.workspace.pk):
                period = self.account.interest_periods.get(index=0)
                self.assertEqual(period.actual_charge, Decimal("25000"))
                self.assertEqual(period.segments.count(), 1)
                self.assertEqual(period.segments.get().agreement_id, effective_agreement(self.account).pk)

    def test_reduction_requires_actual_repayment_and_does_not_restore_entitlement(self):
        self.open()
        self.proposal("60000")
        with self.assertRaisesMessage(ValueError, "Repay principal"):
            self.approve_change()
        approval = self.approve_change("40000")
        self.assertEqual(self.position().principal, Decimal("100000"))
        with self.assertRaisesMessage(ValueError, "repayment reference"):
            self.activate(approval, payment_reference="")
        op = self.activate(approval)
        self.assertEqual(op.amount, Decimal("40000"))
        self.assertEqual(self.position().principal, Decimal("60000"))
        self.assertEqual(self.position().unused, 0)
        with self.assertRaises(ValueError):
            self.payout("1")
        self.revise("100000")
        self.assertEqual(self.position().principal, Decimal("60000"))
        self.assertEqual(self.position().unused, Decimal("40000"))
        self.payout("40000")
        with self.assertRaises(ValueError):
            self.payout("0.01")

    def test_unused_reduction_needs_no_fictitious_repayment_or_price(self):
        self.open()
        with self.later(1, 1):
            # No current price; nothing is being paid out or handed back.
            self.revise("8000000")
            self.assertEqual(self.position().principal, Decimal("100000"))
            self.assertEqual(self.position().unused, Decimal("7900000"))
            self.assertEqual(self.balance()["overdue_interest"], Decimal("100000"))

    def test_no_repayment_on_rate_only_increase_or_above_principal(self):
        self.open()
        for limit, rate, repayment in ((None, "2", "1"), ("15000000", "1", "1"), ("9000000", "1", "100001")):
            self.proposal(limit, rate)
            with self.assertRaises(ValueError):
                self.approve_change(repayment)
        self.assertEqual(self.position().principal, Decimal("100000"))

    def test_frozen_payment_frequency_ltv_identity_and_noop(self):
        self.open()
        for changes in ({"frequency": "ANNUAL"}, {"ltv": "0.80"}, {"lender_name": "Other lender"}, {"lender_address": "Other address"}):
            with self.assertRaisesMessage(ValueError, "preserve"):
                self.proposal("12000000", **changes)
        with self.assertRaisesMessage(ValueError, "already active"):
            self.proposal()

    def test_stale_approval_after_payment_requires_reapproval(self):
        self.open()
        with self.later(1):
            self.proposal(rate="2")
            approval = self.approve_change()
            self.pay("1")
            with self.assertRaisesMessage(ValueError, "stale"):
                self.activate(approval)
            self.activate(self.approve_change())

    def test_midnight_and_superseding_proposal_invalidate_approval(self):
        self.open()
        self.proposal(rate="2")
        approval = self.approve_change()
        self.proposal(rate="3")
        with self.assertRaisesMessage(ValueError, "stale"):
            self.activate(approval)
        approval = self.approve_change()
        with self.later(0, 1):
            with self.assertRaisesMessage(ValueError, "today"):
                self.activate(approval)
            with self.assertRaisesMessage(ValueError, "today"):
                self.proposal(rate="3", intended_on=self.started_on)
            self.proposal(rate="3")
            self.activate(self.approve_change())

    def test_activation_and_approval_retries_conflicts_and_double_activation(self):
        self.open()
        self.proposal(rate="2")
        preview = revisions.preview_revision(**self.args())
        approval_args = dict(self.command(), review_hash=preview["review_hash"], agreement_reference="Signed")
        approval = revisions.approve_revision(**approval_args)
        self.assertEqual(revisions.approve_revision(**approval_args).pk, approval.pk)
        preview = revisions.preview_activation(**self.args(), approval_id=approval.pk)
        args = dict(self.command(), approval_id=approval.pk, review_hash=preview["review_hash"])
        op = revisions.activate_revision(**args)
        self.assertEqual(revisions.activate_revision(**args).pk, op.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            revisions.activate_revision(**dict(args, payment_reference="Changed"))
        with self.assertRaises(ValueError):
            revisions.activate_revision(**dict(args, request_key=uuid.uuid4()))
        with self.later(0, 1):
            self.assertEqual(revisions.activate_revision(**args).pk, op.pk)

    def test_finalized_month_and_existing_receipt_stay_unchanged(self):
        self.open()
        with self.later(1):
            receipt = self.pay("100000")
            with workspace_context(self.workspace.pk):
                before = list(self.account.interest_periods.values())
                allocations = list(receipt.interest_allocations.values())
            self.revise(rate="2")
        with self.later(2):
            self.assertEqual(self.balance()["due_interest"], Decimal("200000"))
            self.pay("200000")
            with workspace_context(self.workspace.pk):
                self.assertEqual(list(self.account.interest_periods.filter(index=0).values()), before)
                self.assertEqual(list(receipt.interest_allocations.values()), allocations)

    def test_half_paise_segments_are_summed_exactly_before_rounding(self):
        self.proposal("1", "1")
        self.deposit(); self.approve(); self.payout("0.01")
        with self.later(1, 15):
            self.revise("2", "0.5")
        with self.later(2):
            self.pay("0.02")
            with workspace_context(self.workspace.pk):
                second = self.account.interest_periods.get(index=1)
                self.assertEqual(second.charge, Decimal("0.01"))
                self.assertEqual(list(second.segments.values_list("exact_numerator", "exact_denominator")),
                    [(Decimal(1), Decimal(200)), (Decimal(1), Decimal(200))])

    def test_approver_cannot_collect_principal_cashier_can_execute_approved_reduction(self):
        self.open()
        self.proposal("60000")
        staff = get_user_model().objects.create_user(username="revision-staff")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.workspace, role=role)
        ct = ContentType.objects.get_for_model(Company)
        def grants(*codes):
            workspace_role_permissions(role, self.workspace).set([
                Permission.objects.get_or_create(content_type=ct, codename=c, defaults={"name": c})[0] for c in codes])
        grants("data_view", "loan_approve")
        approval = self.approve_change("40000", actor=staff)
        with self.assertRaises(PermissionDenied):
            self.activate(approval, actor=staff)
        grants("data_view", "loan_repay")
        with self.assertRaises(PermissionDenied):
            self.approve_change("40000", actor=staff)
        self.activate(approval, actor=staff)
        self.assertEqual(self.position().principal, Decimal("60000"))
        self.proposal("100000")
        approval = self.approve_change()
        with self.assertRaises(PermissionDenied):
            self.activate(approval, actor=staff)

    def test_unavailable_licence_blocks_increase_but_allows_rate_change_and_reduction(self):
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.create(workspace=self.workspace, name="Test associated", license_number="ASSOC",
                issued_on=self.started_on-timedelta(days=1), expires_on=self.started_on)
        self.series = drafts.create_series(workspace=self.workspace, actor=self.actor, code="KA", name="Associated", prefix="KA", license_id=license.pk)
        self.account = drafts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.open()
        with self.later(0, 1):
            self.proposal("15000000")
            with self.assertRaisesMessage(ValueError, "licence"):
                self.approve_change()
            self.revise(rate="0.5")
            self.revise("60000", repayment="40000")
            self.assertEqual(self.position().principal, Decimal("60000"))


@override_settings(STORAGES=collection.opening_tests.STORAGES)
class KhataRevisionRaceTests(RevisionFixture, TransactionTestCase):
    def test_two_activators_cannot_collect_principal_twice(self):
        self.open(); self.proposal("60000")
        approval = self.approve_change("40000")
        preview = revisions.preview_activation(**self.args(), approval_id=approval.pk)
        ready = Barrier(2)
        def activate(_):
            try:
                ready.wait(timeout=15)
                return revisions.activate_revision(**self.command(), approval_id=approval.pk,
                    review_hash=preview["review_hash"], payment_reference="Cash").pk
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(activate, range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(self.position().principal, Decimal("60000"))


@override_settings(STORAGES=collection.opening_tests.STORAGES)
class KhataRevisionRLSTests(RevisionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.runtime_role = "khata_revision_rls_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(self.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def test_raw_reduction_cannot_omit_repayment_or_overdraw_restored_capacity(self):
        self.open(); self.proposal("60000")
        approval = self.approve_change("40000")
        review = revisions.preview_activation(**self.args(), approval_id=approval.pk)
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaisesMessage(DatabaseError, "unchanged approval"), transaction.atomic():
                KhataOperation.objects.create(workspace=self.workspace, account=self.account, sequence=approval.sequence+1,
                    kind="REVISE", amount=0, agreement=approval.agreement, approval=approval,
                    business_date=timezone.localdate(), request_key=uuid.uuid4(), request_sha256="a"*64,
                    created_by=self.actor, evidence=dict(review["snapshot"], payment_reference="Cash"))
        activation = self.activate(approval)
        with self.runtime(), workspace_context(self.workspace.pk):
            with self.assertRaisesMessage(DatabaseError, "unused entitlement"), transaction.atomic():
                KhataOperation.objects.create(workspace=self.workspace, account=self.account, sequence=activation.sequence+1,
                    kind="WITHDRAW", amount=1, agreement=activation.agreement, approval=approval,
                    business_date=timezone.localdate(), request_key=uuid.uuid4(), request_sha256="b"*64,
                    created_by=self.actor, evidence={"schema": "khata-opening/1"})
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataOperation.objects.filter(pk=activation.pk).update(amount=0)

    def test_raw_proposal_cannot_change_fixed_contract_or_cross_workspace(self):
        self.open()
        other_ws, other_actor, other_borrower = foundation.fixture(uuid.uuid4().hex[:8])
        other_series = drafts.create_series(workspace=other_ws, actor=other_actor, code="KH", name="Other")
        other_account = drafts.create_draft(**foundation.draft_args(other_ws, other_actor, other_borrower, other_series))
        with self.runtime(), workspace_context(self.workspace.pk):
            original = effective_agreement(self.account)
            for changes in ({"frequency": "ANNUAL"}, {"ltv": Decimal("0.9")}, {"account_id": other_account.pk}):
                forged = copy.copy(original)
                forged.pk = None
                forged._state = copy.copy(original._state)
                forged._state.adding = True
                forged.number += 1
                forged.request_key = uuid.uuid4()
                for key, value in changes.items():
                    setattr(forged, key, value)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataAgreementRevision.objects.bulk_create([forged])

    def test_raw_receipt_segments_cannot_reference_unactivated_proposals(self):
        self.open()
        with self.later(1, 15):
            self.revise(rate="2")
            unactivated = self.proposal(rate="3")
        with self.later(2), self.runtime(), workspace_context(self.workspace.pk):
            rows = servicing._pending_periods(self.account, timezone.localdate())
            row = rows[1]
            row["segments"][-1]["agreement_id"] = unactivated.pk
            with self.assertRaisesMessage(DatabaseError, "segment/source"), transaction.atomic():
                servicing._finalize(self.account, self.actor, timezone.localdate(), uuid.uuid4(), "c"*64, rows)
            self.assertFalse(KhataInterestSegment.objects.exists())

    def test_raw_activation_cannot_reinterpret_a_finalized_month(self):
        self.open()
        self.proposal(rate="2")
        approval = self.approve_change()
        review = revisions.preview_activation(**self.args(), approval_id=approval.pk)
        with self.later(1):
            self.pay("100000")
            with self.runtime(), workspace_context(self.workspace.pk):
                with self.assertRaisesMessage(DatabaseError, "cannot rewrite finalized interest"), transaction.atomic():
                    KhataOperation.objects.create(workspace=self.workspace, account=self.account,
                        sequence=self.account.operations.order_by("-sequence").first().sequence+1,
                        kind="REVISE", amount=0, agreement=approval.agreement, approval=approval,
                        business_date=self.started_on, request_key=uuid.uuid4(), request_sha256="d"*64,
                        created_by=self.actor, evidence=review["snapshot"])
