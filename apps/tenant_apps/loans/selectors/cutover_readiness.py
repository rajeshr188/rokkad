"""Fail-closed production cutover readiness for the PawnLoan MVP."""

from dataclasses import asdict, dataclass
from datetime import date

from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.recorder import MigrationRecorder

from apps.tenant_apps.loans.feature_flags import is_new_loans_enabled
from apps.tenant_apps.loans.models import current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.operations import (
    get_pawn_loan_operations_snapshot,
)
from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports


MANUAL_ACKNOWLEDGEMENTS = (
    ("BACKUP_REHEARSED", "A current backup and restore procedure was verified."),
    ("ROLLBACK_REHEARSED", "Feature-flag rollback and record ownership were rehearsed."),
    ("SUPPORT_READY", "Support ownership and escalation evidence were confirmed."),
    ("MONITORING_READY", "Outbox, reconciliation, and stale-processing monitoring were confirmed."),
    ("PERMISSIONS_REVIEWED", "Owner/Admin/member permissions were reviewed."),
    ("PILOT_WORKFLOW_ACCEPTED", "A real approved workflow was accepted by the pilot owner."),
)


@dataclass(frozen=True)
class PawnLoanCutoverCheck:
    code: str
    passed: bool
    message: str
    automated: bool = True


@dataclass(frozen=True)
class PawnLoanCutoverReadiness:
    workspace_id: int
    as_of_date: date
    feature_enabled: bool
    checks: tuple[PawnLoanCutoverCheck, ...]

    @property
    def blocker_count(self):
        return sum(not check.passed for check in self.checks)

    @property
    def is_ready(self):
        return self.blocker_count == 0

    def as_dict(self):
        return {
            "workspace_id": self.workspace_id,
            "as_of_date": self.as_of_date.isoformat(),
            "feature_enabled": self.feature_enabled,
            "is_ready": self.is_ready,
            "blocker_count": self.blocker_count,
            "checks": [asdict(check) for check in self.checks],
        }


def get_pawn_loan_cutover_readiness(*, as_of_date, acknowledgements=None):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("PawnLoan cutover readiness requires an active tenant schema.")

    workspace = getattr(connection, "tenant", None)
    operations = get_pawn_loan_operations_snapshot()
    reports = get_pawn_loan_reports(as_of_date=as_of_date)
    return build_pawn_loan_cutover_readiness(
        workspace_id=workspace_id,
        as_of_date=as_of_date,
        feature_enabled=is_new_loans_enabled(workspace),
        pending_migrations=_pending_loans_migrations(),
        operations=operations,
        reports=reports,
        acknowledgements=acknowledgements,
    )


def build_pawn_loan_cutover_readiness(
    *,
    workspace_id,
    as_of_date,
    feature_enabled,
    pending_migrations,
    operations,
    reports,
    acknowledgements=None,
):
    acknowledgements = acknowledgements or {}
    sequence_rows = tuple(operations.sequence_rows)
    checks = [
        PawnLoanCutoverCheck(
            "LOANS_MIGRATIONS",
            not pending_migrations,
            (
                "All Loans migrations are applied."
                if not pending_migrations
                else "Pending Loans migrations: " + ", ".join(pending_migrations)
            ),
        ),
        PawnLoanCutoverCheck(
            "NUMBERING_READY",
            bool(sequence_rows) and operations.sequence_blocker_count == 0,
            (
                f"{len(sequence_rows)} required numbering sequence checks passed."
                if sequence_rows and operations.sequence_blocker_count == 0
                else (
                    f"{operations.sequence_blocker_count} numbering blocker(s) remain."
                    if sequence_rows
                    else "No license/series numbering setup is available."
                )
            ),
        ),
        PawnLoanCutoverCheck(
            "OUTBOX_HEALTH",
            operations.failed_count == 0 and not operations.stale_processing_events,
            (
                "No failed or stale accounting deliveries."
                if operations.failed_count == 0 and not operations.stale_processing_events
                else (
                    f"Failed deliveries={operations.failed_count}; "
                    f"stale processing={len(operations.stale_processing_events)}."
                )
            ),
        ),
        PawnLoanCutoverCheck(
            "ACCOUNTING_READY",
            operations.accounting_blocker_count == 0,
            (
                "Approved/active loans have no accounting setup blockers."
                if operations.accounting_blocker_count == 0
                else f"{operations.accounting_blocker_count} accounting blocker(s) remain."
            ),
        ),
        PawnLoanCutoverCheck(
            "LOANS_RECONCILIATION",
            not reports.issues,
            (
                "Loans source-to-DEA reconciliation has no findings."
                if not reports.issues
                else f"Loans reconciliation has {len(reports.issues)} finding(s)."
            ),
        ),
    ]
    checks.extend(
        PawnLoanCutoverCheck(
            code,
            bool(acknowledgements.get(code)),
            message if acknowledgements.get(code) else f"Required acknowledgement missing: {message}",
            automated=False,
        )
        for code, message in MANUAL_ACKNOWLEDGEMENTS
    )
    return PawnLoanCutoverReadiness(
        workspace_id=workspace_id,
        as_of_date=as_of_date,
        feature_enabled=feature_enabled,
        checks=tuple(checks),
    )


def _pending_loans_migrations():
    loader = MigrationLoader(connection, ignore_no_migrations=True)
    applied = MigrationRecorder(connection).applied_migrations()
    pending = []
    for app_label, migration_name in loader.graph.leaf_nodes("loans"):
        if (app_label, migration_name) not in applied:
            pending.append(f"{app_label}.{migration_name}")
    return tuple(sorted(pending))


__all__ = [
    "MANUAL_ACKNOWLEDGEMENTS",
    "PawnLoanCutoverCheck",
    "PawnLoanCutoverReadiness",
    "build_pawn_loan_cutover_readiness",
    "get_pawn_loan_cutover_readiness",
]
