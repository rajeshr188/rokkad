"""Collection boundaries, estimates, saved event provenance and private reads."""
import copy
import uuid
from datetime import date, datetime, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import patch

from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.domain.khata import anniversary
from apps.tenant_apps.loans.selectors.khata_collections import collection_rows, recorded_exchange_warnings
from apps.tenant_apps.loans.selectors.khata_events import event_operations, event_details
from apps.tenant_apps.loans.services import khata_accounts, khata_opening
from apps.tenant_apps.loans.web import khata_views, khata_workflows
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import draft_args, fixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataCollectionTests(CorrectionFixture, TestCase):
    def request(self, actor=None, **params):
        request = RequestFactory().get("/", params)
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def row(self, status="all", horizon=7):
        with workspace_context(self.workspace.pk):
            return next(r for r in collection_rows(workspace=self.workspace, status=status, horizon=horizon)
                if r["account"].pk == self.account.pk)

    def test_monthly_due_overdue_partial_receipt_correction_and_next_due(self):
        row = self.row()
        self.assertEqual(row["next_due"], anniversary(self.started_on, 1))
        self.assertEqual(row["next_unpaid"], Decimal("100000"))
        self.assertTrue(row["estimated"])
        self.assertEqual(row["due_interest"], 0)
        with self.later(1):
            row = self.row()
            self.assertEqual((row["collection_status"], row["days_overdue"]), ("due", 0))
            self.assertFalse(row["estimated"])
            receipt = self.pay("25000")
            self.assertEqual(self.row()["next_unpaid"], Decimal("75000"))
            self.correct(receipt)
            self.assertEqual(self.row()["next_unpaid"], Decimal("100000"))
            self.pay("100000")
            self.assertEqual(self.row()["next_due"], anniversary(self.started_on, 2))
        with self.later(2, 1):
            row = self.row()
            self.assertEqual((row["collection_status"], row["days_overdue"]), ("overdue", 1))
            self.assertEqual(row["next_unpaid"], Decimal("100000"))
            self.assertEqual(row["due_interest"], self.balance()["due_interest"])

    def test_oldest_unpaid_instalment_is_distinct_from_total_arrears(self):
        with self.later(3, 4):
            self.pay("25000")
            row = self.row()
            self.assertEqual(row["next_due"], anniversary(self.started_on, 1))
            self.assertEqual(row["next_unpaid"], Decimal("75000"))
            self.assertEqual(row["due_interest"], Decimal("275000"))
            self.assertEqual(row["days_overdue"], (timezone.localdate() - anniversary(self.started_on, 1)).days)

    def test_annual_estimate_groups_months_and_preserves_rate_unit(self):
        self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.open("ANNUAL")
        with self.later(4):
            row = self.row()
            self.assertEqual(row["next_due"], anniversary(self.started_on, 12))
            self.assertEqual(row["next_unpaid"], Decimal("1200000"))
            self.assertEqual(row["due_interest"], 0)
            self.assertEqual(row["interest"], Decimal("400000"))
        with self.later(12):
            self.assertEqual(self.row()["collection_status"], "due")
            self.pay("1200000")
            self.assertEqual(self.row()["next_due"], anniversary(self.started_on, 24))
        with self.later(24, 1):
            self.assertEqual(self.row()["days_overdue"], 1)

    def test_upcoming_window_does_not_skip_the_due_day_in_same_calendar_month(self):
        with self.later(1, -5):
            self.assertEqual(self.row(status="upcoming")["next_due"], anniversary(self.started_on, 1))
            with workspace_context(self.workspace.pk):
                self.assertFalse(collection_rows(workspace=self.workspace, status="due"))
        with self.later(1):
            with workspace_context(self.workspace.pk):
                self.assertFalse(collection_rows(workspace=self.workspace, status="upcoming"))

    def test_short_month_and_leap_anniversaries_restore_original_day(self):
        with patch("django.utils.timezone.now", return_value=datetime(2024, 1, 31, 12, tzinfo=dt_timezone.utc)):
            self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
            self.quote(); self.open()
        with patch("django.utils.timezone.now", return_value=datetime(2024, 2, 25, 12, tzinfo=dt_timezone.utc)):
            self.assertEqual(self.row()["next_due"], date(2024, 2, 29))
        with patch("django.utils.timezone.now", return_value=datetime(2024, 2, 29, 12, tzinfo=dt_timezone.utc)):
            self.pay("100000")
            self.assertEqual(self.row()["next_due"], date(2024, 3, 31))

    def test_only_activated_revisions_affect_future_estimate_and_zero_rates_are_clear(self):
        with self.later(1):
            self.pay("100000")
            self.proposal("15000000", rate="2")
            self.assertEqual(self.row()["next_unpaid"], Decimal("100000"))
            self.quote(); approval = self.approve_change()
            self.assertEqual(self.row()["next_unpaid"], Decimal("100000"))
            self.activate(approval)
            self.assertEqual(self.row()["next_unpaid"], Decimal("300000"))
        self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.open(monthly_rate="0")
        self.assertEqual(self.row()["collection_status"], "clear")

    def test_read_pages_never_finalize_or_collect_and_viewer_cannot_receive(self):
        with self.later(1, 1):
            before = self.balance()
            viewer = self.staff()
            with workspace_context(self.workspace.pk):
                count = self.account.operations.count()
                response = khata_views.collections(self.request())
                self.assertContains(response, "Receive interest")
                self.assertContains(response, "Unavailable")  # Yesterday's prices do not hide dues.
                self.assertContains(response, "1,00,000")
                self.assertIn("private", response["Cache-Control"])
                self.assertContains(khata_views.collections(self.request(actor=viewer)), "Interest schedule")
                self.assertNotContains(khata_views.collections(self.request(actor=viewer)), "Receive interest")
                self.assertEqual(self.account.operations.count(), count)
            self.assertEqual(before, self.balance())

    def test_filters_invalid_input_unavailable_evidence_and_totals_before_paging(self):
        main = self.account
        for _ in range(26):
            self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
            self.open()
        self.account = main
        with self.later(1, 1), workspace_context(self.workspace.pk):
            response = khata_views.collections(self.request(page="2", status="overdue", horizon="30"))
            self.assertContains(response, "27,00,000")
            self.assertContains(response, "Page 2 of 2")
            self.assertEqual(response.content.count(b'data-account="'), 2)
            with patch.object(khata_views, "collection_rows") as read:
                response = khata_views.collections(self.request(horizon="999"))
                read.assert_not_called()
            self.assertContains(response, "Select a valid choice")
            rows = collection_rows(workspace=self.workspace, filters={"q": main.account_number})
            self.assertEqual([r["account"].pk for r in rows], [main.pk])
            with patch("apps.tenant_apps.loans.selectors.khata_collections.account_summary", side_effect=ValueError("Incomplete")):
                response = khata_views.collections(self.request(q=main.account_number, status="overdue"))
                self.assertContains(response, "Complete money totals are unavailable")
                self.assertContains(response, "Needs review")
        self.settle()
        with workspace_context(self.workspace.pk):
            self.assertFalse(collection_rows(workspace=self.workspace, filters={"q": main.account_number}, status="all"))

    def test_recorded_warning_and_current_cover_have_separate_meaning(self):
        incoming = self.replacement("10")
        source = self.exchange([self.first], [incoming])
        with workspace_context(self.workspace.pk):
            row = self.row()
            warnings = recorded_exchange_warnings(workspace=self.workspace, account_ids=[self.account.pk])
            self.assertEqual(warnings[self.account.pk].pk, source.pk)
            response = khata_views.collections(self.request(status="all"))
            self.assertContains(response, "Below agreed cover")
            self.assertContains(response, f"Exchange #{source.pk}")
        self.correct(source)
        with workspace_context(self.workspace.pk):
            response = khata_views.collections(self.request(status="all"))
            self.assertContains(response, "subsequently corrected")
            self.assertContains(response, "Within agreed cover")

    def test_exchange_event_keeps_groups_values_policies_and_links_after_later_changes(self):
        incoming = [self.replacement("10"), self.replacement("10")]
        source = self.exchange([self.first], incoming)
        original = copy.deepcopy(source.evidence)
        self.quote("20000")
        khata_opening.set_policies(workspace=self.workspace, actor=self.actor, exchange="BLOCK", overdue="BLOCK",
            reason="Later owner policy", request_key=uuid.uuid4())
        with workspace_context(self.workspace.pk):
            op = event_operations(self.account).get(pk=source.pk)
            data = event_details(op)
            self.assertEqual({g["role"]: len(g["rows"]) for g in data["groups"]}, {"IN": 2, "OUT": 1})
            self.assertTrue(data["warnings"])
            self.assertEqual(data["snapshot"]["exchange_policy"], "WARN")
            response = khata_views.event(self.request(), self.account.pk, source.pk)
            self.assertContains(response, "Exact collateral groups")
            self.assertContains(response, "10,000")  # Frozen price, not today's 20,000.
            self.assertContains(response, "Borrower exchanged collateral")
            for item in (self.first, *incoming):
                self.assertContains(response, f"item={item.public_id}#collateral-item-{item.public_id}")
            source.refresh_from_db()
            self.assertEqual(source.evidence, original)
        correction = self.correct(source)
        with workspace_context(self.workspace.pk):
            response = khata_views.event(self.request(), self.account.pk, source.pk)
            self.assertContains(response, "subsequently corrected")
            self.assertContains(response, f"events/{correction.pk}/")

    def test_receipt_revision_handover_and_charge_details_are_typed_saved_sources(self):
        with self.later(1):
            receipt = self.pay("100000")
            self.proposal("60000"); revision = self.activate(self.approve_change("40000"))
            self.quote(); incoming = self.replacement("100")
            exchange = self.exchange([self.first], [incoming]); handover = self.handover(self.first, exchange)
            with workspace_context(self.workspace.pk):
                response = khata_views.event(self.request(), self.account.pk, receipt.pk)
                self.assertContains(response, "Receipt allocation, oldest due first")
                response = khata_views.event(self.request(), self.account.pk, revision.pk)
                self.assertContains(response, "Signed borrower agreement")
                self.assertContains(response, "Actual principal repayment: INR 40,000")
                response = khata_views.event(self.request(), self.account.pk, handover.pk)
                self.assertContains(response, "Signed handover")
                self.assertContains(response, f"events/{exchange.pk}/")
                accrued = self.account.operations.get(kind="ACCRUE")
                self.assertContains(khata_views.event(self.request(), self.account.pk, accrued.pk), "Frozen interest periods")

    def test_event_workspace_account_viewer_method_and_context_boundaries(self):
        other = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        source = self.first.received_operation
        with workspace_context(self.workspace.pk):
            with self.assertRaises(Http404):
                khata_views.event(self.request(), other.pk, source.pk)
            self.assertContains(khata_views.event(self.request(actor=self.staff()), self.account.pk, source.pk), "Recorded event")
            request = self.request(); request.method = "POST"
            self.assertEqual(khata_views.event(request, self.account.pk, source.pk).status_code, 405)
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            event_operations(self.account)
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            collection_rows(workspace=self.workspace)
        foreign, actor, _ = fixture(uuid.uuid4().hex[:8])
        with workspace_context(foreign.pk):
            request = self.request(actor=actor); request.workspace = foreign
            with self.assertRaises(Http404):
                khata_views.event(request, self.account.pk, source.pk)
