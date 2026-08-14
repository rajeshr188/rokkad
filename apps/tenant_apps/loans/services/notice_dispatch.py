"""Shared delivery lifecycle for Loans-owned notice intents.

Loans owns notice intent and scheduling. Notify owns delivery state and provider
attempts. This module coordinates that boundary without knowing the business
meaning of a customer or operational notice.
"""

from dataclasses import dataclass

from django.utils import timezone

from apps.tenant_apps.loans.integrations.notice_delivery import (
    deliver_pawn_notice_job,
    get_pawn_notice_delivery_states,
)


@dataclass(frozen=True)
class NoticeDeliveryBatch:
    due_count: int
    sent_count: int
    failed_count: int


def dispatch_linked_notice(
    notice,
    *,
    error_type,
    as_of=None,
    delivery_handler=None,
    states_loader=None,
    future_message="This notice is scheduled for a future time.",
    missing_message="The linked Notify delivery job is missing.",
):
    """Return Notify's receipt after enforcing the common delivery lifecycle."""

    as_of = as_of or timezone.now()
    if notice.scheduled_for > as_of:
        raise error_type(future_message)
    if not notice.notification_job_id:
        raise error_type(missing_message)
    state = (states_loader or get_pawn_notice_delivery_states)((notice.notification_job_id,)).get(
        notice.notification_job_id
    )
    if state is None:
        raise error_type(missing_message)
    if state.status == "SENT":
        return state
    if state.status == "CANCELLED":
        raise error_type("A cancelled notice cannot be delivered.")
    return (delivery_handler or deliver_pawn_notice_job)(notice.notification_job_id)


def dispatch_due_notices(
    queryset,
    *,
    dispatch,
    as_of=None,
    limit=100,
    states_loader=None,
):
    """Dispatch a bounded, deterministic set of due intents still queued in Notify."""

    as_of = as_of or timezone.now()
    limit = max(0, int(limit))
    candidates = tuple(
        queryset.filter(scheduled_for__lte=as_of)
        .order_by("scheduled_for", "pk")
        .values_list("pk", "notification_job_id")
    )
    states = (states_loader or get_pawn_notice_delivery_states)(
        job_id for _, job_id in candidates
    )
    due_ids = tuple(
        notice_id
        for notice_id, job_id in candidates
        if states.get(job_id) and states[job_id].status == "QUEUED"
    )[:limit]
    sent = failed = 0
    for notice_id in due_ids:
        receipt = dispatch(notice_id, as_of=as_of)
        sent += receipt.status == "SENT"
        failed += receipt.status == "FAILED"
    return NoticeDeliveryBatch(len(due_ids), sent, failed)


__all__ = [
    "NoticeDeliveryBatch",
    "dispatch_due_notices",
    "dispatch_linked_notice",
]
