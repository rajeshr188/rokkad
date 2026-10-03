"""Cash truth across dated compensation, current custody and protected exports."""
import csv
import io
import uuid
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.selectors.khata_reports import cash_operations, cash_totals, cash_row, custody_items, custody_totals
from apps.tenant_apps.loans.services.khata_report_exports import export_csv
from apps.tenant_apps.loans.services import khata_accounts, khata_opening
from apps.tenant_apps.loans.web import khata_reports
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import draft_args, fixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataReportTests(CorrectionFixture, TestCase):
    def request(self, actor=None, **params):
        request = RequestFactory().get("/", params)
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def cash(self, **data):
        return cash_operations(workspace=self.workspace, data=data)

    def custody(self, **data):
        return custody_items(workspace=self.workspace, data=data)

    def test_withdrawals_interest_reduction_settlement_and_totals_are_cash_only(self):
        with self.later(1):
            receipt = self.pay("100000")
            self.proposal("60000"); revision = self.activate(self.approve_change("40000")); settlement = self.settle()
            with workspace_context(self.workspace.pk):
                rows = self.cash()
                self.assertEqual({op.kind for op in rows}, {"WITHDRAW", "INTEREST", "REVISE", "SETTLE"})
                self.assertEqual(cash_totals(rows), dict(principal_in=Decimal("100000"), interest_in=Decimal("100000"),
                    cash_in=Decimal("200000"), cash_out=Decimal("100000"), net_cash=Decimal("100000")))
                day = timezone.localdate()
                dated = self.cash(from_date=day, to_date=day)
                self.assertEqual({op.pk for op in dated}, {receipt.pk, revision.pk, settlement.pk})
                self.assertEqual(cash_totals(dated)["net_cash"], Decimal("200000"))
                self.assertEqual(self.cash(kind="REVISE").get().principal_in, Decimal("40000"))

    def test_not_received_correction_outside_range_removes_fictitious_cash_not_as_refund(self):
        with self.later(1):
            receipt = self.pay("25000"); receipt_day = timezone.localdate()
        with self.later(1, 1):
            correction = self.correct(receipt)
            with workspace_context(self.workspace.pk):
                original = self.cash(from_date=receipt_day, to_date=receipt_day).get()
                self.assertEqual(original.cash_in, 0)
                self.assertEqual(original.amount, Decimal("25000"))
                self.assertEqual(original.corrected_by.pk, correction.pk)
                self.assertIn("not received", cash_row(original)["note"])
                self.assertEqual(cash_totals(self.cash(kind="CORRECT"))["cash_out"], 0)
                response = khata_reports.reports(self.request(from_date=str(receipt_day), to_date=str(receipt_day)))
                self.assertContains(response, f"Corrected by #{correction.pk}")
                self.assertContains(response, "zero actual cash")
            self.assertEqual(self.balance()["paid_interest"], 0)

    def test_actual_refund_remains_separate_cash_out_on_correction_date(self):
        with self.later(1):
            receipt = self.pay("25000"); received_on = timezone.localdate()
        with self.later(1, 1):
            refund = self.correct(receipt, cash_resolution="REFUNDED")
            with workspace_context(self.workspace.pk):
                self.assertEqual(cash_totals(self.cash(from_date=received_on, to_date=received_on))["cash_in"], Decimal("25000"))
                rows = self.cash(from_date=timezone.localdate(), to_date=timezone.localdate())
                self.assertEqual(rows.get().pk, refund.pk)
                self.assertEqual(cash_totals(rows)["net_cash"], Decimal("-25000"))
                self.assertEqual(cash_totals(self.cash(kind="CORRECT"))["cash_out"], Decimal("25000"))

    def test_non_cash_exchange_correction_is_visible_without_cash_amount(self):
        incoming = self.replacement("100")
        source = self.exchange([self.first], [incoming]); correction = self.correct(source)
        with workspace_context(self.workspace.pk):
            row = self.cash(kind="CORRECT").get()
            self.assertEqual(row.pk, correction.pk)
            self.assertEqual(row.cash_in + row.cash_out, 0)
            self.assertIn("Exchange correction", cash_row(row)["note"])

    def test_current_custody_tracks_reservation_handover_and_compensated_replacements(self):
        incoming = [self.replacement("10"), self.replacement("10")]
        exchange = self.exchange([self.first], incoming)
        with workspace_context(self.workspace.pk):
            pending = self.custody(custody="pending").get()
            self.assertEqual(pending.pk, self.first.pk)
            self.assertEqual(pending.reservation_id, exchange.pk)
            self.assertEqual(self.custody().count(), 3)
        correction = self.correct(exchange)
        with workspace_context(self.workspace.pk):
            self.assertEqual(set(self.custody(custody="pending").values_list("pk", flat=True)), {i.pk for i in incoming})
            self.assertEqual(self.custody(custody="held").get().pk, self.first.pk)
        handover = self.handover(incoming[0], correction)
        with workspace_context(self.workspace.pk):
            returned = self.custody(custody="returned").get()
            self.assertEqual(returned.return_id, handover.pk)
            self.assertEqual(returned.return_recipient, "Borrower")
            self.assertEqual(returned.return_reference, "Signed handover")
            self.assertEqual(self.custody().count(), 2)
            response = khata_reports.reports(self.request(section="custody", custody="returned"))
            self.assertContains(response, f"Actual return #{handover.pk}")

    def test_unopened_and_settled_pending_items_are_not_lost_and_weights_stay_per_metal(self):
        active = self.account
        self.account = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        one = self.deposit(metal="SILVER", quantity=4, net_weight="50", gross_weight="55")
        two = self.deposit(metal="SILVER", quantity=2, net_weight="25", gross_weight="25")
        returned = khata_opening.return_unopened_item(**self.command(), item_id=two.pk, recipient="Borrower", reason="Returned unopened item")
        self.account = active; self.settle()
        with workspace_context(self.workspace.pk):
            totals = custody_totals(self.custody())
            self.assertEqual({r["metal"] for r in totals}, {"GOLD", "SILVER"})
            silver = next(r for r in totals if r["metal"] == "SILVER")
            self.assertEqual((silver["records"], silver["pieces"], silver["net"]), (1, 4, Decimal("50")))
            self.assertEqual(self.custody(custody="pending").get().pk, self.first.pk)
            self.assertEqual(self.custody(custody="returned").get().return_reference, "Returned unopened item")
            self.assertEqual(self.custody(custody="returned").get().return_id, returned.pk)

    def test_receipt_dates_select_current_cohort_not_historical_custody(self):
        receipt_day = self.started_on
        incoming = self.replacement("100")
        exchange = self.exchange([self.first], [incoming])
        with self.later(0, 1):
            self.handover(self.first, exchange)
            with workspace_context(self.workspace.pk):
                selected = self.custody(from_date=receipt_day, to_date=receipt_day, custody="returned")
                self.assertEqual(selected.get().pk, self.first.pk)
                self.assertEqual(self.custody(from_date=receipt_day, to_date=receipt_day).get().pk, incoming.pk)

    def test_totals_before_pages_sort_and_csv_includes_all_matching_sources(self):
        for n in range(27):
            self.payout("1")
        with workspace_context(self.workspace.pk):
            response = khata_reports.reports(self.request(page="2"))
            self.assertContains(response, "1,00,027")
            self.assertEqual(response.content.count(b'data-operation="'), 3)
            self.assertContains(response, "Page 2 of 2")
            oldest = list(self.cash(sort="oldest").values_list("pk", flat=True))
            self.assertEqual(list(self.cash(sort="newest").values_list("pk", flat=True)), oldest[::-1])
            download = khata_reports.reports(self.request(export="csv", page="2"))
            data = list(csv.DictReader(io.StringIO(download.content.decode("utf-8-sig"))))
            self.assertEqual(len(data), 28)
            self.assertEqual(sum(Decimal(r["Cash out INR"]) for r in data), Decimal("100027"))
            self.assertTrue(all('/events/' in r["Source URL"] for r in data))
            self.assertIn("private", download["Cache-Control"])

    def test_filters_bad_dates_unknown_sections_and_export_bound_are_explicit(self):
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.cash(q=self.account.account_number).count(), 1)
            self.assertEqual(self.custody(q=str(self.first.public_id)).get().pk, self.first.pk)
            self.assertFalse(self.cash(association="associated"))
            for data in ({"from_date": "bad"}, {"from_date": "2026-10-11", "to_date": "2026-10-10"},
                    {"account": "999999999999999999999999"}, {"borrower": "999999999999999999999999"}):
                response = khata_reports.reports(self.request(**data))
                self.assertNotContains(response, 'data-operation="')
            self.assertEqual(khata_reports.reports(self.request(export="csv", from_date="bad")).status_code, 400)
            with self.assertRaises(Http404):
                khata_reports.reports(self.request(section="as-of-balances"))
            with patch("apps.tenant_apps.loans.services.khata_report_exports.MAX_EXPORT_ROWS", 0):
                response = khata_reports.reports(self.request(export="csv"))
                self.assertEqual(response.status_code, 409)
                self.assertContains(response, "Narrow", status_code=409)

    def test_csv_preserves_exact_item_identity_return_source_and_escapes_formulas(self):
        item = self.deposit(description="=HYPERLINK(\"bad\")", storage_reference="@unsafe", quantity=3)
        with workspace_context(self.workspace.pk):
            response = khata_reports.reports(self.request(section="custody", export="csv", q=str(item.public_id)))
            rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["Permanent UUID"], str(item.public_id))
            self.assertEqual(rows[0]["Description"], "'=HYPERLINK(\"bad\")")
            self.assertEqual(rows[0]["Storage"], "'@unsafe")
            self.assertEqual(rows[0]["Pieces"], "3")

    def test_view_export_workspace_and_context_boundaries_and_no_source_writes(self):
        viewer = self.staff()
        with workspace_context(self.workspace.pk):
            before = self.balance(); count = self.account.operations.count()
            self.assertContains(khata_reports.reports(self.request(actor=viewer)), "Khata operational reports")
            self.assertNotContains(khata_reports.reports(self.request(actor=viewer)), "Download matching CSV")
            with self.assertRaises(PermissionDenied):
                khata_reports.reports(self.request(actor=viewer, export="csv"))
            exporter = self.staff("report_export")
            self.assertEqual(khata_reports.reports(self.request(actor=exporter, export="csv")).status_code, 200)
            self.assertEqual(self.account.operations.count(), count)
            self.assertEqual(self.balance(), before)
            request = self.request(); request.method = "POST"
            self.assertEqual(khata_reports.reports(request).status_code, 405)
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            self.cash()
        foreign, actor, _ = fixture(uuid.uuid4().hex[:8])
        with workspace_context(foreign.pk):
            self.assertFalse(cash_operations(workspace=foreign, data={"account": self.account.pk}))
            self.assertFalse(custody_items(workspace=foreign, data={"account": self.account.pk}))
            with self.assertRaisesMessage(ValueError, "matching Workspace"):
                export_csv(workspace=self.workspace, section="cash", queryset=[], absolute_url=lambda u:u)
