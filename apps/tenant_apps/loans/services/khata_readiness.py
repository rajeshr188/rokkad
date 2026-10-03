"""Read-only software evidence for a separately approved, named khata pilot."""
import hashlib

from django.db import connection
from django.core.exceptions import ValidationError
from django.db.migrations.recorder import MigrationRecorder
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.services.storage_references import validate_coverage
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataSeries
from apps.tenant_apps.loans.selectors.khata_summary import portfolio_summary
from .action_access import require_workspace_action
from .khata_accounts import _series_ready
from .khata_recovery import export_archive, _models, _read


MANUAL_GATES = (
    "Accept the named Workspace, independent/associated series and authorized operators.",
    "Approve the supported scope, refused correction kinds and statutory/default boundary.",
    "Retain verified full database/private-media backups and independent checksums off the candidate.",
    "Rehearse exact-identity restore on a matching disposable recovery database.",
    "Print 100 x 60 mm labels at actual size and scan item/account QR codes from paper.",
    "Verify the candidate build, owner-only migration plan and restricted web/worker connections.",
    "Approve monitoring, support handling and compatible forward-fix/rollback procedures.",
)


def assess_readiness(*, workspace, actor):
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.export")
        resolve_workspace_access(actor=actor, workspace=workspace).require("workspace.settings.manage")
        checks = []

        def check(code, passed, detail):
            checks.append(dict(code=code, passed=bool(passed), detail=detail))

        applied = MigrationRecorder(connection).applied_migrations()
        check("MIGRATION", ("loans", "0040_khata_labels") in applied, "Loans 0040 label guards must be applied by the owner connection.")
        tables = [m._meta.db_table for m in _models()]
        with connection.cursor() as cursor:
            cursor.execute("SELECT relname, relrowsecurity, relforcerowsecurity, pg_has_role(current_user, relowner, 'USAGE') "
                "FROM pg_class WHERE oid=ANY(%s::regclass[])", [tables])
            rows = cursor.fetchall()
            check("RLS", len(rows) == len(tables) and all(r[1] and r[2] for r in rows), "Every khata table requires enabled and forced RLS.")
            cursor.execute("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
            superuser, bypass = cursor.fetchone()
            check("RUNTIME_ROLE", not superuser and not bypass and not any(r[3] for r in rows),
                "Run this assessment through the restricted runtime connection to verify role safety; owner credentials are for migrations/recovery only.")
            cursor.execute("SELECT t.tgname, t.tgenabled, t.tgrelid::regclass::text FROM pg_trigger t WHERE t.tgrelid=ANY(%s::regclass[]) AND NOT t.tgisinternal", [tables])
            triggers = cursor.fetchall()
            document_guards = {"khata_document_guard", "khata_document_immutable_guard", "khata_label_guard"}
            check("GUARDS", {row[2] for row in triggers} == set(tables) and all(row[1] == "O" for row in triggers)
                and document_guards <= {row[0] for row in triggers}, "Every khata table and all A4/label immutable-source guards must be present and enabled.")
        try:
            validate_coverage()
        except (ValueError, RuntimeError, ValidationError) as exc:
            check("STORAGE_REGISTRY", False, str(exc))
        else:
            check("STORAGE_REGISTRY", True, "Retained khata photos and document/label files are registered.")
        series = list(KhataSeries.objects.filter(workspace=workspace, is_active=True).select_related("license"))
        available = []
        unavailable = []
        for row in series:
            try:
                _series_ready(row, timezone.localdate())
            except ValueError as exc:
                unavailable.append(dict(id=row.pk, name=row.name, reason=str(exc)))
            else:
                available.append(dict(id=row.pk, name=row.name, associated=bool(row.license_id)))
        check("SERIES", bool(available), "At least one active, unexhausted, currently eligible khata series is required for a pilot opening.")
        totals = portfolio_summary(workspace=workspace, include_rows=False)
        check("BALANCES", not totals.get("unavailable"), "Canonical balances must be available; limits/unused entitlement are not debt.")
        try:
            content = export_archive(workspace=workspace, actor=actor)
            _read(content, hashlib.sha256(content).hexdigest())
        except (ValueError, OSError) as exc:
            check("NATIVE_EVIDENCE", False, str(exc))
        else:
            check("NATIVE_EVIDENCE", True, "Native rows, source evidence and retained file bytes encode and verify. This does not certify a saved backup or completed restore rehearsal.")
        return dict(workspace_id=workspace.pk, workspace_slug=workspace.slug, as_of=timezone.localdate().isoformat(),
            software_ready=all(row["passed"] for row in checks), pilot_authorized=False,
            checks=checks, available_series=available, unavailable_series=unavailable,
            manual_gates=list(MANUAL_GATES), totals={k: str(totals.get(k)) for k in
                ("active_count", "principal", "interest", "due_interest", "overdue_interest", "pending_returns")})
