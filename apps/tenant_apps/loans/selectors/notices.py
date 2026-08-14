"""Read models that join Loans-owned intent to Notify-owned delivery state."""

from dataclasses import dataclass

from apps.tenant_apps.loans.integrations.notice_delivery import (
    get_pawn_notice_delivery_states,
)


@dataclass(frozen=True)
class PawnLoanNoticeRow:
    notice: object
    status: str
    external_reference: str
    failure_reason: str
    sent_at: object | None
    attempt_count: int
    last_attempt_at: object | None
    template: object | None
    artifact: object | None


def build_pawn_loan_notice_rows(notices) -> tuple[PawnLoanNoticeRow, ...]:
    from apps.tenant_apps.notify_v2.models import NotificationArtifact, NotificationJob

    notices = tuple(notices)
    states = get_pawn_notice_delivery_states(
        notice.notification_job_id for notice in notices
    )
    job_ids = tuple(notice.notification_job_id for notice in notices if notice.notification_job_id)
    jobs = {job.pk: job for job in NotificationJob.objects.filter(pk__in=job_ids).select_related("template")}
    artifacts = {}
    for artifact in NotificationArtifact.objects.filter(job_id__in=job_ids).order_by("job_id", "-created", "-pk"):
        artifacts.setdefault(artifact.job_id, artifact)
    rows = []
    for notice in notices:
        state = states.get(notice.notification_job_id)
        rows.append(
            PawnLoanNoticeRow(
                notice=notice,
                status=state.status if state else "MISSING",
                external_reference=state.external_reference if state else "",
                failure_reason=(
                    state.failure_reason
                    if state
                    else "The linked Notify delivery job is missing."
                ),
                sent_at=state.sent_at if state else None,
                attempt_count=state.attempt_count if state else 0,
                last_attempt_at=state.last_attempt_at if state else None,
                template=getattr(jobs.get(notice.notification_job_id), "template", None),
                artifact=artifacts.get(notice.notification_job_id),
            )
        )
    return tuple(rows)


def get_pawn_loan_notice_rows(loan) -> tuple[PawnLoanNoticeRow, ...]:
    return build_pawn_loan_notice_rows(
        loan.notices.all().order_by("-created_at", "-pk")
    )


__all__ = [
    "PawnLoanNoticeRow",
    "build_pawn_loan_notice_rows",
    "get_pawn_loan_notice_rows",
]
