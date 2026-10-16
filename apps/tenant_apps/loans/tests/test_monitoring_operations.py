"""Local PostgreSQL characterization; timings are observations, never SLO gates.

Set ROKKAD_MONITORING_MEASURE=1 to print aggregate synthetic measurements.
Only run with Django's isolated test database, not against operational data.
"""
import json
import os
import uuid
from importlib import import_module
from concurrent.futures import ThreadPoolExecutor
from statistics import median
from threading import Event
from time import perf_counter
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import DatabaseError, connection, connections, transaction
from django.forms.models import model_to_dict
from django.test import TransactionTestCase, override_settings

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import LoanRiskSnapshot, PawnCollateralItem, PawnLoan
from apps.tenant_apps.loans.services import risk_snapshots
from apps.tenant_apps.loans.services import record_pawn_loan_repayment, reverse_pawn_loan_event
from apps.tenant_apps.loans.services.risk_jobs import reassess_pawn_loans_pass
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from apps.tenant_apps.loans.web.economic_forms import LoanMonitoringPolicyForm
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.rates.models import Rate


def report(case, **values):
    if os.environ.get("ROKKAD_MONITORING_MEASURE") == "1":
        print("LS06 " + json.dumps(dict(case=case, **values), sort_keys=True), flush=True)


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class MonitoringOperationsTests(TransactionTestCase):
    def setUp(self):
        suffix = uuid.uuid4().hex
        self.actor = get_user_model().objects.create_user(username="monitor-ops-" + suffix)
        self.tenant = Company.objects.create(name=suffix, schema_name=suffix,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant,
            role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            fixtures.CollateralReappraisalTests.make_loan(self, method="LATEST_APPRAISAL")
        self.role = connection.ops.quote_name("monitor_ops_" + suffix)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {self.role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {self.role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {self.role}")
        self.addCleanup(self.drop_role)

    def drop_role(self):
        with connection.cursor() as cursor:
            cursor.execute(f"DROP OWNED BY {self.role}")
            cursor.execute(f"DROP ROLE {self.role}")

    def restrict(self):
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {self.role}")
            cursor.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
            self.assertEqual(cursor.fetchone(), (False, False))

    def add_invalidation_rows(self, count):
        # Deliberately minimal synthetic source/projection rows, NOT admitted
        # financial loans. Used only to measure fan-out, never to assess debt.
        rows = PawnLoan.objects.bulk_create([
            PawnLoan(workspace=self.tenant, license=self.loan.license,
                series=self.loan.series, borrower=self.loan.borrower,
                product_version=self.loan.product_version, state="ACTIVE",
                loan_number="MEASURE-" + uuid.uuid4().hex, principal_amount=1000,
                monthly_interest_rate=2) for _ in range(count)
        ])
        PawnCollateralItem.objects.bulk_create([
            PawnCollateralItem(workspace=self.tenant, loan=row, description="Synthetic gold",
                metal="GOLD", gross_weight=1, net_weight=1, purity_percentage=100,
                allocated_principal=1000) for row in rows
        ])
        LoanRiskSnapshot.objects.bulk_create([
            LoanRiskSnapshot(workspace=self.tenant, loan=row, as_of_date=self.today,
                status="CURRENT", assessment_fingerprint="synthetic-only") for row in rows
        ])
        return rows

    def test_rate_invalidation_fanout_and_repeated_stale_updates(self):
        with workspace_context(self.tenant.pk):
            self.restrict()
            # Include a genuine assessed loan; it must also be invalidated.
            snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            previous = 1
            # Keep routine regression small; the explicit measurement run also
            # exercises the largest bounded cohort.
            sizes = (1, 100, 2500) if os.environ.get("ROKKAD_MONITORING_MEASURE") == "1" else (1, 100)
            for size in sizes:
                self.add_invalidation_rows(size - previous)
                previous = size
                samples, repeat_samples = [], []
                for _ in range(5):
                    LoanRiskSnapshot.objects.update(status="CURRENT")
                    for target in (samples, repeat_samples):
                        updates = []
                        def observe(execute, sql, params, many, context):
                            started = perf_counter()
                            result = execute(sql, params, many, context)
                            if sql.lstrip().startswith('UPDATE "loans_loanrisksnapshot"'):
                                updates.append((context["cursor"].rowcount,
                                    (perf_counter() - started) * 1000))
                            return result
                        with connection.execute_wrapper(observe):
                            Rate.objects.create(rate_source=self.source,
                                buying_rate=3200, selling_rate=3300)
                        self.assertEqual(len(updates), 1)
                        self.assertEqual(updates[0][0], size)
                        target.append(updates[0][1])
                        self.assertEqual(LoanRiskSnapshot.objects.filter(status="STALE").count(), size)
                report("rate_invalidation", rows=size, samples=5,
                    current_median_ms=round(median(samples), 3), current_max_ms=round(max(samples), 3),
                    already_stale_median_ms=round(median(repeat_samples), 3),
                    updates_per_source_save=1, rewritten_rows_per_source_save=size)
            snapshot.refresh_from_db()
            self.assertEqual(snapshot.status, "STALE")

    def test_worker_natural_claim_duration_and_query_count(self):
        samples, holds, counts = [], [], []
        for _ in range(5):
            with workspace_context(self.tenant.pk):
                LoanRiskSnapshot.objects.filter(loan=self.loan).update(status="STALE")
            claimed, queries = [], []
            def observe(execute, sql, params, many, context):
                result = execute(sql, params, many, context)
                queries.append(None)
                if "SKIP LOCKED" in sql:
                    claimed.append(perf_counter())
                return result
            # SET ROLE applies to both the candidate-selection and claim contexts.
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {self.role}")
            try:
                start = perf_counter()
                with connection.execute_wrapper(observe):
                    result = reassess_pawn_loans_pass(workspace_id=self.tenant.pk,
                        as_of_date=self.today, batch_size=1)
                finish = perf_counter()
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
            self.assertEqual(result, {"selected": 1, "current": 1, "errors": []})
            self.assertEqual(len(claimed), 1)
            samples.append((finish - start) * 1000)
            holds.append((finish - claimed[0]) * 1000)
            counts.append(len(queries))
        report("worker_single_item", samples=5, pass_median_ms=round(median(samples), 3),
            claim_to_return_median_ms=round(median(holds), 3),
            claim_to_return_max_ms=round(max(holds), 3), query_counts=counts)

    def test_real_receipt_and_reversal_invalidate_without_monitoring_postings(self):
        with workspace_context(self.tenant.pk):
            self.restrict()
            snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        payment = None
        for action in ("receipt", "reversal"):
            with workspace_context(self.tenant.pk):
                self.restrict()
                before_refresh = self.loan.loan_events.count()
                risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
                self.assertEqual(self.loan.loan_events.count(), before_refresh)
                event_count = self.loan.loan_events.count()
            updates = []
            def observe(execute, sql, params, many, context):
                start = perf_counter()
                result = execute(sql, params, many, context)
                if sql.lstrip().startswith('UPDATE "loans_loanrisksnapshot"'):
                    updates.append((context["cursor"].rowcount, (perf_counter() - start) * 1000))
                return result
            start = perf_counter()
            with connection.execute_wrapper(observe), workspace_context(self.tenant.pk):
                self.restrict()
                if action == "receipt":
                    payment = record_pawn_loan_repayment(self.loan.pk, amount="100",
                        request_key="measurement-receipt", actor=self.actor)
                else:
                    reverse_pawn_loan_event(payment.loan_event.pk,
                        reason="Synthetic measurement reversal", actor=self.actor)
                snapshot.refresh_from_db()
                self.assertEqual(snapshot.status, "STALE")
                if action == "receipt":
                    # Ordinary servicing also recognizes eligible completed
                    # monthly charges; monitoring itself recognized none.
                    self.assertTrue(self.loan.loan_events.filter(pk=payment.loan_event.pk).exists())
                    self.assertGreater(self.loan.loan_events.count(), event_count)
                else:
                    self.assertEqual(self.loan.loan_events.count(), event_count + 1)
            elapsed = (perf_counter() - start) * 1000
            self.assertTrue(updates)
            self.assertTrue(all(rows == 1 for rows, _ in updates))
            report(action, invalidation_statements=len(updates),
                invalidation_total_ms=round(sum(ms for _, ms in updates), 3),
                operation_with_assertions_commit_ms=round(elapsed, 3))

    def test_claim_blocks_same_loan_but_not_other_loan_or_competing_worker(self):
        with workspace_context(self.tenant.pk):
            other = self.add_invalidation_rows(1)[0]
        claimed, release, waiter_ready = Event(), Event(), Event()
        worker_pid = []
        real_inputs = risk_snapshots.get_pawn_loan_financial_inputs

        def paused(*args, **kwargs):
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                worker_pid.append(cursor.fetchone()[0])
            claimed.set()
            if not release.wait(15):
                raise AssertionError("Characterization release was not signalled")
            return real_inputs(*args, **kwargs)

        def worker():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                return reassess_pawn_loans_pass(workspace_id=self.tenant.pk,
                    as_of_date=self.today, batch_size=1)
            finally:
                connections.close_all()

        def waiter():
            try:
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '10s'")
                    start = perf_counter()
                    waiter_ready.set()
                    PawnLoan.objects.select_for_update().get(pk=self.loan.pk)
                    return (perf_counter() - start) * 1000
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool, patch.object(
            risk_snapshots, "get_pawn_loan_financial_inputs", side_effect=paused
        ):
            refresh = pool.submit(worker)
            try:
                self.assertTrue(claimed.wait(10))
                blocked = pool.submit(waiter)
                self.assertTrue(waiter_ready.wait(10))
                # Verify actual PostgreSQL blocking, not a sleep-based timing guess.
                deadline = perf_counter() + 5
                observed = False
                while perf_counter() < deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                            "WHERE %s = ANY(pg_blocking_pids(pid)))", [worker_pid[0]])
                        observed = cursor.fetchone()[0]
                    if observed:
                        break
                    Event().wait(0.01)
                self.assertTrue(observed)
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    PawnLoan.objects.select_for_update(nowait=True).get(pk=other.pk)
                    competitor = risk_snapshots.reassess_pawn_loans_batch(
                        workspace_id=self.tenant.pk, as_of_date=self.today,
                        batch_size=1, loan_ids=(self.loan.pk,))
                    self.assertEqual(competitor["selected"], 0)
            finally:
                release.set()
            self.assertEqual(refresh.result(timeout=15)["current"], 1)
            wait_ms = blocked.result(timeout=15)
        report("controlled_contention", same_loan_block_observed=True,
            unrelated_loan_nowait_succeeded=True, competitor_selected=0,
            deliberately_paused_wait_ms=round(wait_ms, 3))

    def test_source_and_invalidation_rollback_together_and_failure_is_not_swallowed(self):
        with workspace_context(self.tenant.pk):
            self.restrict()
            snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            before = Rate.objects.count()
            with self.assertRaisesMessage(ValueError, "abort source"), transaction.atomic():
                Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
                self.assertEqual(LoanRiskSnapshot.objects.get(pk=snapshot.pk).status, "STALE")
                raise ValueError("abort source")
            self.assertEqual(Rate.objects.count(), before)
            self.assertEqual(LoanRiskSnapshot.objects.get(pk=snapshot.pk).status, "CURRENT")

            def reject(execute, sql, params, many, context):
                if sql.lstrip().startswith('UPDATE "loans_loanrisksnapshot"'):
                    raise DatabaseError("Synthetic projection unavailability")
                return execute(sql, params, many, context)
            with self.assertRaisesMessage(DatabaseError, "projection unavailability"), transaction.atomic():
                with connection.execute_wrapper(reject):
                    Rate.objects.create(rate_source=self.source, buying_rate=3400, selling_rate=3500)
            self.assertEqual(Rate.objects.count(), before)
            self.assertEqual(LoanRiskSnapshot.objects.get(pk=snapshot.pk).status, "CURRENT")

    def test_committed_rate_during_worker_calculation_cannot_publish_current(self):
        with workspace_context(self.tenant.pk):
            self.restrict()
            snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            LoanRiskSnapshot.objects.filter(pk=snapshot.pk).update(status="STALE")
            before_events = self.loan.risk_events.count()
        entered, release = Event(), Event()
        real_inputs = risk_snapshots.get_pawn_loan_financial_inputs

        def paused(*args, **kwargs):
            entered.set()
            if not release.wait(15):
                raise AssertionError("Rate-race release was not signalled")
            return real_inputs(*args, **kwargs)

        def worker():
            try:
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    return risk_snapshots.reassess_pawn_loans_batch(
                        workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=1) as pool, patch.object(
            risk_snapshots, "get_pawn_loan_financial_inputs", side_effect=paused
        ):
            future = pool.submit(worker)
            try:
                self.assertTrue(entered.wait(10))
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    Rate.objects.create(rate_source=self.source, buying_rate=3200, selling_rate=3300)
            finally:
                release.set()
            result = future.result(timeout=15)
        self.assertEqual(result["current"], 0)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("Source evidence changed", result["errors"][0]["error"])
        with workspace_context(self.tenant.pk):
            self.restrict()
            self.assertEqual(LoanRiskSnapshot.objects.get(pk=snapshot.pk).status, "STALE")
            self.assertEqual(self.loan.risk_events.count(), before_events)

    def test_stale_scope_lock_fences_rate_and_policy_after_final_fingerprint(self):
        for source in ("rate", "policy"):
            with self.subTest(source=source):
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
                    LoanRiskSnapshot.objects.filter(pk=snapshot.pk).update(status="STALE")
                entered, release, writer_ready = Event(), Event(), Event()
                worker_pid = []
                real_values = risk_snapshots._snapshot_values

                def paused(**kwargs):
                    # The snapshot is still STALE and locked; the final source
                    # fingerprint has already been checked. A CURRENT-only
                    # invalidation filter without this lock fence is unsafe.
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT pg_backend_pid()")
                        worker_pid.append(cursor.fetchone()[0])
                    entered.set()
                    if not release.wait(15):
                        raise AssertionError("Late-race release was not signalled")
                    return real_values(**kwargs)

                def worker():
                    try:
                        with workspace_context(self.tenant.pk):
                            self.restrict()
                            return risk_snapshots.reassess_pawn_loans_batch(
                                workspace_id=self.tenant.pk, as_of_date=self.today, batch_size=1)
                    finally:
                        connections.close_all()

                def writer():
                    try:
                        with workspace_context(self.tenant.pk):
                            self.restrict()
                            with connection.cursor() as cursor:
                                cursor.execute("SET LOCAL lock_timeout = '10s'")
                            writer_ready.set()
                            if source == "rate":
                                Rate.objects.create(rate_source=self.source, buying_rate=3400, selling_rate=3500)
                            else:
                                values = model_to_dict(self.policy, fields=LoanMonitoringPolicyForm.Meta.fields)
                                values.update(license=None, supersedes=self.policy, effective_from=self.today,
                                    amendment_reason="Synthetic late amendment", rate_freshness_days=8)
                                create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **values)
                    finally:
                        connections.close_all()

                with ThreadPoolExecutor(max_workers=2) as pool, patch.object(
                    risk_snapshots, "_snapshot_values", side_effect=paused
                ):
                    refresh = pool.submit(worker)
                    try:
                        self.assertTrue(entered.wait(10))
                        mutation = pool.submit(writer)
                        self.assertTrue(writer_ready.wait(10))
                        deadline, observed = perf_counter() + 5, False
                        while perf_counter() < deadline:
                            with connection.cursor() as cursor:
                                cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                                    "WHERE %s = ANY(pg_blocking_pids(pid)))", [worker_pid[0]])
                                observed = cursor.fetchone()[0]
                            if observed:
                                break
                            Event().wait(0.01)
                        self.assertTrue(observed)
                    finally:
                        release.set()
                    self.assertEqual(refresh.result(timeout=15)["current"], 1)
                    mutation.result(timeout=15)
                with workspace_context(self.tenant.pk):
                    self.restrict()
                    self.assertEqual(LoanRiskSnapshot.objects.get(pk=snapshot.pk).status, "STALE")

    def test_policy_guard_upgrade_is_reversible_and_preserves_populated_evidence(self):
        migration = import_module("apps.tenant_apps.loans.migrations.0086_monitoring_policy_lock_mode")
        with workspace_context(self.tenant.pk):
            snapshot = risk_snapshots.refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
            policy_before = model_to_dict(self.policy)
            snapshot_before = model_to_dict(snapshot)
            events_before = list(self.loan.risk_events.values())
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_get_functiondef('loans_guard_monitoring_policy()'::regprocedure)")
            installed = cursor.fetchone()[0]
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(migration.PREVIOUS)
                cursor.execute("SELECT pg_get_functiondef('loans_guard_monitoring_policy()'::regprocedure)")
                previous = cursor.fetchone()[0]
                self.assertIn("FOR UPDATE;", previous)
                cursor.execute(migration.CURRENT)
                cursor.execute("SELECT pg_get_functiondef('loans_guard_monitoring_policy()'::regprocedure)")
                current = cursor.fetchone()[0]
                self.assertEqual(current.replace("FOR NO KEY UPDATE;", "FOR UPDATE;"), previous)
        finally:
            # Later migrations can extend this function. Never leave a historical
            # guard installed for the remaining database/concurrency tests.
            with connection.cursor() as cursor:
                cursor.execute(installed)
        with workspace_context(self.tenant.pk):
            self.policy.refresh_from_db()
            snapshot.refresh_from_db()
            self.assertEqual(model_to_dict(self.policy), policy_before)
            self.assertEqual(model_to_dict(snapshot), snapshot_before)
            self.assertEqual(list(self.loan.risk_events.values()), events_before)
