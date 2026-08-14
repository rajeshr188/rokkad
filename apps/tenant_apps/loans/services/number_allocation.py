from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.tenant_apps.loans.domain import LoanDocumentKind
from apps.tenant_apps.loans.models import LoanNumberSequence, LoanSeries
from apps.tenant_apps.loans.services.license_series import (
    assert_series_can_issue,
)


class NumberAllocationError(ValueError):
    """Raised when an official document number cannot be allocated."""


class SequenceExhaustedError(NumberAllocationError):
    """Raised when a bounded series has no remaining numbers."""


@dataclass(frozen=True)
class NumberAllocation:
    value: str
    counter: int
    sequence_id: int


def preview_number(
    *, series: LoanSeries, document_kind: LoanDocumentKind | str
) -> NumberAllocation:
    assert_series_can_issue(series)
    sequence = _get_ready_sequence(series=series, document_kind=document_kind)
    return _build_allocation(sequence)


def allocate_number(
    *,
    series: LoanSeries,
    document_kind: LoanDocumentKind | str,
    actor=None,
) -> NumberAllocation:
    """Allocate once under a row lock; committed numbers are never reclaimed."""
    assert_series_can_issue(series)
    kind = LoanDocumentKind(document_kind).value
    with transaction.atomic():
        try:
            sequence = (
                LoanNumberSequence.objects.select_for_update()
                .select_related("series__license")
                .get(series=series, document_kind=kind)
            )
        except LoanNumberSequence.DoesNotExist as exc:
            raise NumberAllocationError(
                "No number sequence is configured for this document kind."
            ) from exc
        allocation = _build_allocation(sequence)
        LoanNumberSequence.objects.filter(pk=sequence.pk).update(
            next_number=sequence.next_number + 1,
            updated_by=actor,
        )
    return allocation


def allocate_pawn_loan_number(*, series: LoanSeries, actor=None) -> NumberAllocation:
    """The draft service uses this at draft creation, never at approval."""
    return allocate_number(
        series=series,
        document_kind=LoanDocumentKind.PAWN_LOAN,
        actor=actor,
    )


def allocate_release_number(*, series: LoanSeries, actor=None) -> NumberAllocation:
    return allocate_number(
        series=series,
        document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE,
        actor=actor,
    )


def _get_ready_sequence(
    *, series: LoanSeries, document_kind: LoanDocumentKind | str
) -> LoanNumberSequence:
    kind = LoanDocumentKind(document_kind).value
    try:
        return LoanNumberSequence.objects.get(series=series, document_kind=kind)
    except LoanNumberSequence.DoesNotExist as exc:
        raise NumberAllocationError(
            "No number sequence is configured for this document kind."
        ) from exc


def _build_allocation(sequence: LoanNumberSequence) -> NumberAllocation:
    if not sequence.is_active:
        raise NumberAllocationError("The number sequence is inactive.")
    if sequence.next_number > sequence.maximum_number:
        raise SequenceExhaustedError(
            "The number sequence is exhausted; select or create a new series."
        )
    return NumberAllocation(
        value=f"{sequence.prefix}{sequence.next_number:0{sequence.width}d}",
        counter=sequence.next_number,
        sequence_id=sequence.pk,
    )
