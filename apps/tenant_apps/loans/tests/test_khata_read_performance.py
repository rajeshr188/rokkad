"""Read pruning preserves canonical money, custody and exact private identities."""
import uuid
from unittest.mock import patch

from django.test import RequestFactory, TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.selectors.khata_summary import summary_accounts, account_summary, collateral_cover, MONEY_FIELDS
from apps.tenant_apps.loans.services import khata_accounts
from apps.tenant_apps.loans.web import khata_views, khata_labels
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import draft_args
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataReadPerformanceTests(CorrectionFixture, TestCase):
    def request(self, **params):
        request = RequestFactory().get("/", params)
        request.user, request.workspace = self.actor, self.workspace
        return request

    def compare_reads(self, account=None):
        account = account or self.account
        with workspace_context(self.workspace.pk):
            full = summary_accounts(workspace=self.workspace).get(pk=account.pk)
            compact = summary_accounts(workspace=self.workspace, balances_only=True).get(pk=account.pk)
            expected, actual = account_summary(full), account_summary(compact)
            for key in (*MONEY_FIELDS, "outstanding", "schedule", "held_count", "pending_returns", "agreement", "opened"):
                self.assertEqual(actual[key], expected[key], key)
            self.assertEqual(collateral_cover(compact, actual), collateral_cover(full, expected))
            self.assertTrue(all(op.kind in ("WITHDRAW", "REVISE", "SETTLE") for op in compact.summary_operations))
            self.assertNotIn("collateral", compact._prefetched_objects_cache)

    def test_compact_reads_equal_complete_sources_through_revisions_receipts_and_closure(self):
        self.compare_reads()
        with self.later(1, 1):
            self.quote()
            self.revise("15000000", "1.5")
            receipt = self.pay("25000")
            self.compare_reads()
            self.correct(receipt)
            self.compare_reads()
        with self.later(2, 2):
            self.quote()
            self.settle()
            self.compare_reads()
            with workspace_context(self.workspace.pk):
                reservation = self.account.operations.get(kind="SETTLE")
            self.handover(self.first, reservation)
            self.compare_reads()

    def test_corrected_exchange_and_draft_custody_counts_match_complete_reads(self):
        incoming = self.replacement()
        exchange = self.exchange([self.first], [incoming])
        self.compare_reads()
        correction = self.correct(exchange)
        self.compare_reads()
        self.handover(incoming, correction)
        self.compare_reads()
        draft = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.compare_reads(draft)
        khata_accounts.cancel_draft(workspace=self.workspace, actor=self.actor, account_id=draft.pk, reason="Cancelled fictional draft")
        self.compare_reads(draft)

    def test_nonfinancial_tabs_remain_available_without_balance_replay(self):
        with workspace_context(self.workspace.pk), patch.object(khata_views, "account_summary", side_effect=AssertionError("No balance graph needed")), patch.object(khata_views, "collateral_cover", side_effect=AssertionError("No valuation needed")):
            for tab in ("history", "collateral", "documents"):
                response = khata_views.detail(self.request(tab=tab), self.account.pk)
                self.assertContains(response, f'id="khata-panel-{tab}"')
                self.assertIn("no-store", response["Cache-Control"])

    def test_custody_is_bounded_and_qr_and_history_target_exact_item_across_pages(self):
        items = [self.first, *(self.deposit(description=f"Paged item {n}") for n in range(57))]
        self.photo(items[-1])
        with workspace_context(self.workspace.pk):
            first = khata_views.detail(self.request(section="collateral"), self.account.pk)
            self.assertContains(first, '<tr id="collateral-item-', count=25)
            self.assertNotContains(first, f'id="collateral-item-{items[-1].public_id}"')
            last = khata_views.detail(self.request(section="collateral", **{"collateral-page": 3}), self.account.pk)
            self.assertContains(last, '<tr id="collateral-item-', count=8)
            scan = khata_labels.item_scan(self.request(), items[-1].public_id)
            self.assertIn(f'&item={items[-1].public_id}#collateral-item-', scan["Location"])
            exact = khata_views.detail(self.request(section="collateral", item=str(items[-1].public_id)), self.account.pk)
            self.assertContains(exact, '<tr id="collateral-item-', count=1)
            self.assertContains(exact, f'id="collateral-item-{items[-1].public_id}"')
            self.assertContains(exact, "?thumbnail=1")
            history = khata_views.detail(self.request(**{"history-operation": items[-1].received_operation_id}), self.account.pk)
            self.assertContains(history, f'item={items[-1].public_id}#collateral-item-')
            invalid = khata_views.detail(self.request(section="collateral", item="invalid"), self.account.pk)
            self.assertNotContains(invalid, '<tr id="collateral-item-')

    def test_register_filters_narrow_accounts_before_replay_and_totals_precede_pagination(self):
        for _ in range(27):
            khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        visited = []
        def capture(account):
            visited.append(account.pk)
            return account_summary(account)
        with workspace_context(self.workspace.pk), patch("apps.tenant_apps.loans.selectors.khata_summary.account_summary", side_effect=capture):
            response = khata_views.index(self.request(q="KH00028"))
            self.assertContains(response, "KH00028")
            self.assertEqual(len(visited), 1)
            visited.clear()
            response = khata_views.index(self.request(state="invalid"))
            self.assertEqual(visited, [])
            response = khata_views.index(self.request(q="KH", page=2))
            self.assertContains(response, "INR 1,00,000")
            self.assertContains(response, "KH00001")
            self.assertEqual(len(visited), 28)

    def test_selected_item_is_account_scoped_and_light_reads_require_workspace_context(self):
        other = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            response = khata_views.detail(self.request(section="collateral", item=str(self.first.public_id)), other.pk)
            self.assertNotContains(response, f'id="collateral-item-{self.first.public_id}"')
        with self.assertRaises(ValueError):
            summary_accounts(workspace=self.workspace, balances_only=True)
