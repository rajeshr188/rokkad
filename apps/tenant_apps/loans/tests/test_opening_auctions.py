"""Opening recovery uses checkpoint debt, statutory evidence and coupled reversal."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from django.utils import timezone
from decimal import Decimal
from uuid import uuid4
from django.test import override_settings
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import pawn_auctions as auctions
from apps.tenant_apps.loans.services.opening_servicing import opening_payment_balance
from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.obligation_state import get_active_repayment_schedule_as_of
from .test_opening_release import OpeningReleaseFixture
from .factories import prepare_test_auction_service


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OpeningAuctionTests(OpeningReleaseFixture):
    def setUp(self):
        super().setUp()
        self.day = date(2021, 5, 1)
        self.enterContext(patch("django.utils.timezone.now", side_effect=lambda: timezone.make_aware(datetime.combine(self.day, time(10)))))
        self.enterContext(patch("django.utils.timezone.localdate", side_effect=lambda value=None: timezone.localtime(value or timezone.now()).date()))
        self.sale_day = self.day + timedelta(days=60)

    def review(self):
        facts = dict(through_date=self.day, confirmed_complete=True, source_reference="Checked opening book",
            request_key=uuid4().hex)
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **facts)
        return confirm_transaction_review(self.loan.pk, actor=self.actor, review_token=token, acknowledged=True, **facts)

    def prepare(self):
        self.review()
        auction = auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day,
            request_key="opening-sale", actor=self.actor)
        prepare_test_auction_service(auction, self.actor, self.day)
        self.day = self.sale_day
        self.review()
        auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
        return auction

    def test_settlement_and_paired_reverse_preserve_checkpoint_and_resume_exposure(self):
        frozen = self.origin.payload_fingerprint
        auction = self.prepare()
        quote, _ = opening_payment_balance(self.loan, as_of_date=self.day)
        self.assertGreater(quote.interest_outstanding, 0)
        result = auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=quote.total_due,
            buyer_name="Actual buyer", actor=self.actor)
        self.assertEqual(result.loan_event.payload["opening_collection"]["operation"], "AUCTION_RECOVERY")
        auction.refresh_from_db()
        self.assertEqual(auction.interest_amount, quote.interest_outstanding)
        self.assertIsNotNone(auction.catch_up_accrual_id)
        self.loan.refresh_from_db(); self.item.refresh_from_db()
        self.assertEqual((self.loan.state, self.item.custody_state), ("CLOSED", "AUCTION_DISPOSED"))
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).total_due, 0)
        self.assertEqual(preview_opening_collection(self.loan, events=self.loan.loan_events.all(), as_of_date=self.day).additional_interest, 0)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 0)
        with self.assertRaises(ValueError):
            reverse_pawn_loan_event(result.loan_event.pk, reason="Wrong standalone reversal", actor=self.actor)
        reverse = auctions.reverse_pawn_loan_auction(auction.pk, reason="Sale cancelled", actor=self.actor)
        self.assertIsNotNone(reverse.catch_up_reversal_event)
        self.loan.refresh_from_db(); self.item.refresh_from_db(); self.origin.refresh_from_db()
        self.assertEqual((self.loan.state, self.item.custody_state), ("ACTIVE", "IN_VAULT"))
        self.assertEqual(self.origin.payload_fingerprint, frozen)
        self.assertEqual(get_active_repayment_schedule_as_of(self.loan, self.day).pk, self.schedule.pk)
        self.assertEqual(opening_payment_balance(self.loan, as_of_date=self.day)[0].total_due, quote.total_due)
        self.assertTrue(auctions.reverse_pawn_loan_auction(auction.pk, reason="Sale cancelled", actor=self.actor).already_reversed)

    def test_review_and_statutory_readiness_are_required_and_mismatch_is_atomic(self):
        with self.assertRaisesMessage(ValueError, "Confirm complete"):
            auctions.initiate_pawn_loan_auction(self.loan.pk, scheduled_date=self.sale_day,
                request_key="unreviewed", actor=self.actor)
        auction = self.prepare()
        count = self.loan.loan_events.count()
        with self.assertRaisesMessage(ValueError, "exactly clear"):
            auctions.complete_pawn_loan_auction(auction.pk, recovery_amount="1", buyer_name="Buyer", actor=self.actor)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertFalse(auction.items.exists())
        from apps.tenant_apps.loans.services.statutory_notices import record_handling
        record_handling(auction.pk, kind="WITHDRAWN", actor=self.actor,
            data=dict(occurred_on=self.day, request_key="withdrawn", notes="Wrong catalogue"))
        with self.assertRaises(ValueError):
            auctions.complete_pawn_loan_auction(auction.pk, recovery_amount="1000", buyer_name="Buyer", actor=self.actor)

    def test_current_receipt_reduces_debt_without_changing_original_maturity(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        maturity = get_pawn_loan_balance(self.loan, as_of_date=self.day).due_date
        record_pawn_loan_repayment(self.loan.pk, amount="250", request_key="partial", actor=self.actor)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).due_date, maturity)
        auction = self.prepare()
        quote, _ = opening_payment_balance(self.loan, as_of_date=self.day)
        result = auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=quote.total_due,
            buyer_name="Buyer", actor=self.actor)
        self.assertEqual(Decimal(result.loan_event.payload["values"]["principal"]), quote.principal_outstanding)

    def test_auction_source_and_statutory_media_survive_exact_workspace_recovery(self):
        from hashlib import sha256
        from .test_pawn_recovery import PawnRecoveryTests
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        auction = self.prepare()
        quote, _ = opening_payment_balance(self.loan, as_of_date=self.day)
        auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=quote.total_due, buyer_name="Buyer", actor=self.actor)
        content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        original, files = recovery._read(content, sha256(content).hexdigest())
        self.assertTrue(files)
        PawnRecoveryTests.empty(self)
        recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
            expected_sha256=sha256(content).hexdigest(), commit=True)
        new = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        restored, _ = recovery._read(new, sha256(new).hexdigest())
        self.assertEqual(original["tables"], restored["tables"])
        self.assertEqual(original["reconciliation"], restored["reconciliation"])

    def test_foreign_workspace_cannot_start_or_settle_auction(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        auction = self.prepare()
        count = self.loan.loan_events.count()
        with without_workspace_context(), workspace_context(other.pk):
            with self.assertRaises(ValueError):
                auctions.complete_pawn_loan_auction(auction.pk, recovery_amount="1000", buyer_name="Buyer", actor=self.actor)
        self.assertEqual(count, self.loan.loan_events.count())


from . import test_opening_checkpoint as checkpoints
from .test_recorded_auctions import on


class CheckpointAuctionTests(checkpoints.OpeningCheckpointTests):
    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_reduced_checkpoint_current_auction_and_reversal_keep_explicit_future_capture(self):
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
        notice_day, sale_day = date(2021, 5, 1), date(2021, 6, 30)
        with self.scoped():
            with on(notice_day):
                origin = self.write()
                loan = origin.loan
                frozen = loan.loan_events.get(event_kind="MIGRATION_OPENING").payload_fingerprint
                def check(day, mode):
                    facts = dict(through_date=day, confirmed_complete=True, future_capture=mode,
                        source_reference="Synthetic complete post-cutover book", request_key=uuid4().hex)
                    _, token = preview_transaction_review(loan.pk, actor=self.actor, **facts)
                    confirm_transaction_review(loan.pk, actor=self.actor, review_token=token, acknowledged=True, **facts)
                check(notice_day, "PAPER_MIXED")
                auction = auctions.initiate_pawn_loan_auction(loan.pk, scheduled_date=sale_day,
                    request_key="checkpoint-auction", actor=self.actor)
            prepare_test_auction_service(auction, self.actor, notice_day)
            with on(sale_day):
                check(sale_day, "ROKKAD_ONLY")
                reviewed_id = transaction_completeness(loan, sale_day).review_id
                auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
                quote, _ = opening_payment_balance(loan, as_of_date=sale_day)
                self.assertEqual(quote.principal_outstanding, 800)
                result = auctions.complete_pawn_loan_auction(auction.pk, recovery_amount=quote.total_due,
                    buyer_name="Buyer", actor=self.actor)
                self.assertEqual(result.loan_event.payload["opening_collection"]["profile"], "opening-auctions/1")
                loan.refresh_from_db()
                self.assertEqual(transaction_completeness(loan, sale_day).review_id, reviewed_id)
                self.assertTrue(transaction_completeness(loan, sale_day).complete)
                auctions.reverse_pawn_loan_auction(auction.pk, reason="Actual auction cancellation", actor=self.actor)
                loan.refresh_from_db()
                self.assertEqual(transaction_completeness(loan, sale_day+timedelta(days=1)).status, "ROKKAD_ONLY")
                self.assertEqual(opening_payment_balance(loan, as_of_date=sale_day)[0].total_due, quote.total_due)
                self.assertEqual(loan.loan_events.get(event_kind="MIGRATION_OPENING").payload_fingerprint, frozen)

    def test_unknown_original_valuation_does_not_block_fresh_current_appraisal_monitoring(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        self.review["collateral"][0]["valuation"] = dict(status="UNVERIFIED", source_amount=None, source_date=None,
            evidence_reference="Original valuation not retained; no past approval claimed")
        self.setup["policy"]["valuation_method"] = "LATEST_APPRAISAL"
        day = date(2021, 3, 2)
        with self.scoped(), on(day):
            origin = self.write()
            loan = origin.loan
            event = loan.loan_events.get(event_kind="MIGRATION_OPENING")
            frozen = event.payload_fingerprint
            m.LoanMonitoringPolicy.objects.create(workspace=self.a, version=1, effective_from=day,
                compliance_profile="synthetic-current-risk", ltv_warning_ratio="0.7", ltv_breach_ratio="0.8", ltv_critical_ratio="0.9",
                eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy":"derived-v1"},
                appraisal_freshness_days=7, created_by=self.actor)
            item = loan.collateral_items.get()
            record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
                appraised_value=Decimal("2000"), method="PHYSICAL_INSPECTION", expected_version=0,
                evidence_reference="Actual current inspection", review_notes="Current value assessed separately from original evidence")
            current = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=day)
            self.assertEqual(current.eligible_collateral_value, 2000)
            snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=day)
            self.assertEqual(snapshot.status, "CURRENT")
            self.assertNotIn("VALUATION_UNKNOWN", snapshot.flags)
            self.assertIn("TRANSACTIONS_UNCONFIRMED", snapshot.flags)
            self.assertIsNone(get_pawn_loan_collateral_valuation(loan.pk, as_of_date=day+timedelta(days=8)).eligible_collateral_value)
            event.refresh_from_db()
            self.assertEqual(event.payload_fingerprint, frozen)
