"""Opt-in 100-Workspace monitoring workload; never targets the development DB.

Example: python scripts/benchmark_monitoring_load.py --workspaces 100 --sizes 3000 10000
Use --workspaces 2 --sizes 25 --seconds 60 --workers 2 for driver verification.
Reports actual completion/deadline failure, not extrapolated capacity. Retains
only the dedicated disposable database for diagnosis; no operational worker runs.
"""
import argparse
import json
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from benchmark_monitoring_mixed import MixedMonitoringBenchmark, HISTORY_MODELS
from benchmark_monitoring import apps, connection, DiscoverRunner, override_settings
from monitoring_load_fixtures import copy_load_loans
from django.conf import settings
from django.db import connections
from django.utils import timezone
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import PawnLoan, LoanRiskSnapshot
from apps.tenant_apps.loans.services.risk_jobs import reassess_pawn_loans_pass
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio, get_risk_portfolio_summary, current_snapshot_filter
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.risk import get_pawn_loan_risk_assessment
from apps.tenant_apps.loans import services
from apps.tenant_apps.rates.models import Rate
from apps.orgs.models import Company

DB = "test_rokkad_monitoring_load"


@contextmanager
def keep_test_awake():
    """Prevent Windows idle sleep only for this process; preserve manual control."""
    if os.name != 'nt':
        yield
        return
    import ctypes
    api=ctypes.windll.kernel32.SetThreadExecutionState
    api.argtypes=[ctypes.c_uint32]
    api.restype=ctypes.c_uint32
    previous=api(0x80000001)  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED; display may sleep.
    if not previous:
        raise RuntimeError('Could not request temporary idle-sleep prevention for the load test.')
    try:
        yield
    finally:
        api(previous)


def seed_templates(workspace_id):
    seed_ids=list(PawnLoan.objects.filter(workspace_id=workspace_id).order_by('pk').values_list('pk',flat=True)[:6])
    if len(seed_ids)!=6:
        raise RuntimeError("Expected exactly six original seed profiles per Workspace.")
    result=[]
    for name in (*HISTORY_MODELS,'LoanRiskSnapshot'):
        model=apps.get_model('loans',name)
        if model is PawnLoan:
            lookup='pk__in'
        elif any(f.name=='loan' for f in model._meta.concrete_fields):
            lookup='loan_id__in'
        else:
            lookup='collateral_item__loan_id__in'
        result.append((model,list(model.objects.filter(workspace_id=workspace_id,**{lookup:seed_ids}).order_by('pk'))))
    return result


def expand_workspace(workspace_id,size):
    # Owner-backed disposable fixture construction, never an application worker.
    connections.close_all()
    settings.DATABASES['default']['NAME']=DB
    connection.settings_dict['NAME']=DB
    settings.DEBUG=False
    started=time.monotonic()
    try:
        templates=seed_templates(workspace_id)
        current=PawnLoan.objects.filter(workspace_id=workspace_id,state='ACTIVE').count()
        if current>size or (size-current)%5:
            raise RuntimeError('Existing fixture size cannot be resumed at this target.')
        # Bound deferred FK-check memory and preserve completed fixture chunks.
        # This is fixture setup; runtime still commits one assessed loan at a time.
        while current<size:
            increment=min(1000,size-current)
            with workspace_context(workspace_id):
                copy_load_loans(templates,increment//5)
            current+=increment
        with workspace_context(workspace_id):
            assert PawnLoan.objects.filter(workspace_id=workspace_id,state='ACTIVE').count()==size
            assert PawnLoan.objects.filter(workspace_id=workspace_id,state='CLOSED').count()==size//5
        return dict(workspace=workspace_id,active=size,seconds=time.monotonic()-started)
    finally:
        connections.close_all()


def emit(kind, **values):
    print(json.dumps(dict(kind=kind, at=timezone.now().isoformat(), **values), default=str), flush=True)


def runtime(role):
    connections.close_all()
    settings.DATABASES["default"]["NAME"] = DB
    connection.settings_dict["NAME"] = DB
    settings.DEBUG = False
    connection.force_debug_cursor = False
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database()")
        assert cursor.fetchone()[0] == DB
        cursor.execute(f"SET ROLE {connection.ops.quote_name(role)}")
        cursor.execute("SET statement_timeout = '60s'")
        cursor.execute("SET lock_timeout = '10s'")
        cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        assert cursor.fetchone() == (False, False)
    assert PawnLoan.objects.count() == 0


def worker(role, workspaces, deadline, stop, output):
    try:
        runtime(role)
        while not stop.is_set() and time.monotonic() < deadline:
            progress = 0
            for workspace in workspaces:
                if stop.is_set() or time.monotonic() >= deadline:
                    break
                started = time.monotonic()
                result = reassess_pawn_loans_pass(workspace_id=workspace["id"], as_of_date=timezone.localdate(), batch_size=50)
                output.put(dict(kind="batch", workspace=workspace["id"], seconds=time.monotonic()-started, **result))
                progress += result["current"]
            stop.wait(1 if progress else 5)
    except Exception as exc:
        output.put(dict(kind="worker_error", error=repr(exc)))
        stop.set()
    finally:
        connections.close_all()


def foreground(role, workspaces, deadline, stop, output):
    from django.contrib.auth import get_user_model
    from uuid import uuid4
    try:
        runtime(role)
        run_key=uuid4().hex
        iteration = 0
        while not stop.is_set() and time.monotonic() < deadline:
            workspace = workspaces[iteration % len(workspaces)]
            started = time.monotonic()
            with workspace_context(workspace["id"]):
                summary = get_risk_portfolio_summary()
                page = list(get_risk_portfolio())
                assert all(row.workspace_id == workspace["id"] for row in page)
                assert summary.loan_count == workspace["active"]
            output.put(dict(kind="foreground", operation="portfolio", seconds=time.monotonic()-started))
            # Two actual financial actions per iteration; only real seed evidence
            # is serviced. A reversal restores the fixture before its next turn.
            started = time.monotonic()
            with workspace_context(workspace["id"]):
                actor = get_user_model().objects.get(pk=workspace["actor"])
                payment = services.record_pawn_loan_repayment(workspace["loan"], amount="1",
                    request_key=f"load-{run_key}-{iteration}", actor=actor)
                services.reverse_pawn_loan_event(payment.loan_event.pk, reason="Load-test correction", actor=actor)
            output.put(dict(kind="foreground", operation="repayment_and_reversal", seconds=time.monotonic()-started))
            iteration += 1
            stop.wait(5)
    except Exception as exc:
        output.put(dict(kind="foreground_error", error=repr(exc)))
        stop.set()
    finally:
        connections.close_all()


def percentile(values, fraction):
    return sorted(values)[min(len(values)-1, int((len(values)-1)*fraction))] if values else None


def wave_counts(workspaces):
    """Observe successful use of this wave even after later date/source staleness."""
    values=', '.join(['(%s::bigint,%s::bigint,%s::timestamptz)']*len(workspaces))
    params=[value for w in workspaces for value in (w['id'],w['quote'],w['changed_at'])]
    with connection.cursor() as cursor:
        cursor.execute(f'''WITH targets(workspace_id,quote_id,changed_at) AS (VALUES {values})
            SELECT s.workspace_id,count(*) FROM loans_loanrisksnapshot s
            JOIN targets t ON t.workspace_id=s.workspace_id
            JOIN loans_pawnloan l ON l.id=s.loan_id AND l.workspace_id=s.workspace_id
            WHERE l.state='ACTIVE' AND s.assessed_at>=t.changed_at
            AND s.assessment_fingerprint<>''
            AND (s.source_provenance->'valuation_rate_ids') @> jsonb_build_array(t.quote_id)
            GROUP BY s.workspace_id''',params)
        return dict(cursor.fetchall())


def run_phase(workspaces, role, seconds, workers):
    from queue import Empty
    ctx = mp.get_context("spawn")
    stop, output = ctx.Event(), ctx.Queue()
    started = time.monotonic()
    deadline = started + seconds
    # Rates are Workspace-local, so publish one wave in each explicit scope.
    for workspace in workspaces:
        with workspace_context(workspace["id"]):
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {connection.ops.quote_name(role)}")
            last_price=Rate.objects.filter(rate_source_id=workspace['source'],metal=Rate.Metal.GOLD).order_by('-effective_at','-pk').values_list('buying_rate',flat=True).first()
            price=1400 if last_price==1500 else 1500
            quote = Rate.objects.create(rate_source_id=workspace["source"], buying_rate=price, selling_rate=price+10)
            workspace["quote"] = quote.pk
            assert LoanRiskSnapshot.objects.filter(current_snapshot_filter(timezone.localdate())).count() == 0
        workspace['changed_at']=timezone.now()
    emit("wave_published", workspaces=len(workspaces), active=sum(w["active"] for w in workspaces), seconds=time.monotonic()-started)
    processes = [ctx.Process(target=worker, args=(role, workspaces[i::workers], deadline, stop, output))
                 for i in range(min(workers, len(workspaces)))]
    processes.append(ctx.Process(target=foreground, args=(role, workspaces, deadline, stop, output)))
    for process in processes:
        process.start()
    totals, errors, latencies = {}, [], {}
    completed_at, last_report = {}, time.monotonic()-30
    uninterrupted=True
    try:
        while time.monotonic() < deadline and not stop.is_set():
            try:
                row = output.get(timeout=1)
                if row["kind"] == "batch":
                    totals[row["workspace"]] = totals.get(row["workspace"], 0) + row["current"]
                    errors.extend(row["errors"])
                elif row["kind"] == "foreground":
                    latencies.setdefault(row["operation"], []).append(row["seconds"])
                else:
                    errors.append(row)
                    stop.set()
            except Empty:
                pass
            for process in processes:
                if process.exitcode is not None and not stop.is_set():
                    errors.append({"process":process.pid,"error":"Load process exited before completion", "exitcode":process.exitcode})
                    stop.set()
            if time.monotonic() - last_report >= 30:
                gap=time.monotonic()-last_report
                if gap>120:
                    uninterrupted=False
                    errors.append(dict(error='Measurement gap invalidates continuous-load acceptance',seconds=gap))
                    stop.set()
                last_report = time.monotonic()
                # Owner connection observes aggregate progress only; all application
                # calculations and concurrent servicing execute with restricted RLS.
                counts = wave_counts(workspaces)
                for workspace in workspaces:
                    if counts.get(workspace["id"], 0) == workspace["active"] and time.monotonic()<=deadline:
                        completed_at.setdefault(workspace["id"], time.monotonic()-started)
                emit("progress", seconds=round(time.monotonic()-started, 2), wave_assessed=sum(counts.values()),
                     target=sum(w["active"] for w in workspaces), completed_workspaces=len(completed_at), errors=len(errors))
                if len(completed_at) == len(workspaces):
                    break
    finally:
        stop.set()
        for process in processes:
            process.join(timeout=65)
            if process.is_alive():
                process.terminate()
                process.join(timeout=10)
                errors.append({"process": process.pid, "error": "Worker exceeded shutdown grace"})
        while True:
            try:
                row = output.get_nowait()
                if row['kind']=='batch':
                    errors.extend(row['errors'])
                elif row['kind']=='foreground':
                    latencies.setdefault(row['operation'],[]).append(row['seconds'])
                elif row["kind"].endswith("error"):
                    errors.append(row)
            except Empty:
                break
    counts = {}
    final_wave_counts=wave_counts(workspaces)
    for workspace in workspaces:
        with workspace_context(workspace["id"]):
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {connection.ops.quote_name(role)}")
            counts[workspace["id"]] = LoanRiskSnapshot.objects.filter(current_snapshot_filter(timezone.localdate()), loan__state="ACTIVE").count()
            assert not LoanRiskSnapshot.objects.filter(loan__state="CLOSED").exists()
            assert not PawnLoan.objects.exclude(workspace_id=workspace["id"]).exists()
            for snapshot in LoanRiskSnapshot.objects.filter(current_snapshot_filter(timezone.localdate())).order_by("loan_id")[:5]:
                assert workspace["quote"] in snapshot.source_provenance["valuation_rate_ids"], "Current snapshot missed the new gold quote"
            # Compare refreshed copies against independent canonical reads. This
            # catches incorrect SQL fixture linkage, not just successful writes.
            for snapshot in LoanRiskSnapshot.objects.filter(current_snapshot_filter(timezone.localdate())).exclude(loan_id__in=workspace["seeds"]).order_by("loan_id")[:5]:
                exposure=get_pawn_loan_exposure(snapshot.loan_id,as_of_date=snapshot.as_of_date)
                risk=get_pawn_loan_risk_assessment(snapshot.loan_id,as_of_date=snapshot.as_of_date)
                assert (snapshot.exposure,snapshot.due,snapshot.overdue)==(exposure.total_economic_exposure,exposure.due_now.total,exposure.overdue.total)
                assert snapshot.assessment_fingerprint==risk.fingerprint
    result = dict(seconds=time.monotonic()-started, workspaces=len(workspaces), active=sum(w["active"] for w in workspaces),
        workers=workers, current=sum(counts.values()), wave_assessed=sum(final_wave_counts.values()), completed_workspaces=len(completed_at),
        per_workspace_current=counts, errors=errors[:20], error_count=len(errors),
        latency={name: dict(samples=len(values), p50=percentile(values,.5), p95=percentile(values,.95), p99=percentile(values,.99)) for name,values in latencies.items()},
        valid_continuous_run=uninterrupted,
        passed=len(completed_at)==len(workspaces) and not errors and uninterrupted,
        target_seconds=seconds)
    emit("phase_result", **result)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspaces", type=int, default=100)
    parser.add_argument("--sizes", type=int, nargs="+", default=[3000,10000])
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--reset", action="store_true", help="Clear only the dedicated disposable load-test database before seeding.")
    parser.add_argument("--resume", action="store_true", help="Resume interrupted first-size fixture construction in the dedicated database.")
    args=parser.parse_args()
    if args.reset and args.resume:
        parser.error("Choose reset or resume, not both.")
    if not 1 <= args.workspaces <= 100 or not 1 <= args.workers <= 16 or not 1 <= args.seconds <= 3600:
        parser.error("Use 1-100 Workspaces, 1-16 workers and 1-3600 seconds.")
    if args.sizes != sorted(set(args.sizes)) or any(n < 5 or n > 10000 or n % 5 for n in args.sizes):
        parser.error("Sizes must be increasing multiples of five, from 5 to 10000.")
    settings.DATABASES["default"]["NAME"] = "rokkad_monitoring_load"
    connection.settings_dict["NAME"] = "rokkad_monitoring_load"
    runner=DiscoverRunner(interactive=False, keepdb=True, verbosity=0)
    runner.setup_test_environment()
    # No serialized-rollback tests run here; never serialize the retained large
    # fixture database into Python memory during resume.
    runner.setup_databases(serialized_aliases=set())
    assert connection.settings_dict["NAME"] == DB
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), pg_try_advisory_lock(hashtext('rokkad-monitoring-load'))")
        database, acquired = cursor.fetchone()
        if database != DB or not acquired:
            raise RuntimeError("Load database identity mismatch or another load driver is running.")
    settings.DEBUG=False
    if args.reset:
        from django.core.management import call_command
        call_command("flush", interactive=False, verbosity=0)
    if PawnLoan.objects.exists() and not args.resume:
        raise RuntimeError("Load database already contains loans; preserve it for diagnosis or explicitly recreate it before rerunning.")
    role="monitoring_load_runtime"
    with connection.cursor() as cursor:
        cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
        cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
        cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
        cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
    workspaces=[]
    results=[]
    try:
        with override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.InMemoryStorage"}, "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            if args.resume:
                companies=list(Company.objects.filter(name__startswith='Mixed benchmark ').order_by('pk'))
                if len(companies)!=args.workspaces or Company.objects.count()!=args.workspaces:
                    raise RuntimeError('Resume requires the complete, exclusive set of benchmark Workspaces.')
            else:
                companies=[]
                for index in range(args.workspaces):
                    fixture=MixedMonitoringBenchmark("test_mixed_portfolios")
                    fixture.setUp()
                    with workspace_context(fixture.tenant.pk):
                        profiles=fixture.make_profiles()
                        for loan in profiles.values():
                            refresh_loan_risk_snapshot(loan.pk, as_of_date=fixture.today)
                    companies.append(fixture.tenant)
                    emit("workspace_seed", index=index+1, workspace=fixture.tenant.pk)
            for company in companies:
                seeds=list(PawnLoan.objects.filter(workspace=company).order_by('pk').values_list('pk',flat=True)[:6])
                source=apps.get_model('rates','RateSource').objects.get(workspace=company)
                workspaces.append(dict(id=company.pk,source=source.pk,actor=company.owner_id,loan=seeds[0],seeds=seeds))
            for size in args.sizes:
                with ProcessPoolExecutor(max_workers=args.workers,mp_context=mp.get_context('spawn')) as executor:
                    futures=[executor.submit(expand_workspace,workspace['id'],size) for workspace in workspaces]
                    for index,future in enumerate(as_completed(futures)):
                        emit('workspace_expanded',index=index+1,**future.result())
                for workspace in workspaces:
                    workspace['active']=size
                with connection.cursor() as cursor:
                    cursor.execute("ANALYZE")
                    cursor.execute("SELECT pg_database_size(current_database())")
                    emit("dataset_ready", database_bytes=cursor.fetchone()[0], active=size*args.workspaces)
                results.append(run_phase(workspaces,role,args.seconds,args.workers))
                if not results[-1]['valid_continuous_run']:
                    break
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {role}")
            cursor.execute(f"DROP ROLE {role}")
        connections.close_all()
    emit("run_result", phases=results, passed=all(result["passed"] for result in results))
    return 0 if all(result["passed"] for result in results) else 1


if __name__ == "__main__":
    with keep_test_awake():
        sys.exit(main())
