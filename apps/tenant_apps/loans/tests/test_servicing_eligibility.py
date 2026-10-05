"""Action purpose, shared monthly debt and unchanged validated evidence writers."""
from copy import deepcopy
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import paper_repayments as paper
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
from apps.tenant_apps.loans.services.recorded_closures import preview_recorded_closure, record_paper_closure
from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from . import test_shared_monthly_contract as monthly
from . import test_opening_release as opening
from . import test_recorded_origination as old_recorded


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class NativeActionPurposeTests(WorkspaceTestCase):
    setup_tenant = classmethod(monthly.SharedNativeContractTests.setup_tenant.__func__)
    make_loan = monthly.SharedNativeContractTests.make_loan

    def setUp(self):
        monthly.SharedNativeContractTests.setUp(self)
        self.day = date(2026, 6, 6)
        self.enterContext(patch("django.utils.timezone.localdate", side_effect=lambda *a, **kw: self.day))
        m.LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="LD02-", width=5, maximum_number=10000)
        self.inputs = dict(amount="220", received_on=date(2026, 5, 6), receipt_reference="Paper book 17",
            request_key="paper-native", actor=self.actor)

    def paper_payment(self, **changes):
        facts = dict(self.inputs, **changes)
        review = paper.preview_paper_repayment(self.loan.pk, **facts)
        return paper.record_paper_repayment(self.loan.pk, **facts, review_token=review.review_token, confirmed_received=True)

    def closing_facts(self, **changes):
        return dict(date="2026-05-06", amount="1020", number="", reference="Signed closing page",
            basis="PAPER_SETTLEMENT", recipient="", request_key="paper-close", **changes)

    def close_from_paper(self, facts):
        review, token = preview_recorded_closure(loan_id=self.loan.pk, actor=self.actor, data=facts)
        return record_paper_closure(loan_id=self.loan.pk, actor=self.actor, data=facts,
            review_token=token, confirmed=True), review, token

    def test_completed_receipt_on_native_origin_preserves_actual_date_and_terms(self):
        original = deepcopy(self.loan.disbursal_snapshot.evidence)
        paid = self.paper_payment()
        self.assertEqual((paid.allocation.interest, paid.allocation.principal), (20, 200))
        self.assertEqual(paid.loan_event.effective_date, date(2026, 5, 6))
        self.assertEqual(paid.loan_event.payload["repayment"]["recording"]["original_receiver"], None)
        self.assertEqual(self.loan.disbursal_snapshot.evidence, original)
        self.assertEqual(get_servicing_position(self.loan, as_of_date=date(2026, 6, 6)).balance.total_due, 816)
        self.assertEqual(transaction_completeness(self.loan, self.day).status, "UNCONFIRMED")
        self.assertFalse(self.loan.transaction_reviews.exists())
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.assertRaisesMessage(ValueError, "Completed paper receipts"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk)

    def test_preview_is_read_only_retry_and_changed_purpose_or_evidence_fail(self):
        count = self.loan.loan_events.count()
        review = paper.preview_paper_repayment(self.loan.pk, **self.inputs)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertFalse(self.loan.interest_accruals.exists())
        paid = paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=review.review_token, confirmed_received=True)
        again = paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=review.review_token, confirmed_received=True)
        self.assertTrue(again.already_recorded)
        self.assertEqual(paid.loan_event.pk, again.loan_event.pk)
        with self.assertRaisesMessage(ValueError, "recording purpose"):
            record_pawn_loan_repayment(self.loan.pk, amount=220, request_key="paper-native", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "different receipt facts"):
            paper.record_paper_repayment(self.loan.pk, **dict(self.inputs, receipt_reference="Other page"),
                review_token=review.review_token, confirmed_received=True)

    def test_native_paper_receipt_recovery_retains_exact_source_and_coverage(self):
        import hashlib
        from . import test_pawn_recovery as recovery_tests
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        paid = self.paper_payment()
        original = deepcopy(paid.loan_event.payload)
        content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        digest = hashlib.sha256(content).hexdigest()
        tables = recovery._read(content, digest)[0]["tables"]
        recovery_tests.PawnRecoveryTests.empty(self)
        recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
            expected_sha256=digest, commit=True)
        loan = m.PawnLoan.objects.get(pk=self.loan.pk)
        self.assertEqual(m.PawnLoanEvent.objects.get(pk=paid.loan_event.pk).payload, original)
        self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance.total_due, 816)
        self.assertEqual(transaction_completeness(loan, self.day).status, "UNCONFIRMED")
        restored = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        self.assertEqual(recovery._read(restored, hashlib.sha256(restored).hexdigest())[0]["tables"], tables)

    def test_later_activity_and_same_day_stale_review_are_blocked(self):
        self.day = self.inputs["received_on"]
        review = paper.preview_paper_repayment(self.loan.pk, **self.inputs)
        record_pawn_loan_repayment(self.loan.pk, amount=1, request_key="same-day", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed since review"):
            paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=review.review_token, confirmed_received=True)
        self.day = date(2026, 6, 6)
        record_pawn_loan_repayment(self.loan.pk, amount=1, request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "Later activity"):
            paper.preview_paper_repayment(self.loan.pk, **self.inputs)

    def test_failure_rolls_back_native_recognition_receipt_and_allocations(self):
        review = paper.preview_paper_repayment(self.loan.pk, **self.inputs)
        with patch("apps.tenant_apps.loans.services.pawn_repayment.allocate_event_to_obligations", side_effect=RuntimeError("posting failed")):
            with self.assertRaises(RuntimeError):
                paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=review.review_token, confirmed_received=True)
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(self.loan.interest_accruals.exists())

    def test_authorization_and_foreign_workspace_do_not_disclose_or_post(self):
        with self.assertRaises(PermissionDenied):
            paper.preview_paper_repayment(self.loan.pk, **dict(self.inputs, actor=None))
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        other = Company.objects.create(name="Other LD02", schema_name="other-ld02", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            eligibility = servicing_eligibility(self.loan, operation="REPAYMENT", purpose="PAPER", effective_date=self.day)
            self.assertFalse(eligibility.ready)
            self.assertEqual(eligibility.blockers[0].code, "UNSUPPORTED_CONTRACT")
            with self.assertRaises(ValueError):
                paper.preview_paper_repayment(self.loan.pk, **self.inputs)

    def test_completed_native_receipt_posts_under_restricted_role_and_remains_immutable(self):
        role = connection.ops.quote_name("ld02_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            paid = self.paper_payment()
            self.assertEqual(paid.allocation.principal, 200)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.filter(pk=paid.loan_event.pk).update(payload={})
            from apps.tenancy.context import without_workspace_context
            with without_workspace_context():
                self.assertFalse(m.PawnLoanEvent.objects.filter(pk=paid.loan_event.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_full_release_recognizes_all_completed_periods_atomically(self):
        self.day = date(2026, 7, 6)
        quote = preview_pawn_loan_full_release(self.loan.pk)
        self.assertEqual(quote.minimum_settlement, 1060)
        self.assertEqual([p.period_number for p in quote.completed_period_accruals], [1, 2, 3])
        self.assertEqual(self.loan.interest_accruals.count(), 0)
        result = release_pawn_loan_in_full(self.loan.pk, settlement_amount=1060, request_key="full", actor=self.actor)
        self.assertEqual(result.release.interest_amount, 60)
        self.assertEqual(self.loan.interest_accruals.count(), 4)
        self.assertTrue(release_pawn_loan_in_full(self.loan.pk, settlement_amount=1060, request_key="full", actor=self.actor).already_released)
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Return cancelled")
        self.loan.refresh_from_db()
        self.assertEqual(get_servicing_position(self.loan, as_of_date=self.day).balance.total_due, 1060)
        self.assertEqual(self.loan.state, "ACTIVE")

    def test_wrong_full_settlement_rolls_back_completed_recognition_and_number(self):
        with self.assertRaisesMessage(ValueError, "must equal"):
            release_pawn_loan_in_full(self.loan.pk, settlement_amount=999, request_key="wrong", actor=self.actor)
        self.assertFalse(self.loan.interest_accruals.exists())
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertEqual(m.LoanNumberSequence.objects.get(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE").next_number, 1)

    def test_full_release_on_last_upfront_covered_day_recognizes_zero_period(self):
        self.day = date(2026, 5, 5)
        self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 1000)
        result = release_pawn_loan_in_full(self.loan.pk, settlement_amount=1000,
            request_key="covered-day", actor=self.actor)
        self.assertEqual(result.release.interest_amount, 0)
        self.assertEqual(self.loan.interest_accruals.count(), 1)

    def test_paper_settlement_keeps_unknown_handover_and_later_confirmation(self):
        facts = self.closing_facts()
        (release, created), review, token = self.close_from_paper(facts)
        self.assertTrue(created)
        self.assertEqual(Decimal(review["interest"]), 20)
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "PAPER_CLOSED")
        self.assertIsNone(release.items.get().returned_at)
        self.assertEqual(transaction_completeness(self.loan, self.day).status, "UNCONFIRMED")
        self.assertFalse(record_paper_closure(loan_id=self.loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)[1])
        with self.assertRaisesMessage(ValueError, "different closure facts"):
            record_paper_closure(loan_id=self.loan.pk, actor=self.actor, data=dict(facts, reference="Other"), review_token=token, confirmed=True)
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        data = dict(date="2026-05-07", recipient="Borrower", reference="Signed handover", request_key="handover")
        _, signed = preview_paper_handover(self.loan.pk, actor=self.actor, data=data)
        confirm_paper_handover(self.loan.pk, actor=self.actor, data=data, review_token=signed, confirmed=True)
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "WITH_CUSTOMER")
        self.assertIsNone(release.items.get().returned_at)
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        with self.assertRaisesMessage(ValueError, "custody"):
            reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Cannot erase later handover")

    def test_zero_cash_closure_after_fully_received_payment(self):
        self.day = date(2026, 5, 6)
        record_pawn_loan_repayment(self.loan.pk, amount=1020, request_key="all-paid", actor=self.actor)
        self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 0)
        closed = release_pawn_loan_in_full(self.loan.pk, settlement_amount=0, request_key="no-extra-cash", actor=self.actor)
        self.assertEqual(closed.release.settlement_amount, 0)
        self.assertEqual(get_servicing_position(closed.loan, as_of_date=self.day).balance.total_due, 0)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_ordinary_native_screen_offers_paper_purpose_and_closure(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        kwargs = dict(workspace_slug=self.tenant.slug, pk=self.loan.pk)
        response = client.get(reverse("workspace_loans:pawn_loan_repay", kwargs=kwargs))
        self.assertContains(response, "Record a paper receipt")
        self.assertContains(client.get(reverse("workspace_loans:pawn_loan_detail", kwargs=kwargs)), "Record paper closure")


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PaperCurrentServicingTests(WorkspaceTestCase):
    setup_tenant = classmethod(monthly.SharedPaperContractTests.setup_tenant.__func__)
    make_snapshot = monthly.SharedPaperContractTests.make_snapshot
    prepare_history = monthly.SharedPaperContractTests.prepare_history
    admit = monthly.SharedPaperContractTests.admit

    def setUp(self):
        monthly.SharedPaperContractTests.setUp(self)
        self.loan = self.admit()
        self.day = date(2026, 5, 6)
        self.enterContext(patch("django.utils.timezone.localdate", side_effect=lambda *a, **kw: self.day))

    def test_current_digital_collection_and_full_release_on_paper_origin(self):
        loan = self.loan
        paid = record_pawn_loan_repayment(loan.pk, amount=2200, request_key="digital", actor=self.actor)
        self.assertEqual((paid.allocation.interest, paid.allocation.principal), (200, 2000))
        self.assertNotIn("recording", paid.loan_event.payload["repayment"])
        self.assertEqual(get_servicing_position(loan, as_of_date=self.day).balance.total_due, 8000)
        closed = release_pawn_loan_in_full(loan.pk, settlement_amount=8000, request_key="return", actor=self.actor)
        self.assertEqual(closed.release.settlement_amount, 8000)
        self.assertEqual(get_servicing_position(closed.loan, as_of_date=self.day).balance.total_due, 0)


class OpeningPaperClosureTests(opening.OpeningReleaseFixture):

    def test_opening_unknown_handover_settlement_and_paired_reversal(self):
        data = dict(date="2021-02-02", amount="1010", number="", reference="Opening paper closing",
            basis="PAPER_SETTLEMENT", recipient="", request_key="opening-paper-close")
        _, token = preview_recorded_closure(loan_id=self.loan.pk, actor=self.actor, data=data)
        release, _ = record_paper_closure(loan_id=self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(release.interest_amount, 10)
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "PAPER_CLOSED")
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        reversed_release = reverse_pawn_loan_event(release.loan_event.pk, actor=self.actor, reason="Closing page was wrong")
        self.assertIsNotNone(reversed_release.catch_up_reversal_event)
        self.loan.refresh_from_db()
        self.assertEqual(get_servicing_position(self.loan, as_of_date=self.day).balance.total_due, 1010)


class LegacyRecordedCollectionTests(WorkspaceTestCase):
    setup_tenant = classmethod(old_recorded.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = old_recorded.RecordedOriginationTests.make_snapshot

    def test_legacy_event_fold_keeps_current_payment_without_inventing_paper_contract(self):
        loan = self.make_snapshot().loan
        position = get_servicing_position(loan, as_of_date=timezone.localdate())
        self.assertEqual(position.contract.profile, "recorded-event-fold/1")
        paid = record_pawn_loan_repayment(loan.pk, amount=100, request_key="legacy-current", actor=self.actor)
        self.assertEqual((paid.allocation.interest, paid.allocation.principal), (0, 100))
        with self.assertRaisesMessage(ValueError, "supported saved monthly contract"):
            paper.preview_paper_repayment(loan.pk, amount=100, received_on=paid.loan_event.effective_date,
                receipt_reference="Paper", request_key="legacy-paper", actor=self.actor)


class WholeRupeeInterestReleaseTests(WorkspaceTestCase):
    setup_tenant = classmethod(monthly.SharedNativeContractTests.setup_tenant.__func__)
    make_loan = monthly.SharedNativeContractTests.make_loan
    original_principal = Decimal("5025.25")
    interest_quantum = Decimal("1")

    def test_full_release_preserves_paise_principal_with_whole_rupee_interest(self):
        monthly.SharedNativeContractTests.setUp(self)
        m.LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="PAISE-", width=5, maximum_number=10000)
        with patch("django.utils.timezone.localdate", return_value=date(2026, 5, 6)):
            quote = preview_pawn_loan_full_release(self.loan.pk)
            self.assertEqual(quote.minimum_settlement, Decimal("5126.25"))
            release = release_pawn_loan_in_full(self.loan.pk, settlement_amount="5126.25",
                request_key="paise-release", actor=self.actor).release
            self.assertEqual((release.principal_amount, release.interest_amount), (Decimal("5025.25"), 101))


class OpeningAllocationLimitTests(monthly.OpeningImportFixture):
    def setUp(self):
        super().setUp()
        first = self.review["collateral"][0]
        first.update(original_principal="500", remaining_principal="500")
        second = deepcopy(first)
        second.update(id="girvi_loanitem:2", description="Second item", monthly_rate="2")
        self.review["collateral"].append(second)
        self.review["source"]["item_ids"].append(second["id"])

    def test_completed_multiple_item_principal_is_blocked_before_posting_but_current_collection_works(self):
        with self.scoped(), patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
            loan = self.write().loan
            items = list(loan.collateral_items.order_by("pk"))
            for split in (None, {str(items[0].pk): "200", str(items[1].pk): "0"}):
                with self.assertRaisesMessage(ValueError, "one outstanding item only"):
                    paper.preview_paper_repayment(loan.pk, amount=215, received_on=date(2021, 2, 2),
                        receipt_reference="Multiple items", request_key="split", actor=self.actor, item_principal_split=split)
            self.assertEqual(loan.loan_events.count(), 1)
            self.assertFalse(loan.interest_accruals.exists())
            paid = record_pawn_loan_repayment(loan.pk, amount=215, request_key="current", actor=self.actor)
            self.assertEqual((paid.allocation.interest, paid.allocation.principal), (15, 200))
            self.assertEqual(paid.item_allocations[0].monthly_interest_rate, 2)
            self.assertEqual(paid.item_allocations[0].principal_applied, 200)
