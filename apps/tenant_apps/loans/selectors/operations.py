"""Owner/Admin operational diagnostics for the PawnLoan MVP."""

from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Max
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanRiskSnapshot,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.accounting_readiness import (
    assess_pawn_loan_accounting_readiness,
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
class AccountingSetupRow:
    loan: object
    ready: bool
    blockers: tuple[object, ...]


@dataclass(frozen=True)
class OperationsBlocker:
    code: str
    message: str
    action_label: str
    action_url: str | None = None


@dataclass(frozen=True)
class PawnLoanOperationsSnapshot:
    generated_at: object
    outbox_counts: dict
    failed_events: tuple[object, ...]
    stale_processing_events: tuple[object, ...]
    sequence_rows: tuple[SequenceHealthRow, ...]
    accounting_rows: tuple[AccountingSetupRow, ...]
    recent_reversals: tuple[object, ...]
    recent_audit_events: tuple[object, ...]
    active_loan_count: int
    unassessed_active_loan_count: int
    last_successful_risk_assessment_at: object | None

    @property
    def failed_count(self):
        return self.outbox_counts.get(LoanOutboxStatus.FAILED.value, 0)

    @property
    def sequence_blocker_count(self):
        return sum(row.status != "READY" for row in self.sequence_rows)

    @property
    def accounting_blocker_count(self):
        return sum(not row.ready for row in self.accounting_rows)


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
    outboxes = PawnLoanAccountingOutbox.objects.filter(
        event__loan__workspace_id=workspace_id
    )
    outbox_counts = {
        status.value: outboxes.filter(status=status.value).count()
        for status in LoanOutboxStatus
    }
    failed = tuple(
        outboxes.filter(status=LoanOutboxStatus.FAILED.value)
        .select_related("event", "event__loan")
        .order_by("-updated_at")[:failed_limit]
    )
    stale = tuple(
        outboxes.filter(
            status=LoanOutboxStatus.PROCESSING.value,
            claimed_at__lt=now - stale_after,
        )
        .select_related("event", "event__loan")
        .order_by("claimed_at")[:failed_limit]
    )
    licenses = tuple(
        LoanLicense.objects.filter(workspace_id=workspace_id)
        .prefetch_related("series__number_sequences")
        .order_by("license_number")
    )
    loans = tuple(
        PawnLoan.objects.filter(
            workspace_id=workspace_id,
            state__in=[PawnLoanState.APPROVED.value, PawnLoanState.ACTIVE.value],
        )
        .select_related("borrower", "license", "policy_snapshot")
        .order_by("loan_number")
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
        outbox_counts=outbox_counts,
        failed_events=failed,
        stale_processing_events=stale,
        sequence_rows=_sequence_health(licenses),
        accounting_rows=_accounting_health(loans),
        recent_reversals=tuple(
            PawnLoanAccountingEvent.objects.filter(
                loan__workspace_id=workspace_id,
                event_kind=TransactionKind.REVERSAL.value,
            )
            .select_related("loan", "reversal_of", "created_by", "outbox")
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


def _accounting_health(loans):
    rows = []
    for loan in loans:
        try:
            recognition = loan.policy_snapshot.accounting_recognition
        except ObjectDoesNotExist:
            recognition = None
        try:
            readiness = assess_pawn_loan_accounting_readiness(
                loan,
                effective_date=timezone.localdate(),
                requires_interest_receivable=(
                    recognition == AccountingRecognition.ACCRUAL.value
                ),
            )
            rows.append(AccountingSetupRow(loan, readiness.ready, readiness.blockers))
        except Exception as exc:
            blocker = OperationsBlocker(
                code="ACCOUNTING_CHECK_FAILED",
                message=str(exc),
                action_label="Review accounting setup",
            )
            rows.append(AccountingSetupRow(loan, False, (blocker,)))
    return tuple(rows)


__all__ = [
    "AccountingSetupRow",
    "PawnLoanOperationsSnapshot",
    "OperationsBlocker",
    "SequenceHealthRow",
    "get_pawn_loan_operations_snapshot",
]
