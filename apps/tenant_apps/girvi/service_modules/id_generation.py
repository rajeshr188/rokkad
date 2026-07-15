import logging
import re
from typing import Optional

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.tenant_apps.girvi.models.license import Series

logger = logging.getLogger(__name__)


def _sequence_model():
    return apps.get_model("girvi", "GirviNumberSequence")


def _document_kind_for_loan_model(loan_model=None):
    Sequence = _sequence_model()
    model_name = getattr(loan_model, "__name__", "") if loan_model else ""
    if model_name == "TakenLoan":
        return Sequence.DocumentKind.TAKEN_LOAN
    return Sequence.DocumentKind.GIVEN_LOAN


def _default_sequence_config(series, document_kind):
    Sequence = _sequence_model()
    if document_kind == Sequence.DocumentKind.GIVEN_LOAN_RELEASE:
        prefix = (getattr(series, "name", "") or "").strip() or ReleaseIDGenerator.DEFAULT_PREFIX
    else:
        prefix = (getattr(series, "prefix", "") or "").strip()
    if not prefix:
        raise ValidationError("Series prefix is required before Girvi number sequences can be initialized.")
    return {
        "prefix": prefix,
        "width": int(getattr(series, "max_limit", None) or 5),
        "next_number": 1,
        "is_active": True,
    }


class GirviNumberSequenceService:
    """Locked allocator for Girvi document numbers scoped by series and document kind."""

    _TRAILING_DIGITS_RE = re.compile(r"(\d+)$")

    @classmethod
    def preview(cls, series: Series, document_kind: str) -> str:
        sequence = cls.ensure_sequence(series, document_kind)
        return sequence.format_number(cls._next_available_number(sequence))

    @classmethod
    def allocate(cls, series: Series, document_kind: str, *, updated_by=None) -> str:
        if not series:
            raise ValueError("Series is required for Girvi number allocation")

        Sequence = _sequence_model()
        with transaction.atomic():
            cls.ensure_sequence(series, document_kind, updated_by=updated_by)
            sequence = (
                Sequence.objects.select_for_update()
                .select_related("series")
                .get(series_id=cls._series_pk(series), document_kind=document_kind)
            )
            cls._assert_sequence_active(sequence)
            allocated_number = cls._next_available_number(sequence)
            value = sequence.format_number(allocated_number)
            sequence.mark_allocated(allocated_number, updated_by=updated_by)
            return value

    @classmethod
    def sync_from_existing(cls, series: Series, document_kind: str, *, apply=False, updated_by=None):
        Sequence = _sequence_model()
        defaults = _default_sequence_config(series, document_kind)
        existing_ids = cls._existing_ids(series, document_kind)
        highest = cls._highest_numeric_suffix(existing_ids, defaults["prefix"])
        target_next = highest + 1

        sequence = Sequence.objects.filter(series=series, document_kind=document_kind).first()
        created = False
        if sequence is None:
            sequence = Sequence(series=series, document_kind=document_kind, **defaults)
            created = True

        before = {
            "prefix": sequence.prefix,
            "width": sequence.width,
            "next_number": sequence.next_number,
            "is_active": sequence.is_active,
        }
        sequence.prefix = sequence.prefix or defaults["prefix"]
        sequence.width = sequence.width or defaults["width"]
        sequence.next_number = max(int(sequence.next_number or 1), target_next)
        if updated_by is not None:
            sequence.updated_by = updated_by

        if apply:
            sequence.save()

        return {
            "series_id": cls._series_pk(series),
            "document_kind": document_kind,
            "created": created,
            "applied": bool(apply),
            "prefix": sequence.prefix,
            "width": sequence.width,
            "highest_existing_number": highest,
            "target_next_number": target_next,
            "before": before,
            "after": {
                "prefix": sequence.prefix,
                "width": sequence.width,
                "next_number": sequence.next_number,
                "is_active": sequence.is_active,
            },
        }

    @classmethod
    def ensure_sequence(cls, series: Series, document_kind: str, *, updated_by=None):
        """Return a configured sequence, creating it from existing IDs when absent."""
        if not series:
            raise ValueError("Series is required for Girvi number sequence setup")

        Sequence = _sequence_model()
        series_pk = cls._series_pk(series)
        try:
            sequence = Sequence.objects.get(
                series_id=series_pk,
                document_kind=document_kind,
            )
        except Sequence.DoesNotExist:
            try:
                with transaction.atomic():
                    cls.sync_from_existing(
                        series,
                        document_kind,
                        apply=True,
                        updated_by=updated_by,
                    )
            except IntegrityError:
                # Another request initialized the same sequence first.
                pass
            sequence = Sequence.objects.get(
                series_id=series_pk,
                document_kind=document_kind,
            )
        cls._assert_sequence_active(sequence)
        return sequence

    @classmethod
    def sync_all_for_series(cls, series: Series, *, apply=False, updated_by=None):
        Sequence = _sequence_model()
        return [
            cls.sync_from_existing(
                series,
                document_kind,
                apply=apply,
                updated_by=updated_by,
            )
            for document_kind in (
                Sequence.DocumentKind.GIVEN_LOAN,
                Sequence.DocumentKind.TAKEN_LOAN,
                Sequence.DocumentKind.GIVEN_LOAN_RELEASE,
                Sequence.DocumentKind.TAKEN_LOAN_SETTLEMENT,
            )
        ]

    @classmethod
    def summaries_for_series(cls, series: Series):
        Sequence = _sequence_model()
        existing = {
            sequence.document_kind: sequence
            for sequence in Sequence.objects.filter(series=series)
        }
        summaries = []
        for document_kind in (
            Sequence.DocumentKind.GIVEN_LOAN,
            Sequence.DocumentKind.TAKEN_LOAN,
            Sequence.DocumentKind.GIVEN_LOAN_RELEASE,
            Sequence.DocumentKind.TAKEN_LOAN_SETTLEMENT,
        ):
            sequence = existing.get(document_kind)
            summaries.append(
                {
                    "document_kind": document_kind,
                    "label": Sequence.DocumentKind(document_kind).label,
                    "sequence": sequence,
                    "is_configured": sequence is not None,
                    "preview": sequence.preview_value if sequence else "",
                }
            )
        return summaries

    @classmethod
    def _get_sequence(cls, series, document_kind):
        if not series:
            raise ValueError("Series is required for Girvi number sequence preview")
        Sequence = _sequence_model()
        try:
            sequence = Sequence.objects.get(
                series_id=cls._series_pk(series),
                document_kind=document_kind,
            )
        except Sequence.DoesNotExist as exc:
            raise ValidationError(
                f"Girvi number sequence is not configured for {document_kind} in series {series}."
            ) from exc
        cls._assert_sequence_active(sequence)
        return sequence

    @staticmethod
    def _series_pk(series):
        return getattr(series, "pk", None) or getattr(series, "id", None)

    @staticmethod
    def _assert_sequence_active(sequence):
        if not sequence.is_active:
            raise ValidationError(
                f"Girvi number sequence for {sequence.document_kind} in series {sequence.series} is inactive."
            )

    @classmethod
    def _highest_numeric_suffix(cls, values, prefix):
        highest = 0
        prefix_len = len(prefix or "")
        for raw_value in values:
            value = str(raw_value or "").strip()
            if prefix and value.startswith(prefix):
                candidate = value[prefix_len:]
            else:
                fallback = cls._TRAILING_DIGITS_RE.search(value)
                candidate = fallback.group(1) if fallback else ""
            try:
                highest = max(highest, int(candidate))
            except (TypeError, ValueError):
                continue
        return highest

    @classmethod
    def _next_available_number(cls, sequence):
        existing_values = {
            str(value or "").strip()
            for value in cls._existing_ids(sequence.series, sequence.document_kind)
        }
        candidate = int(sequence.next_number or 1)
        while sequence.format_number(candidate) in existing_values:
            candidate += 1
        return candidate

    @staticmethod
    def _existing_ids(series, document_kind):
        Sequence = _sequence_model()
        if document_kind == Sequence.DocumentKind.GIVEN_LOAN:
            return apps.get_model("girvi", "GivenLoan").objects.filter(
                series=series
            ).values_list("loan_id", flat=True)
        if document_kind == Sequence.DocumentKind.TAKEN_LOAN:
            return apps.get_model("girvi", "TakenLoan").objects.filter(
                series=series
            ).values_list("loan_id", flat=True)
        if document_kind == Sequence.DocumentKind.GIVEN_LOAN_RELEASE:
            return apps.get_model("girvi", "Release").objects.filter(
                loan__series=series
            ).values_list("release_id", flat=True)
        return []


class LoanIDGenerator:
    """
    Simplified loan ID generation service.
    Series is mandatory - generates formatted IDs like 'A00123'.

    Thread-safe using select_for_update locks.
    """

    @staticmethod
    def generate(series: Series, loan_model=None) -> str:
        document_kind = _document_kind_for_loan_model(loan_model)
        return GirviNumberSequenceService.allocate(series, document_kind)

    @staticmethod
    def preview(series: Series, loan_model=None) -> str:
        document_kind = _document_kind_for_loan_model(loan_model)
        return GirviNumberSequenceService.preview(series, document_kind)


def validate_loan_id_unique_across_loan_tables(
    loan_id: str,
    *,
    exclude_given_pk=None,
    exclude_taken_pk=None,
) -> None:
    """
    Validate a manual/imported loan ID against both runtime loan tables.

    The database currently guarantees uniqueness inside each concrete loan table.
    Until a tenant-local registry table exists, command/form code must also
    reject cross-table duplicates deterministically before save.
    """
    normalized = (loan_id or "").strip()
    if not normalized:
        return

    GivenLoan = apps.get_model("girvi", "GivenLoan")
    TakenLoan = apps.get_model("girvi", "TakenLoan")

    given_qs = GivenLoan.objects.filter(loan_id=normalized)
    if exclude_given_pk:
        given_qs = given_qs.exclude(pk=exclude_given_pk)

    taken_qs = TakenLoan.objects.filter(loan_id=normalized)
    if exclude_taken_pk:
        taken_qs = taken_qs.exclude(pk=exclude_taken_pk)

    if given_qs.exists() or taken_qs.exists():
        raise ValidationError("A loan with this LoanID already exists.")


class ReleaseIDGenerator:
    DEFAULT_PREFIX = "RL"
    OPTIONAL_DELIMITER = "-"
    _TRAILING_DIGITS_RE = re.compile(r"(\d+)$")

    @classmethod
    def generate(cls, series: "Series") -> str:
        if not series:
            raise ValueError("Series is required for release ID generation")
        Sequence = _sequence_model()
        return GirviNumberSequenceService.allocate(
            series,
            Sequence.DocumentKind.GIVEN_LOAN_RELEASE,
        )

    @classmethod
    def preview(cls, series: "Series") -> str:
        if not series:
            raise ValueError("Series is required for release ID preview")
        Sequence = _sequence_model()
        return GirviNumberSequenceService.preview(
            series,
            Sequence.DocumentKind.GIVEN_LOAN_RELEASE,
        )

    @classmethod
    def _determine_prefix(cls, series: "Series") -> str:
        prefix = (series.name or "").strip()
        if prefix:
            return prefix

        logger.warning(
            "Series %s has no name configured. Falling back to default release prefix '%s'.",
            series.pk,
            cls.DEFAULT_PREFIX,
        )
        return cls.DEFAULT_PREFIX

    @classmethod
    def _extract_sequence(cls, last_release: Optional["Release"], prefix: str) -> int:
        if not last_release or not last_release.release_id:
            return 0

        release_id = last_release.release_id.strip()
        pattern = rf"^{re.escape(prefix)}(?:{re.escape(cls.OPTIONAL_DELIMITER)})?(\d+)$"
        match = re.match(pattern, release_id)

        if match:
            sequence = int(match.group(1))
            logger.debug(
                "Extracted sequence %d from release ID '%s' using prefix '%s'",
                sequence,
                release_id,
                prefix,
            )
            return sequence

        fallback = cls._TRAILING_DIGITS_RE.search(release_id)
        if fallback:
            sequence = int(fallback.group(1))
            logger.warning(
                "Release ID '%s' does not match expected prefix '%s'. "
                "Using trailing digits fallback: %d",
                release_id,
                prefix,
                sequence,
            )
            return sequence

        logger.warning(
            "Unable to parse release ID '%s' for prefix '%s'. Resetting sequence to 1.",
            release_id,
            prefix,
        )
        return 0

    @staticmethod
    def _format(prefix: str, sequence: int, width: int) -> str:
        padded = f"{sequence:0{width}d}"
        return f"{prefix}{padded}"
