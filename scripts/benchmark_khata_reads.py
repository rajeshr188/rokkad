"""Profile fictional Khata reads in a dedicated Django test database only.

Run with DJANGO_SETTINGS_MODULE=django_project.settings.test and DB_NAME starting
khata_perf_reads_. All fixture writes use supported services; never a pilot import.
Timings describe warm direct Django views, excluding middleware/network/browser.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import gc
import json
from pathlib import Path
import statistics
import sys
import time
import tracemalloc
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import django
django.setup()

from django.conf import settings
from django.db import connection, connections
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.tests.test_khata_corrections import CorrectionFixture
from apps.tenant_apps.loans.tests.test_khata_foundation import draft_args
from apps.tenant_apps.loans.tests.test_khata_opening import STORAGES
from apps.tenant_apps.loans.services import khata_accounts
from apps.tenant_apps.loans.web import khata_views, khata_items, khata_workflows


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--output", required=True)
parser.add_argument("--sizes", default="25,250,1000")
parser.add_argument("--repeats", type=int, default=3)
args = parser.parse_args()
sizes = sorted(set(int(n) for n in args.sizes.split(",")))
if (settings.SETTINGS_MODULE != "django_project.settings.test"
        or not connection.settings_dict["NAME"].startswith("khata_perf_reads_")
        or not sizes or min(sizes) < 10 or max(sizes) > 3000
        or not 2 <= args.repeats <= 10):
    parser.error("Use dedicated khata_perf_reads_ test settings; sizes 10..3000, repeats 2..10.")
report = dict(direct_views=True, network_included=False, warm=True, restricted_role="khata_image_runtime",
    repeats=args.repeats, scenarios=[], competing_readers=4)


@override_settings(STORAGES=STORAGES)
class ReadBenchmark(CorrectionFixture, TransactionTestCase):
    def read(self, kind, params=None, actor=None):
        request = RequestFactory().get("/", params or {})
        request.workspace, request.user = self.workspace, actor or self.actor
        with workspace_context(self.workspace.pk):
            with connection.cursor() as cursor:
                cursor.execute("SET LOCAL ROLE khata_image_runtime")
            try:
                if kind == "register":
                    response = khata_views.index(request)
                elif kind == "picker":
                    response = khata_items.browse(request, self.account.pk)
                elif kind in ("photo", "approve-change"):
                    response = khata_workflows.operate(request, self.account.pk, kind)
                else:
                    response = khata_views.detail(request, self.account.pk)
                assert response.status_code == 200
                return len(response.content)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")

    def profile(self, kind, params):
        self.read(kind, params)  # Warm templates, application caches and connection.
        elapsed = []
        for _ in range(args.repeats):
            start = time.perf_counter()
            byte_count = self.read(kind, params)
            elapsed.append((time.perf_counter() - start) * 1000)
        gc.collect()
        tracemalloc.start()
        with CaptureQueriesContext(connection) as queries:
            self.read(kind, params)
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        return dict(median_ms=round(statistics.median(elapsed), 2), samples_ms=[round(v, 2) for v in elapsed],
            queries=len(queries), peak_python_mib=round(peak / 1024**2, 3), response_bytes=byte_count)

    def test_reads(self):
        assert connection.settings_dict["NAME"].startswith("test_khata_perf_reads_")
        with connection.cursor() as cursor:
            cursor.execute("GRANT SELECT ON ALL TABLES IN SCHEMA public TO khata_image_runtime")
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname='khata_image_runtime'")
            assert cursor.fetchone() == (False, False)
        viewers = [self.staff() for _ in range(3)]
        # One corrected exchange and both pending/handed-over custody sources.
        original = self.first
        exchange = self.exchange([original], [self.replacement()])
        self.correct(exchange)
        for _ in range(4):
            outgoing, incoming = self.deposit(), self.replacement()
            operation = self.exchange([outgoing], [incoming])
            if _ % 2:
                self.handover(outgoing, operation)
        # Completed charges, corrected receipt and partial subsequent collection.
        with self.later(1, 1):
            receipt = self.pay("25000")
            self.correct(receipt)
            self.pay("75000")
        with self.later(12, 3):
            self.quote()
            for _ in range(40):
                khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
            for target in sizes:
                with workspace_context(self.workspace.pk):
                    existing = self.account.collateral.count()
                for n in range(existing, target):
                    item = self.deposit(description=f"Fictional benchmark item {n:04}",
                        storage_reference=f"Benchmark vault / bag {n:04}")
                    if n % 10 == 0:
                        self.photo(item)
                with workspace_context(self.workspace.pk):
                    scenario = dict(items=self.account.collateral.count(), operations=self.account.operations.count(),
                        photos=self.account.collateral.filter(photos__isnull=False).count(), accounts=41, reads={})
                before = self.balance()
                scenario["canonical_balances"] = {key: str(value) for key, value in before.items()}
                for tab in ("overview", "actions", "history", "interest", "collateral", "documents"):
                    scenario["reads"][tab] = self.profile("detail", dict(tab=tab))
                scenario["reads"]["picker"] = self.profile("picker", dict(mode="outgoing", format="json"))
                scenario["reads"]["photo_form"] = self.profile("photo", {})
                scenario["reads"]["register"] = self.profile("register", {})
                scenario["reads"]["register_filtered"] = self.profile("register", dict(q="KH00041"))
                assert self.balance() == before
                report["scenarios"].append(scenario)
                print(f"Measured {target} items / {scenario['operations']} operations.", flush=True)
            def reader(index):
                connections.close_all()
                try:
                    actor = [self.actor, *viewers][index]
                    start = time.perf_counter()
                    self.read("detail", dict(tab="history"), actor)
                    return round((time.perf_counter() - start) * 1000, 2)
                finally:
                    connections.close_all()
            start = time.perf_counter()
            with ThreadPoolExecutor(max_workers=4) as pool:
                report["concurrent_history_ms"] = list(pool.map(reader, range(4)))
            report["concurrent_wall_ms"] = round((time.perf_counter() - start) * 1000, 2)
        Path(args.output).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


runner = DiscoverRunner(keepdb=True, interactive=False, verbosity=1)
runner.setup_test_environment()
configuration = runner.setup_databases()
try:
    result = runner.run_suite(unittest.TestSuite([ReadBenchmark("test_reads")]))
finally:
    runner.teardown_databases(configuration)
    runner.teardown_test_environment()
raise SystemExit(not result.wasSuccessful())
