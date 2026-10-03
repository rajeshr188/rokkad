from contextlib import contextmanager
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4
from django.test import override_settings
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import pawn_auctions as auctions
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from . import test_recorded_origination as origins, test_recorded_history as histories
from .factories import prepare_test_auction_service


@contextmanager
def on(day):
    with patch("django.utils.timezone.now", return_value=timezone.make_aware(datetime.combine(day, time(10)))):
        yield


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RecordedAuctionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "recorded-auction"

    def setUp(self):
        self.prepare_history()
        self.data["events"] = [self.row(amount="2000")]
        self.loan, _, _ = self.admit()
        self.notice_day = self.day+relativedelta(months=4)
        self.sale_day = self.notice_day+timedelta(days=60)

    def review(self, day, complete=True):
        facts = dict(through_date=day, confirmed_complete=complete, source_reference="Checked complete paper book",
            request_key=uuid4().hex)
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **facts)
        return confirm_transaction_review(self.loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)

    def prepare(self):
        with on(self.notice_day):
            self.review(self.notice_day)
            auction = auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day,
                request_key="sale", actor=self.actor)
        prepare_test_auction_service(auction, self.actor, self.notice_day)
        return auction

    def complete(self, auction, *, amount=None):
        with on(self.sale_day):
            self.review(self.sale_day)
            expected = collection_balance(self.loan, self.sale_day)
            auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
            result = auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=amount or expected.total_due,
                buyer_name="Fictional buyer", buyer_reference="Sale receipt", actor=self.actor)
            return result, expected

    def test_anniversary_debt_recovery_exact_retry_custody_and_coupled_reversal(self):
        auction = self.prepare()
        result, expected = self.complete(auction)
        self.assertEqual(result.auction.principal_amount, 8200)
        self.assertEqual(result.auction.interest_amount, expected.interest_outstanding)
        self.assertIsNone(result.auction.catch_up_accrual_id)
        self.assertEqual(self.loan.collateral_items.get().custody_state, "AUCTION_DISPOSED")
        self.loan.refresh_from_db()
        self.assertEqual(collection_balance(self.loan, self.sale_day+relativedelta(months=2)).total_due, 0)
        self.assertTrue(transaction_completeness(self.loan, self.sale_day).complete)
        proof = result.loan_event.payload["auction"]["recorded_collection"]
        recognition = m.PawnLoanEvent.objects.get(pk=proof["recognition_event_id"])
        self.assertEqual(recognition.payload["recorded_collection"]["request_key"], f"auction:{auction.pk}")
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event, PawnReversalError
        with on(self.sale_day):
            again = auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=expected.total_due,
                buyer_name="Fictional buyer", buyer_reference="Sale receipt", actor=self.actor)
            self.assertTrue(again.already_completed)
            with self.assertRaises(PawnReversalError):
                reverse_pawn_loan_event(result.loan_event.pk, reason="Wrong sale", actor=self.actor)
            reversal = auctions.reverse_pawn_loan_auction(auction.pk, reason="Sale cancelled", actor=self.actor)
            self.assertEqual(reversal.catch_up_reversal_event.reversal_of_id, recognition.pk)
            self.assertTrue(auctions.reverse_pawn_loan_auction(auction.pk, reason="Sale cancelled", actor=self.actor).already_reversed)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(self.loan.collateral_items.get().custody_state, "IN_VAULT")
        self.assertEqual(collection_balance(self.loan, self.sale_day).total_due, expected.total_due)
        self.assertEqual(transaction_completeness(self.loan, self.sale_day).status, "CHANGED")
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        with on(self.sale_day):
            record_pawn_loan_repayment(self.loan.pk, amount=expected.interest_outstanding,
                request_key="interest-after-reversal", actor=self.actor)
        self.assertEqual(collection_balance(self.loan, self.sale_day).interest_outstanding, 0)
        self.assertEqual(collection_balance(self.loan, self.sale_day+relativedelta(months=1)).interest_outstanding, 164)

    def test_missing_changed_behind_and_incomplete_coverage_block_before_posting(self):
        count = self.loan.loan_events.count()
        with on(self.notice_day), self.assertRaisesMessage(auctions.PawnAuctionError, "Confirm complete"):
            auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day, request_key="sale", actor=self.actor)
        with on(self.notice_day):
            self.review(self.notice_day, complete=False)
            with self.assertRaisesMessage(auctions.PawnAuctionError, "Confirm complete"):
                auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day, request_key="sale", actor=self.actor)
        self.assertEqual(count, self.loan.loan_events.count())
        self.assertFalse(self.loan.auctions.exists())
        auction = self.prepare()
        with on(self.sale_day), self.assertRaisesMessage(auctions.PawnAuctionError, "Confirm complete"):
            auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
        with on(self.sale_day):
            self.review(self.sale_day)
            auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
            from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
            record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="late-known-receipt", actor=self.actor)
            before = self.loan.loan_events.count()
            with self.assertRaisesMessage(auctions.PawnAuctionError, "Confirm complete"):
                auctions.complete_pawn_loan_auction(auction.pk, recovery_amount="9999", buyer_name="Buyer", actor=self.actor)
            self.assertEqual(before, self.loan.loan_events.count())

    def test_recovery_mismatch_rolls_back_interest_and_custody_and_statutory_gate_stays(self):
        auction = self.prepare()
        count = self.loan.loan_events.count()
        with self.assertRaisesMessage(auctions.PawnAuctionError, "exactly clear"):
            self.complete(auction, amount=Decimal("1"))
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertEqual(self.loan.collateral_items.get().custody_state, "IN_VAULT")
        self.assertFalse(auction.items.exists())
        with on(self.sale_day):
            self.review(self.sale_day)
            from apps.tenant_apps.loans.services.statutory_notices import record_handling
            record_handling(auction.pk, kind="WITHDRAWN", actor=self.actor,
                data=dict(occurred_on=self.sale_day, request_key="withdraw", notes="Wrong catalogue"))
            with self.assertRaises(auctions.PawnAuctionError):
                auctions.complete_pawn_loan_auction(auction.pk, recovery_amount="10000", buyer_name="Buyer", actor=self.actor)

    def test_authorization_and_existing_notice_rules_are_not_bypassed(self):
        with self.assertRaisesMessage(auctions.PawnAuctionError, "administrator"):
            auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day, request_key="bad", actor=None)
        with on(self.notice_day):
            self.review(self.notice_day)
            auction = auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day, request_key="sale", actor=self.actor)
        with on(self.sale_day):
            self.review(self.sale_day)
            with self.assertRaisesMessage(auctions.PawnAuctionError, "statutory"):
                auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)

    def test_completed_auction_and_statutory_media_survive_exact_recovery(self):
        auction = self.prepare()
        result, _ = self.complete(auction)
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        from . import test_pawn_recovery
        from hashlib import sha256
        with on(self.sale_day):
            content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
            original, files = recovery._read(content, sha256(content).hexdigest())
            self.assertGreater(len(files), 0)
            test_pawn_recovery.PawnRecoveryTests.empty(self)
            recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
                expected_sha256=sha256(content).hexdigest(), commit=True)
            new = recovery.export_archive(workspace=self.tenant, actor=self.actor)
            restored, _ = recovery._read(new, sha256(new).hexdigest())
            self.assertEqual(original["tables"], restored["tables"])
            self.assertEqual(original["reconciliation"], restored["reconciliation"])
        current = m.PawnLoanAuction.objects.get(pk=auction.pk)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.auction_recovery_memo(current)
        self.assertIn("Agreed paper", dict(payload.details)["Collection basis"])
