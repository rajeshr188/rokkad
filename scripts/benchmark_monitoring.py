"""Synthetic monitoring baseline in a disposable Django test database.

Replicates a real command-created loan's read evidence. This is a homogeneous
query/throughput baseline, not representative production or multi-tenant load
acceptance. Never use these synthetic copies for workflow correctness tests.
"""
import copy
import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["DJANGO_SETTINGS_MODULE"] = "django_project.settings.test"
os.environ["DB_MIGRATION_NAME"] = "rokkad_monitor_benchmark"

import django
django.setup()

from django.apps import apps
from django.db import connection, transaction
from django.test import override_settings
from django.test.runner import DiscoverRunner
from django.test.utils import CaptureQueriesContext
from apps.tenant_apps.loans.models import PawnLoan, LoanRiskSnapshot
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary, get_risk_portfolio
from apps.tenant_apps.loans.services.risk_snapshots import reassess_pawn_loans_batch
from apps.tenant_apps.loans.tests.test_monitoring_completeness import MonitoringPortfolioTests


MODELS = (
    "PawnLoan", "PawnCollateralItem", "LoanPolicySnapshot", "PawnLoanApprovalSnapshot",
    "PawnLoanEvent", "PawnLoanDisbursalSnapshot", "RepaymentScheduleVersion",
    "RepaymentObligation", "CollateralAppraisal",
)
JSON_IDENTITIES = {
    "loan_id": "PawnLoan", "collateral_item_id": "PawnCollateralItem",
    "policy_snapshot_id": "LoanPolicySnapshot", "approval_snapshot_id": "PawnLoanApprovalSnapshot",
    "loan_event_id": "PawnLoanEvent", "source_event_id": "PawnLoanEvent",
    "schedule_version_id": "RepaymentScheduleVersion",
}


def remap_json(value, mapping, index):
    if isinstance(value, list):
        return [remap_json(row, mapping, index) for row in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        model = JSON_IDENTITIES.get(key)
        if model and (model, item) in mapping:
            result[key] = mapping[(model, item)][index]
        else:
            result[key] = remap_json(item, mapping, index)
    return result


@transaction.atomic
def copy_loans(templates, count):
    mapping = {}
    for model, rows in templates:
        with connection.cursor() as cursor:
            cursor.execute("SELECT nextval(pg_get_serial_sequence(%s, 'id')) FROM generate_series(1, %s)",
                           [model._meta.db_table, count * len(rows)])
            ids = [value[0] for value in cursor.fetchall()]
        for offset, row in enumerate(rows):
            # Interleave profiles so each bounded batch samples the full mix.
            mapping[(model.__name__, row.pk)] = ids[offset::len(rows)]
    for model, rows in templates:
        for row in rows:
            copies = []
            for index in range(count):
                values = {}
                for field in model._meta.concrete_fields:
                    value = copy.deepcopy(getattr(row, field.attname))
                    if field.primary_key:
                        value = mapping[(model.__name__, row.pk)][index]
                    elif field.is_relation and (field.related_model.__name__, value) in mapping:
                        value = mapping[(field.related_model.__name__, value)][index]
                    elif field.get_internal_type() == "JSONField":
                        value = remap_json(value, mapping, index)
                    elif field.name == "public_id":
                        value = uuid.uuid4()
                    elif field.name in ("loan_number", "idempotency_key", "release_number"):
                        value = f"bench-{uuid.uuid4().hex}"
                    values[field.attname] = value
                copies.append(model(**values))
            model.objects.bulk_create(copies, batch_size=500)
    return mapping


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringBenchmark(MonitoringPortfolioTests):
    def test_capacity_baseline(self):
        self.assertTrue(connection.settings_dict["NAME"].startswith("test_rokkad_monitor_benchmark"))
        templates = [(apps.get_model("loans", name), list(apps.get_model("loans", name).objects.filter(workspace=self.tenant))) for name in MODELS]
        reference = self.refresh()
        role = connection.ops.quote_name("monitor_bench_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            for size in (3000, 10000):
                start = perf_counter()
                copy_loans(templates, size - PawnLoan.objects.count())
                with connection.cursor() as cursor:
                    for model, _ in templates:
                        cursor.execute(f"ANALYZE {connection.ops.quote_name(model._meta.db_table)}")
                    cursor.execute(f"SET LOCAL ROLE {role}")
                    cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
                    self.assertEqual(cursor.fetchone(), (False, False))
                print(json.dumps({"active": size, "seed_seconds": round(perf_counter()-start, 3)}), flush=True)
                try:
                    connection.queries_log.clear()
                    with CaptureQueriesContext(connection) as queries:
                        start = perf_counter()
                        summary = get_risk_portfolio_summary(as_of_date=self.today)
                        list(get_risk_portfolio(as_of_date=self.today))
                        elapsed = perf_counter()-start
                    self.assertEqual(summary.loan_count, size)
                    print(json.dumps({"active": size, "operation": "portfolio", "queries": len(queries), "seconds": round(elapsed, 3)}), flush=True)
                    connection.queries_log.clear()
                    with CaptureQueriesContext(connection) as queries:
                        start = perf_counter()
                        result = reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=50)
                        elapsed = perf_counter()-start
                    self.assertEqual(result["current"], 50, result)
                    samples = LoanRiskSnapshot.objects.filter(loan_id__in=PawnLoan.objects.exclude(pk=self.loan.pk).values("pk"), status="CURRENT")
                    for sample in samples:
                        self.assertEqual((sample.exposure, sample.overdue, sample.days_past_due, sample.collateral_value, sample.flags),
                                         (reference.exposure, reference.overdue, reference.days_past_due, reference.collateral_value, reference.flags))
                    tables = Counter()
                    for query in queries:
                        sql = query["sql"]
                        if 'FROM "' in sql:
                            tables[sql.split('FROM "', 1)[1].split('"', 1)[0]] += 1
                    print(json.dumps({"active": size, "operation": "refresh50", "queries": len(queries),
                        "seconds": round(elapsed, 3), "loans_per_second": round(50/elapsed, 2), "top_query_tables": tables.most_common(8)}), flush=True)
                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("RESET ROLE")
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


if __name__ == "__main__":
    sys.exit(bool(DiscoverRunner(interactive=False, keepdb=True).run_tests([
        "__main__.MonitoringBenchmark.test_capacity_baseline",
    ])))
