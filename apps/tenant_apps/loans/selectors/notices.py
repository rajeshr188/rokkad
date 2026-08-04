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


def get_pawn_loan_notice_rows(loan) -> tuple[PawnLoanNoticeRow, ...]:
    notices = tuple(loan.notices.all().order_by("-created_at", "-pk"))
    states = get_pawn_notice_delivery_states(
        notice.notification_job_id for notice in notices
    )
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
            )
        )
    return tuple(rows)


__all__ = ["PawnLoanNoticeRow", "get_pawn_loan_notice_rows"]
