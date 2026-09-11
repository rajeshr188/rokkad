"""Synthetic queue baseline in Django's test database; no development rows modified."""
import os
import sys
import uuid
from pathlib import Path
from statistics import median
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DJANGO_SETTINGS_MODULE"] = "django_project.settings.test"

import django

django.setup()

from django.db import connection
from django.test import override_settings
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext
from apps.tenant_apps.loans.tests import test_pawn_draft_service as fixtures
from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work


class DashboardBenchmark(fixtures.PawnDraftServiceTests):
    def test_portfolios(self):
        self._economic_setup()
        role = connection.ops.quote_name("dashboard_bench_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
        storage = {"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}}
        with override_settings(STORAGES=storage):
            for count in range(1, 101):
                loan = fixtures.create_pawn_draft(self.command(), actor=self.actor)
                self._add_photo(loan)
                fixtures.approve_pawn_loan(loan.pk, actor=self.actor)
                fixtures.disburse_pawn_loan(loan.pk, effective_date=fixtures.date(2026, 7, 18), actor=self.actor)
                if count not in (1, 10, 50, 100):
                    continue
                for mode in ("owner", "restricted"):
                    samples = []
                    with connection.cursor() as cursor:
                        cursor.execute(f"SET LOCAL ROLE {role}" if mode == "restricted" else "RESET ROLE")
                    try:
                        for _ in range(3):
                            with CaptureQueriesContext(connection) as queries:
                                start = perf_counter()
                                work = get_workspace_counter_work(workspace=self.tenant, as_of_date=fixtures.date(2026, 10, 19))
                                samples.append((len(queries), (perf_counter()-start)*1000))
                            self.assertEqual(work["queues"]["overdue"]["count"], count)
                            self.assertEqual(samples[-1][0], 5)
                    finally:
                        with connection.cursor() as cursor:
                            cursor.execute("RESET ROLE")
                    print(f"BATCH role={mode} active={count} queries={samples[-1][0]} median_ms={median(t for _, t in samples):.1f}", flush=True)



if __name__ == "__main__":
    # Select only this method, not the inherited fixture's regression tests.
    sys.exit(bool(DiscoverRunner(interactive=False, keepdb=True).run_tests([
        "__main__.DashboardBenchmark.test_portfolios",
    ])))
