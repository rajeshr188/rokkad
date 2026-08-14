"""Operator-facing read model for a frozen collateral verification session."""

from dataclasses import dataclass

from apps.tenant_apps.loans.integrations.notice_delivery import (
    get_pawn_notice_delivery_states,
)
from apps.tenant_apps.loans.models import LoanOperationalNotice


@dataclass(frozen=True)
class VerificationNoticeRow:
    notice: object
    status: str
    attempt_count: int
    last_attempt_at: object | None
    external_reference: str
    failure_reason: str


@dataclass(frozen=True)
class VerificationObservationRow:
    observation: object
    notices: tuple[VerificationNoticeRow, ...]
    blocks_operations: bool


@dataclass(frozen=True)
class PhysicalVerificationDetail:
    expectations: tuple
    observation_rows: tuple[VerificationObservationRow, ...]
    expected_count: int
    observed_expected_count: int
    pending_count: int
    discrepancy_count: int
    unresolved_count: int
    can_complete: bool


def get_physical_verification_detail(session) -> PhysicalVerificationDetail:
    expectations = tuple(
        session.expectations.select_related(
            "collateral_item__loan", "expected_location", "observation"
        ).order_by("expected_location__code", "collateral_item_id")
    )
    observations = tuple(
        session.observations.select_related(
            "collateral_item__loan",
            "observed_location",
            "expectation__expected_location",
            "recorded_by",
            "resolution",
        ).order_by("recorded_at", "pk")
    )
    notices = tuple(
        LoanOperationalNotice.objects.filter(
            source_verification_observation__session=session
        ).order_by("-created_at", "-pk")
    )
    states = get_pawn_notice_delivery_states(
        notice.notification_job_id for notice in notices
    )
    notices_by_observation = {}
    for notice in notices:
        state = states.get(notice.notification_job_id)
        notices_by_observation.setdefault(
            notice.source_verification_observation_id, []
        ).append(
            VerificationNoticeRow(
                notice=notice,
                status=state.status if state else "MISSING",
                attempt_count=state.attempt_count if state else 0,
                last_attempt_at=state.last_attempt_at if state else None,
                external_reference=state.external_reference if state else "",
                failure_reason=(
                    state.failure_reason
                    if state
                    else "The linked Notify delivery job is missing."
                ),
            )
        )

    observation_rows = []
    discrepancy_count = unresolved_count = 0
    for observation in observations:
        is_discrepancy = observation.classification != "FOUND"
        resolution = getattr(observation, "resolution", None)
        blocks_operations = is_discrepancy and (
            resolution is None or resolution.outcome == "DAMAGED"
        )
        discrepancy_count += int(is_discrepancy)
        unresolved_count += int(blocks_operations)
        observation_rows.append(
            VerificationObservationRow(
                observation=observation,
                notices=tuple(notices_by_observation.get(observation.pk, ())),
                blocks_operations=blocks_operations,
            )
        )

    expected_count = len(expectations)
    observed_expected_count = sum(
        1 for expectation in expectations if hasattr(expectation, "observation")
    )
    pending_count = expected_count - observed_expected_count
    return PhysicalVerificationDetail(
        expectations=expectations,
        observation_rows=tuple(observation_rows),
        expected_count=expected_count,
        observed_expected_count=observed_expected_count,
        pending_count=pending_count,
        discrepancy_count=discrepancy_count,
        unresolved_count=unresolved_count,
        can_complete=session.status == "OPEN" and pending_count == 0,
    )


__all__ = [
    "PhysicalVerificationDetail",
    "VerificationNoticeRow",
    "VerificationObservationRow",
    "get_physical_verification_detail",
]
