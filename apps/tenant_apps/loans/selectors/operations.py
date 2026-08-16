"""Owner/Admin operational diagnostics for the PawnLoan MVP."""

from dataclasses import dataclass
from datetime import timedelta

from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    LoanDocumentKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanRiskSnapshot,
    PawnLoan,
    PawnLoanEvent,
    current_tenant_workspace_id,
)


@dataclass(frozen=True)
class SequenceHealthRow:
    license: object
    series: object
    document_kind: str
    sequence: object | None
    status: str
    message: str
    next_value: str
    remaining: int


@dataclass(frozen=True)
class OperationsBlocker:
    code: str
    message: str
    action_label: str
    action_url: str | None = None


@dataclass(frozen=True)
class PawnLoanOperationsSnapshot:
    generated_at: object
    sequence_rows: tuple[SequenceHealthRow, ...]
    recent_reversals: tuple[object, ...]
    recent_audit_events: tuple[object, ...]
    active_loan_count: int
    unassessed_active_loan_count: int
    last_successful_risk_assessment_at: object | None

    @property
    def sequence_blocker_count(self):
        return sum(row.status != "READY" for row in self.sequence_rows)


def get_pawn_loan_operations_snapshot(
    *,
    failed_limit=50,
    audit_limit=50,
    reversal_limit=25,
    stale_after=timedelta(minutes=15),
):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("PawnLoan operations diagnostics require an active tenant schema.")
    now = timezone.now()
    licenses = tuple(
        LoanLicense.objects.filter(workspace_id=workspace_id)
        .prefetch_related("series__number_sequences")
        .order_by("license_number")
    )
    active_loans = PawnLoan.objects.filter(
        workspace_id=workspace_id,
        state=PawnLoanState.ACTIVE.value,
    )
    current_risk = LoanRiskSnapshot.objects.filter(
        workspace_id=workspace_id,
        status=LoanRiskSnapshot.Status.CURRENT,
    )
    return PawnLoanOperationsSnapshot(
        generated_at=now,
        sequence_rows=_sequence_health(licenses),
        recent_reversals=tuple(
            PawnLoanEvent.objects.filter(
                loan__workspace_id=workspace_id,
                event_kind=TransactionKind.REVERSAL.value,
            )
            .select_related("loan", "reversal_of", "created_by")
            .order_by("-created_at")[:reversal_limit]
        ),
        recent_audit_events=tuple(
            LoanChangeLog.objects.filter(loan__workspace_id=workspace_id)
            .select_related("loan", "actor")
            .order_by("-created_at")[:audit_limit]
        ),
        active_loan_count=active_loans.count(),
        unassessed_active_loan_count=active_loans.filter(
            risk_snapshot__isnull=True,
        ).count(),
        last_successful_risk_assessment_at=current_risk.aggregate(
            latest=Max("assessed_at")
        )["latest"],
    )


def _sequence_health(licenses):
    rows = []
    for license in licenses:
        for series in license.series.all():
            by_kind = {item.document_kind: item for item in series.number_sequences.all()}
            for kind in (
                LoanDocumentKind.PAWN_LOAN.value,
                LoanDocumentKind.PAWN_LOAN_RELEASE.value,
            ):
                sequence = by_kind.get(kind)
                status, message = _sequence_status(license, series, sequence)
                remaining = (
                    max(0, sequence.maximum_number - sequence.next_number + 1)
                    if sequence
                    else 0
                )
                next_value = (
                    f"{sequence.prefix}{sequence.next_number:0{sequence.width}d}"
                    if sequence and remaining
                    else "Not available"
                )
                rows.append(
                    SequenceHealthRow(
                        license,
                        series,
                        kind,
                        sequence,
                        status,
                        message,
                        next_value,
                        remaining,
                    )
                )
    return tuple(rows)


def _sequence_status(license, series, sequence):
    if not license.is_active:
        return "BLOCKED", "License is inactive."
    if license.is_expired():
        return "BLOCKED", "License is expired."
    if not series.is_active:
        return "BLOCKED", "Series is inactive."
    if sequence is None:
        return "BLOCKED", "Required number sequence is missing."
    if not sequence.is_active:
        return "BLOCKED", "Number sequence is inactive."
    if sequence.next_number > sequence.maximum_number:
        return "EXHAUSTED", "Create or select a new series before issuing more documents."
    return "READY", "Ready to allocate."


__all__ = [
    "PawnLoanOperationsSnapshot",
    "OperationsBlocker",
    "SequenceHealthRow",
    "get_pawn_loan_operations_snapshot",
]
