import uuid
import copy
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from PIL import Image

from apps.orgs.models import Company, Role, Membership
from apps.orgs.services.storage_references import collect_references, validate_coverage
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import workspace_role_permissions
from apps.subscriptions.models import Subscription
from apps.tenant_apps.loans.models import (
    KhataAccount, KhataOperation, KhataCollateralItem, KhataCollateralValuation,
    KhataCollateralPhoto, KhataPolicyRevision, PawnLoan,
)
from apps.tenant_apps.loans.services import khata_accounts as drafts, khata_opening as opening
from apps.tenant_apps.loans.services.origination_settings import set_collateral_photo_requirement
from apps.tenant_apps.loans.selectors.khata import account_balances, held_items
from apps.tenant_apps.rates.models import RateSource
from apps.tenant_apps.rates.services import record_quote
from . import test_khata_foundation as foundation
from .test_khata_foundation import fixture, draft_args


STORAGES = {"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


class OpeningFixture:
    def setUp(self):
        super().setUp()
        self.workspace, self.actor, self.borrower = fixture(uuid.uuid4().hex[:8])
        self.series = drafts.create_series(workspace=self.workspace, actor=self.actor, code="KH", name="Opening")
        self.account = drafts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            self.source = RateSource.objects.create(name="Fictional current price", location="Test")
        self.quote()

    def args(self):
        return dict(workspace=self.workspace, actor=self.actor, account_id=self.account.pk)

    def command(self):
        return dict(self.args(), request_key=uuid.uuid4(), business_date=timezone.localdate())

    def quote(self, value="10000"):
        with workspace_context(self.workspace.pk):
            return record_quote(workspace=self.workspace, actor=self.actor, values=dict(rate_source=self.source,
                metal="Gold", purity="24k", currency="INR", buying_rate=Decimal(value), selling_rate=Decimal(value), effective_at=timezone.now()))

    def deposit(self, **changes):
        args = dict(self.command(), description="Gold ring", metal="GOLD", quantity=1,
            gross_weight="100", net_weight="100", purity="100", storage_reference="Vault A / bag 1", received_from="Borrower")
        args.update(changes)
        return opening.record_deposit(**args)

    def approve(self):
        review = opening.preview_opening(**self.args())
        return opening.approve_opening(**self.command(), review_hash=review["review_hash"])

    def payout(self, value="100000"):
        review = opening.preview_withdrawal(**self.args(), value=value)
        return opening.record_withdrawal(**self.command(), value=value, review_hash=review["review_hash"], payment_reference="Cash handed over")

    def balance(self):
        return account_balances(**self.args())

    def photo(self, item):
        content = BytesIO()
        Image.new("RGB", (3, 3), "white").save(content, format="PNG")
        return opening.attach_photo(**self.command(), item_id=item.pk,
            upload=SimpleUploadedFile("collateral.png", content.getvalue(), content_type="image/png"))


@override_settings(STORAGES=STORAGES)
class KhataOpeningTests(OpeningFixture, TestCase):
    def test_deposit_approval_and_actual_first_payout_are_distinct(self):
        item = self.deposit()
        self.assertFalse(self.balance()["opened"])
        approval = self.approve()
        self.assertFalse(self.balance()["opened"])
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "APPROVED")
            self.assertIsNone(self.account.opened_on)
            self.assertEqual(approval.valuations.get().value, Decimal("1000000"))
            self.assertTrue(held_items(self.account).filter(pk=item.pk).exists())
        payout = self.payout("600000")
        self.assertEqual(payout.approval_id, approval.pk)
        self.assertEqual(self.balance()["principal"], Decimal("600000"))
        self.assertEqual(self.balance()["unused"], Decimal("9400000"))
        self.assertEqual(self.balance()["calculated_interest"], Decimal("100000"))
        self.assertEqual(self.balance()["due_interest"], 0)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.opened_on, timezone.localdate())
            self.assertEqual(self.account.state, "ACTIVE")
            self.assertFalse(PawnLoan.objects.exists())

    def test_staged_draws_enforce_ltv_and_topups_do_not_create_money(self):
        self.deposit(); self.approve(); self.payout("600000")
        with self.assertRaisesMessage(ValueError, "backing"):
            self.payout("150000.01")
        self.deposit()
        self.assertEqual(self.balance()["principal"], Decimal("600000"))
        self.payout("900000")
        self.assertEqual(self.balance()["principal"], Decimal("1500000"))
        self.assertEqual(self.balance()["unused"], Decimal("8500000"))

    def test_stale_approval_price_and_draw_reviews_require_refresh(self):
        self.deposit()
        review = opening.preview_opening(**self.args())
        self.quote("9900")
        with self.assertRaisesMessage(ValueError, "changed after review"):
            opening.approve_opening(**self.command(), review_hash=review["review_hash"])
        self.approve()
        self.quote("9800")
        with self.assertRaisesMessage(ValueError, "approval is stale"):
            opening.preview_withdrawal(**self.args(), value="1")
        self.approve()
        review = opening.preview_withdrawal(**self.args(), value="1")
        self.photo(self.deposit())
        with self.assertRaises(ValueError):
            opening.record_withdrawal(**self.command(), value="1", review_hash=review["review_hash"], payment_reference="Cash")
        self.assertEqual(self.balance()["principal"], 0)

    def test_photo_policy_drafts_can_save_and_approval_requires_actual_file(self):
        with workspace_context(self.workspace.pk):
            set_collateral_photo_requirement(workspace=self.workspace, actor=self.actor, required=True)
        item = self.deposit()
        with self.assertRaisesMessage(ValueError, "requires a photograph"):
            self.approve()
        photo = self.photo(item)
        self.approve()
        self.payout()
        refs = collect_references([self.workspace.pk])
        self.assertIn((self.workspace.pk, "collateral_photos"), refs[photo.file.name])
        self.assertIn("loans.khatacollateralphoto.file", validate_coverage())
        photo.file.storage.delete(photo.file.name)
        with self.assertRaisesMessage(ValueError, "unavailable"):
            self.payout()

    def test_current_photo_policy_can_invalidate_first_payout(self):
        self.deposit(); self.approve()
        with workspace_context(self.workspace.pk):
            set_collateral_photo_requirement(workspace=self.workspace, actor=self.actor, required=True)
        with self.assertRaises(ValueError):
            self.payout()

    def test_return_before_opening_and_cancel_preserve_custody_history(self):
        item = self.deposit(); self.approve()
        with self.assertRaisesMessage(ValueError, "Return unopened collateral"):
            drafts.cancel_draft(**self.args(), reason="Cancelled")
        op = opening.return_unopened_item(**self.command(), item_id=item.pk, recipient="Borrower", reason="Cancelled agreement")
        self.assertEqual(op.kind, "RETURN")
        drafts.cancel_draft(**self.args(), reason="Cancelled")
        with workspace_context(self.workspace.pk):
            self.assertFalse(held_items(self.account).exists())
            self.assertEqual(self.account.collateral.count(), 1)
        with self.assertRaises(ValueError):
            self.deposit()

    def test_active_cancellation_return_and_term_edit_are_rejected(self):
        item = self.deposit(); self.approve(); self.payout()
        with self.assertRaises(ValueError):
            drafts.cancel_draft(**self.args(), reason="No")
        with self.assertRaises(ValueError):
            opening.return_unopened_item(**self.command(), item_id=item.pk, recipient="Borrower", reason="No")
        with self.assertRaises(ValueError):
            self.approve()

    def test_idempotent_withdrawal_and_failed_valuation_rollback(self):
        self.deposit(); self.approve()
        review = opening.preview_withdrawal(**self.args(), value="100000")
        args = dict(self.command(), value="100000", review_hash=review["review_hash"], payment_reference="Cash")
        with patch.object(opening, "_save_valuations", side_effect=ValueError("Fixture failure")):
            with self.assertRaises(ValueError):
                opening.record_withdrawal(**args)
        self.assertFalse(self.balance()["opened"])
        op = opening.record_withdrawal(**args)
        self.assertEqual(opening.record_withdrawal(**args).pk, op.pk)
        self.assertEqual(opening.record_withdrawal(**dict(args, value=Decimal("100000.00"))).pk, op.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            opening.record_withdrawal(**dict(args, value="200000"))
        self.assertEqual(self.balance()["principal"], Decimal("100000"))

    def test_overdue_warn_block_and_deposits_remain_allowed(self):
        self.deposit(); self.approve(); self.payout()
        later = timezone.now() + timedelta(days=40)
        Subscription.objects.filter(company=self.workspace).update(trial_end_date=later + timedelta(days=20))
        with patch("django.utils.timezone.now", return_value=later):
            self.quote()
            preview = opening.preview_withdrawal(**self.args(), value="1")
            self.assertEqual(preview["snapshot"]["warnings"], ["Interest is overdue."])
            opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="WARN", overdue="BLOCK", reason="Owner policy", request_key=uuid.uuid4())
            with self.assertRaisesMessage(ValueError, "overdue"):
                self.payout("1")
            self.deposit()
            self.assertEqual(self.balance()["principal"], Decimal("100000"))

    def test_approver_cannot_disburse_or_change_owner_policies(self):
        self.deposit()
        staff = get_user_model().objects.create_user(username="khata-approver")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.workspace, role=role)
        ct = ContentType.objects.get_for_model(Company)
        perms = [Permission.objects.get_or_create(content_type=ct, codename=c, defaults={"name": c})[0] for c in ("data_view", "loan_approve")]
        workspace_role_permissions(role, self.workspace).set(perms)
        review = opening.preview_opening(**dict(self.args(), actor=staff))
        opening.approve_opening(**dict(self.command(), actor=staff), review_hash=review["review_hash"])
        review = opening.preview_withdrawal(**dict(self.args(), actor=staff), value="1")
        with self.assertRaises(PermissionDenied):
            opening.record_withdrawal(**dict(self.command(), actor=staff), value="1", review_hash=review["review_hash"], payment_reference="Cash")
        with self.assertRaises(PermissionDenied):
            opening.set_policies(workspace=self.workspace, actor=staff, exchange="BLOCK", overdue="BLOCK", reason="No", request_key=uuid.uuid4())

    def test_missing_stale_and_future_prices_fail_closed(self):
        self.deposit()
        tomorrow = timezone.now() + timedelta(days=1)
        with patch("django.utils.timezone.now", return_value=tomorrow):
            # Save today's terms; yesterday's quote is still not acceptable.
            args = draft_args(self.workspace, self.actor, self.borrower, self.series)
            args.pop("series_id"); args.pop("borrower_id")
            drafts.propose_revision(**args, account_id=self.account.pk, expected_revision=1, reason="Today")
            with self.assertRaisesMessage(ValueError, "same-day"):
                self.approve()

    def test_revision_after_approval_requires_new_approval_and_today(self):
        self.deposit(); self.approve()
        args = draft_args(self.workspace, self.actor, self.borrower, self.series)
        args.pop("series_id"); args.pop("borrower_id")
        args["monthly_rate"] = "2"
        drafts.propose_revision(**args, account_id=self.account.pk, expected_revision=1, reason="Borrower accepted revised terms")
        with self.assertRaisesMessage(ValueError, "Approve the current agreement"):
            self.payout()
        self.approve(); self.payout()
        self.assertEqual(self.balance()["calculated_interest"], Decimal("200000"))
        with self.assertRaisesMessage(ValueError, "today"):
            self.deposit(business_date=timezone.localdate() - timedelta(days=1))

    def test_later_deposit_cannot_be_appended_to_an_old_approval_valuation(self):
        self.deposit(); approval = self.approve(); self.payout()
        later_item = self.deposit()
        with workspace_context(self.workspace.pk):
            original = approval.valuations.get()
            with self.assertRaisesMessage(DatabaseError, "frozen operation snapshot"), transaction.atomic():
                KhataCollateralValuation.objects.create(workspace=self.workspace, operation=approval,
                    item=later_item, rate=original.rate, value=original.value, rate_evidence=original.rate_evidence)
            self.assertEqual(approval.valuations.count(), 1)


@override_settings(STORAGES=STORAGES)
class KhataWithdrawalConcurrencyTests(OpeningFixture, TransactionTestCase):
    def test_two_cashiers_cannot_spend_the_same_reviewed_availability(self):
        self.deposit(); self.approve()
        review = opening.preview_withdrawal(**self.args(), value="600000")
        ready = Barrier(2)
        def pay(_):
            try:
                ready.wait(timeout=15)
                return opening.record_withdrawal(**self.command(), value="600000", review_hash=review["review_hash"], payment_reference="Cash").pk
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(pay, range(2)))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(self.balance()["principal"], Decimal("600000"))


@override_settings(STORAGES=STORAGES)
class KhataOpeningRLSTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        foundation.KhataRLSBoundaryTests.setUpTestData.__func__(cls)

    runtime = foundation.KhataRLSBoundaryTests.runtime

    def populate(self, workspace, actor, account):
        args = dict(workspace=workspace, actor=actor, account_id=account.pk)
        command = lambda: dict(args, request_key=uuid.uuid4(), business_date=timezone.localdate())
        item = opening.record_deposit(**command(), description="Fictional gold", metal="GOLD", quantity=1,
            gross_weight="100", net_weight="100", purity="100", storage_reference="Vault", received_from="Borrower")
        with workspace_context(workspace.pk):
            source = RateSource.objects.create(name="Test rate", location="Test")
            record_quote(workspace=workspace, actor=actor, values=dict(rate_source=source, metal="Gold", currency="INR", purity="24k",
                buying_rate=Decimal("10000"), selling_rate=Decimal("10000"), effective_at=timezone.now()))
        content = BytesIO()
        Image.new("RGB", (2, 2), "white").save(content, format="PNG")
        photo = opening.attach_photo(**command(), item_id=item.pk,
            upload=SimpleUploadedFile("image.png", content.getvalue(), content_type="image/png"))
        policy = opening.set_policies(workspace=workspace, actor=actor, exchange="WARN", overdue="WARN", reason="Owner review", request_key=uuid.uuid4())
        review = opening.preview_opening(**args)
        approval = opening.approve_opening(**command(), review_hash=review["review_hash"])
        with workspace_context(workspace.pk):
            valuation = approval.valuations.get()
        return (approval, policy, item, valuation, photo)

    def test_populated_evidence_is_isolated_immutable_and_parent_guarded(self):
        from django.db import connection
        own = self.populate(self.workspace, self.actor, self.account)
        other = self.populate(self.other_workspace, self.other_actor, self.other_account)
        with self.runtime():
            for row in own:
                self.assertEqual(type(row).objects.count(), 0)
            with workspace_context(self.workspace.pk):
                for row, foreign in zip(own, other):
                    model = type(row)
                    self.assertTrue(model.objects.filter(pk=row.pk).exists())
                    self.assertFalse(model.objects.filter(pk=foreign.pk).exists())
                    self.assertEqual(model.objects.filter(pk=foreign.pk).update(workspace_id=self.workspace.pk), 0)
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.filter(pk=row.pk).update(workspace_id=self.other_workspace.pk)
                    with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                        cursor.execute(f'DELETE FROM {connection.ops.quote_name(model._meta.db_table)} WHERE id=%s', [row.pk])
                    forged = copy.copy(row)
                    forged.pk = None
                    forged._state = copy.copy(row._state)
                    forged._state.adding = True
                    if isinstance(forged, KhataOperation):
                        forged.account_id = self.other_account.pk
                        forged.request_key = uuid.uuid4()
                    elif isinstance(forged, KhataPolicyRevision):
                        forged.workspace_id = self.other_workspace.pk
                        forged.request_key = uuid.uuid4()
                    elif isinstance(forged, KhataCollateralItem):
                        forged.account_id = self.other_account.pk
                        forged.public_id = uuid.uuid4()
                    else:
                        forged.item_id = other[2].pk
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.bulk_create([forged])
                with self.assertRaisesMessage(DatabaseError, "collateral LTV"), transaction.atomic():
                    approval = own[0]
                    op = KhataOperation.objects.create(workspace=self.workspace, account=self.account,
                        sequence=approval.sequence+1, kind="WITHDRAW", amount="750000.01",
                        agreement_id=approval.agreement_id, approval=approval, business_date=timezone.localdate(),
                        request_key=uuid.uuid4(), request_sha256="a"*64, created_by=self.actor, evidence=approval.evidence)
                    opening._save_valuations(op, approval.evidence)
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                self.assertFalse(KhataOperation.objects.filter(account=self.account, kind="WITHDRAW").exists())

    def test_all_new_tables_fail_closed_and_reject_foreign_parents(self):
        models = (KhataOperation, KhataPolicyRevision, KhataCollateralItem, KhataCollateralValuation, KhataCollateralPhoto)
        with self.runtime():
            for model in models:
                self.assertEqual(model.objects.count(), 0)
            with workspace_context(self.workspace.pk):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataOperation.objects.create(workspace=self.workspace, account=self.other_account, sequence=1, kind="DEPOSIT",
                        business_date=timezone.localdate(), request_key=uuid.uuid4(), request_sha256="a"*64,
                        evidence={"schema": "test"}, created_by=self.actor)
                with self.assertRaises(DatabaseError), transaction.atomic():
                    # Missing receipt item cannot commit, even through raw DML.
                    KhataOperation.objects.create(workspace=self.workspace, account=self.account, sequence=1, kind="DEPOSIT",
                        business_date=timezone.localdate(), request_key=uuid.uuid4(), request_sha256="a"*64,
                        evidence={"schema": "test"}, created_by=self.actor)
                    from django.db import connection
                    with connection.cursor() as cursor:
                        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
