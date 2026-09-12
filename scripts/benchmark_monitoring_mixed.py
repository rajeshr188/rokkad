"""Mixed monitoring read workload; only disposable test data, no production SLA.

Five command-created active profiles and a released loan seed interleaved copies.
Copies exercise read cardinality and are never used as lifecycle/audit fixtures.
"""
import sys
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_monitoring import (
    apps, connection, copy_loans, Counter, DiscoverRunner, json, MODELS,
    MonitoringPortfolioTests, override_settings, PawnLoan, LoanRiskSnapshot,
    perf_counter, uuid, CaptureQueriesContext, get_risk_portfolio,
    get_risk_portfolio_summary, reassess_pawn_loans_batch,
)

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.services.risk_jobs import reassess_pawn_loans_pass
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans import services as svc
from apps.tenant_apps.loans.services.product_catalog import activate_product_version
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.rates.models import Rate


HISTORY_MODELS = (
    *MODELS, "PawnLoanInterestAccrual", "PawnLoanInterestAccrualLine",
    "PawnLoanRepaymentAllocationLine", "RepaymentScheduleChange", "ObligationAllocation",
    "PawnLoanRelease", "PawnLoanReleaseItem", "PawnLoanPrincipalClosingLine",
)


def measure(label, operation, **dimensions):
    connection.queries_log.clear()
    with CaptureQueriesContext(connection) as queries:
        start = perf_counter()
        result = operation()
        elapsed = perf_counter() - start
    assert len(queries) < 8900, "Query logging limit approached; reduce sample size."
    tables = Counter()
    for query in queries:
        if 'FROM "' in query["sql"]:
            tables[query["sql"].split('FROM "', 1)[1].split('"', 1)[0]] += 1
    print(json.dumps(dict(operation=label, seconds=round(elapsed, 4), queries=len(queries),
                         top_query_tables=tables.most_common(5), **dimensions)), flush=True)
    return result


def signature(snapshot):
    return tuple(getattr(snapshot, field) for field in (
        "exposure", "due", "overdue", "days_past_due", "collateral_value", "ltv_ratio",
        "performance_class", "severity", "flags", "assessment_fingerprint",
    ))


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MixedMonitoringBenchmark(TransactionTestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="mixed-benchmark-" + uuid.uuid4().hex)
        self.tenant = Company.objects.create(name="Mixed benchmark " + uuid.uuid4().hex, schema_name="mixed-" + uuid.uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            fixtures.CollateralReappraisalTests.make_loan(self)

    def test_mixed_portfolios(self):
        with workspace_context(self.tenant.pk):
            self.run_scoped_benchmarks()
        role = connection.ops.quote_name("committed_bench_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET ROLE {role}")
        try:
            result = measure("committed_worker50", lambda: reassess_pawn_loans_pass(
                workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=50), active=10000)
            self.assertEqual(result["current"], 50, result)
            self.assertFalse(connection.in_atomic_block)
            self.assertEqual(PawnLoan.objects.count(), 0)
            with workspace_context(self.tenant.pk):
                for row in LoanRiskSnapshot.objects.filter(status="CURRENT"):
                    self.assertEqual(signature(row), self.references[self.identities[row.loan_id]])
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def make_profile(self, code, age, metals, history=False, closed=False):
        loan_date = self.today - timedelta(days=age)
        product = m.LoanProductVersion.objects.get(workspace=self.tenant, product__code=code)
        activate_product_version(product.pk, actor=self.actor)
        collateral = tuple(svc.CollateralDraftInput(description=f"{metal} item", metal=metal,
            gross_weight=Decimal("1" if metal == "GOLD" else "25"),
            net_weight=Decimal("1" if metal == "GOLD" else "25"), purity_percentage=Decimal("100"),
            latest_appraised_value=Decimal("2000"), allocated_principal=Decimal(1000 // len(metals)))
            for metal in metals)
        loan = svc.create_pawn_draft(svc.CreatePawnDraftCommand(workspace_id=self.tenant.pk,
            borrower_id=self.loan.borrower_id, license_id=self.license.pk, series_id=self.series.pk,
            product_version_id=product.pk, principal_amount=Decimal("1000"),
            monthly_interest_rate=Decimal("2"), loan_date=loan_date, tenure_months=12,
            collateral=collateral), actor=self.actor)
        for item in loan.collateral_items.all():
            svc.append_collateral_photo(item.pk, upload=SimpleUploadedFile("bench.jpg", b"\xff\xd8\xff\xe0synthetic", content_type="image/jpeg"), actor=self.actor)
        svc.approve_pawn_loan(loan.pk, actor=self.actor)
        svc.disburse_pawn_loan(loan.pk, effective_date=loan_date, actor=self.actor)
        if history:
            for index, days in enumerate((age * 3 // 4, age // 2, age // 4)):
                with patch("apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate", return_value=self.today - timedelta(days=days)):
                    payment = svc.record_pawn_loan_repayment(loan.pk, amount="100", request_key=f"profile-{index}", actor=self.actor)
            svc.reverse_pawn_loan_event(payment.loan_event.pk, reason="Synthetic repayment correction", actor=self.actor)
        if closed:
            quote = svc.preview_pawn_loan_full_release(loan.pk)
            svc.release_pawn_loan_in_full(loan.pk, settlement_amount=quote.minimum_settlement,
                                         request_key="closed-profile", actor=self.actor)
        loan.refresh_from_db()
        return loan

    def make_profiles(self):
        oldest = self.today - timedelta(days=600)
        self.license = m.LoanLicense.objects.create(workspace=self.tenant, name="Benchmark",
            license_number=uuid.uuid4().hex, issued_on=oldest, expires_on=self.today + timedelta(days=365))
        self.series = m.LoanSeries.objects.create(license=self.license, name="Benchmark", code="BENCH")
        for kind in ("PAWN_LOAN", "PAWN_LOAN_RELEASE"):
            m.LoanNumberSequence.objects.create(series=self.series, document_kind=kind, prefix=kind, width=5, maximum_number=10000)
        svc.create_pawn_loan_economic_policy(workspace=self.tenant, license=self.license,
            valuation_method="LOWER_OF_CALCULATED_AND_APPRAISAL", maximum_ltv_ratio=Decimal("0.8"),
            advance_interest_periods=0, effective_from=oldest, actor=self.actor)
        for metal, rate_metal, price in (("GOLD", Rate.Metal.GOLD, 3000), ("SILVER", Rate.Metal.SILVER, 100)):
            svc.create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=self.license,
                metal=metal, monthly_interest_rate=Decimal("2"), effective_from=oldest, actor=self.actor)
            Rate.objects.create(rate_source=self.source, metal=rate_metal, buying_rate=price,
                selling_rate=price + 10, effective_at=timezone.now() - timedelta(days=600))
            Rate.objects.create(rate_source=self.source, metal=rate_metal, buying_rate=price, selling_rate=price + 10)
        profiles = {
            "bullet100": self.loan,
            "bullet7": self.make_profile("GOLD-BULLET", 7, ("GOLD",)),
            "periodic180": self.make_profile("GOLD-INTEREST-BULLET", 180, ("GOLD", "SILVER"), history=True),
            "flex400": self.make_profile("GOLD-FLEXIBLE", 400, ("GOLD", "SILVER", "GOLD", "SILVER"), history=True),
            "emi180": self.make_profile("GOLD-INSTALLMENT-EMI", 180, ("GOLD",), history=True),
        }
        self.make_profile("GOLD-BULLET", 7, ("SILVER",), closed=True)
        return profiles

    def run_scoped_benchmarks(self):
        self.assertEqual(connection.settings_dict["NAME"], "test_rokkad_monitor_benchmark")
        profiles = self.make_profiles()
        templates = [(apps.get_model("loans", name), list(apps.get_model("loans", name).objects.filter(workspace=self.tenant).order_by("pk"))) for name in HISTORY_MODELS]
        role = connection.ops.quote_name("mixed_bench_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        references, identities = {}, {loan.pk: name for name, loan in profiles.items()}
        self.references, self.identities = references, identities
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
                cursor.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                self.assertEqual(cursor.fetchone(), (False, False))
            for name, loan in profiles.items():
                references[name] = signature(measure("profile", lambda: refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today), profile=name))
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
            for size in (3000, 10000):
                mapping = measure("seed", lambda: copy_loans(templates, (size - PawnLoan.objects.filter(state="ACTIVE").count()) // 5), active=size)
                for name, loan in profiles.items():
                    identities.update((pk, name) for pk in mapping[("PawnLoan", loan.pk)])
                with connection.cursor() as cursor:
                    for model, _ in templates:
                        cursor.execute(f"ANALYZE {connection.ops.quote_name(model._meta.db_table)}")
                    cursor.execute(f"SET LOCAL ROLE {role}")
                try:
                    summary = measure("portfolio_summary", lambda: get_risk_portfolio_summary(as_of_date=self.today), active=size)
                    self.assertEqual(summary.loan_count, size)
                    self.assertEqual(PawnLoan.objects.filter(state="CLOSED").count(), size // 5)
                    measure("portfolio_page", lambda: list(get_risk_portfolio(as_of_date=self.today)), active=size)
                    measure("loan_detail_exposure", lambda: get_pawn_loan_exposure(profiles["flex400"].pk, as_of_date=self.today), active=size)
                    result = measure("refresh50", lambda: reassess_pawn_loans_batch(workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=50), active=size)
                    self.assertEqual(result["current"], 50, result)
                    for row in LoanRiskSnapshot.objects.all():
                        self.assertEqual(signature(row), references[identities[row.loan_id]])
                    # Populate remaining projections from their authoritative profile
                    # to measure the fan-out of quote invalidation at full cardinality.
                    measured = set(LoanRiskSnapshot.objects.values_list("loan_id", flat=True))
                    seed_snapshots = {name: LoanRiskSnapshot.objects.get(loan=loan) for name, loan in profiles.items()}
                    pending = []
                    for pk, name in identities.items():
                        if pk not in measured:
                            row = seed_snapshots[name]
                            values = {field.attname: getattr(row, field.attname) for field in row._meta.concrete_fields if not field.primary_key}
                            values["loan_id"] = pk
                            pending.append(LoanRiskSnapshot(**values))
                    LoanRiskSnapshot.objects.bulk_create(pending, batch_size=500)
                    measure("gold_quote_invalidation", lambda: Rate.objects.create(rate_source=self.source, buying_rate=3000, selling_rate=3010), active=size)
                    self.assertEqual(LoanRiskSnapshot.objects.filter(status="STALE").count(), size)
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
        "__main__.MixedMonitoringBenchmark.test_mixed_portfolios",
    ])))
