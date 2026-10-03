"""Bounded audit browsing, source navigation and private account boundaries."""
import uuid
from datetime import timedelta

from django.core.paginator import Paginator
from django.db import connection
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataOperation
from apps.tenant_apps.loans.selectors.khata_history import history_operations
from apps.tenant_apps.loans.services import khata_accounts
from apps.tenant_apps.loans.web import khata_views
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import draft_args, fixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataHistoryTests(CorrectionFixture, TestCase):
    def request(self, actor=None, **params):
        request = RequestFactory().get("/", params)
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def history(self, **params):
        with workspace_context(self.workspace.pk):
            return khata_views._history_context(self.request(**params), self.account)

    def test_stable_pages_and_date_order_for_many_same_day_events(self):
        items = [self.first, *(self.deposit(description=f"History item {n}") for n in range(51))]
        params = {"history-kind": "DEPOSIT"}
        first = self.history(**params)["history_page"]
        second = self.history(**params, **{"history-page": "2"})["history_page"]
        last = self.history(**params, **{"history-page": "3"})["history_page"]
        self.assertEqual(first.paginator.count, 52)
        self.assertEqual([len(p) for p in (first, second, last)], [25, 25, 2])
        self.assertEqual([op.pk for page in (first, second, last) for op in page],
            [item.received_operation_id for item in reversed(items)])
        oldest = self.history(**params, **{"history-sort": "oldest"})["history_page"]
        self.assertEqual(oldest[0].pk, self.first.received_operation_id)
        self.assertIn("history-kind=DEPOSIT", self.history(**params)["history_query"])
        self.assertTrue(self.history(**params)["open_history"])
        self.assertEqual(self.history(**{"history-page": "invalid"})["history_page"].number, 1)

    def test_event_filters_do_not_filter_the_account_balance_or_write_sources(self):
        with self.later(1, 1):
            self.quote()
            receipt = self.pay("25000")
            incoming = self.replacement(grams="100")
            exchange = self.exchange([self.first], [incoming])
            before = self.balance()
            with workspace_context(self.workspace.pk):
                count = self.account.operations.count()
                for kind, target in (("WITHDRAW", None), ("DEPOSIT", incoming.received_operation_id),
                        ("INTEREST", receipt.pk), ("EXCHANGE", exchange.pk)):
                    page = self.history(**{"history-kind": kind})["history_page"]
                    self.assertTrue(all(op.kind == kind for op in page))
                    self.assertTrue(page.paginator.count)
                    if target:
                        self.assertIn(target, [op.pk for op in page])
                    response = khata_views.detail(self.request(**{"history-kind": kind}), self.account.pk)
                    self.assertContains(response, "Source history")
                    self.assertIn("private", response["Cache-Control"])
                self.assertEqual(self.account.operations.count(), count)
            self.assertEqual(self.balance(), before)

    def test_inclusive_dates_invalid_filters_and_large_operation_id(self):
        with self.later(0, 3):
            target = self.deposit(description="Date boundary item")
            day = timezone.localdate()
        with self.later(0, 4):
            self.deposit(description="Date boundary item")
        page = self.history(**{"history-from_date": day.isoformat(), "history-to_date": day.isoformat()})["history_page"]
        self.assertEqual([op.pk for op in page], [target.received_operation_id])
        for params in ({"history-from_date": "bad"}, {"history-kind": "FAKE"},
                {"history-operation": "999999999999999999999999"},
                {"history-from_date": day.isoformat(), "history-to_date": (day - timedelta(days=1)).isoformat()}):
            context = self.history(**params)
            self.assertTrue(context["history_form"].errors)
            self.assertEqual(context["history_page"].paginator.count, 0)

    def test_item_search_finds_receipts_photos_exchange_and_handover_without_duplicates(self):
        incoming = [self.replacement(grams="60"), self.replacement(grams="60")]
        photo = self.photo(self.first)
        exchange = self.exchange([self.first], incoming)
        handover = self.handover(self.first, exchange)
        by_id = self.history(**{"history-q": str(self.first.pk)})["history_page"]
        by_uuid = self.history(**{"history-q": str(self.first.public_id)})["history_page"]
        expected = {self.first.received_operation_id, photo.operation_id, exchange.pk, handover.pk}
        self.assertEqual({op.pk for op in by_id}, expected)
        self.assertEqual({op.pk for op in by_uuid}, expected)
        common = self.history(**{"history-q": "Vault A / bag 1", "history-kind": "EXCHANGE"})["history_page"]
        self.assertEqual([op.pk for op in common], [exchange.pk])
        payment = self.history(**{"history-q": "Cash handed over"})["history_page"]
        self.assertEqual([op.kind for op in payment], ["WITHDRAW"])

    def test_correction_links_find_the_exact_source_outside_the_current_page(self):
        with self.later(1, 1):
            receipt = self.pay("25000")
            correction = self.correct(receipt)
            for n in range(30):
                self.deposit(description=f"Later source {n}")
            with workspace_context(self.workspace.pk):
                response = khata_views.detail(self.request(**{"history-operation": correction.pk}), self.account.pk)
                self.assertContains(response, f"history-operation={receipt.pk}#operation-{receipt.pk}")
                self.assertContains(response, f'id="operation-{correction.pk}"')
                response = khata_views.detail(self.request(**{"history-operation": receipt.pk}), self.account.pk)
                self.assertContains(response, f"history-operation={correction.pk}#operation-{correction.pk}")
                self.assertContains(response, f'id="operation-{receipt.pk}"')
                self.assertEqual(self.history(**{"history-operation": receipt.pk})["history_page"].paginator.count, 1)

    def test_account_workspace_and_read_only_viewer_boundaries(self):
        other = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            operation = self.account.operations.get(kind="WITHDRAW")
            self.assertFalse(history_operations(other, dict(operation=operation.pk)).exists())
            viewer = self.staff()
            response = khata_views.detail(self.request(actor=viewer, **{"section": "history"}), self.account.pk)
            self.assertContains(response, "Source history")
        foreign_workspace, _, _ = fixture(uuid.uuid4().hex[:8])
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            history_operations(self.account, {})
        with workspace_context(foreign_workspace.pk):
            with self.assertRaisesMessage(ValueError, "matching Workspace"):
                history_operations(self.account, {})
            request = self.request()
            request.workspace = foreign_workspace
            request.user = foreign_workspace.owner
            with self.assertRaises(Http404):
                khata_views.detail(request, self.account.pk)

    def test_history_rows_are_bounded_and_related_sources_do_not_add_queries(self):
        for n in range(30):
            self.deposit(description=f"Bounded source {n}")
        with workspace_context(self.workspace.pk):
            operations = history_operations(self.account, dict(kind="DEPOSIT"))
            with CaptureQueriesContext(connection) as queries:
                page = Paginator(operations, 25).page(1)
                for op in page:
                    op.received_item.description
                    op.created_by.get_username()
            self.assertEqual(len(page), 25)
            self.assertEqual(len(queries), 2)
