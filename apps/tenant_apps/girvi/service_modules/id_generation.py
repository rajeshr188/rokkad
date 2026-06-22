import logging
import re
from typing import Optional

from django.apps import apps
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.girvi.models import Series

logger = logging.getLogger(__name__)


class LoanIDGenerator:
    """
    Simplified loan ID generation service.
    Series is mandatory - generates formatted IDs like 'A00123'.

    Thread-safe using select_for_update locks.
    """

    @staticmethod
    def generate(series: Series, loan_model=None) -> str:
        if not series:
            raise ValueError("Series is required for loan ID generation")

        with transaction.atomic():
            series = Series.objects.select_for_update().get(id=series.id)
            GivenLoan = apps.get_model("girvi", "GivenLoan")
            TakenLoan = apps.get_model("girvi", "TakenLoan")
            last_num = 0
            for model in (GivenLoan, TakenLoan):
                for loan_id in model.objects.filter(series=series).values_list(
                    "loan_id", flat=True
                ):
                    try:
                        last_num = max(last_num, int(str(loan_id)[len(series.prefix) :]))
                    except (ValueError, IndexError, TypeError):
                        continue
            next_num = last_num + 1

            return series.format_loan_id(next_num)


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

        prefix = cls._determine_prefix(series)

        ReleaseModel = apps.get_model("girvi", "Release")
        with transaction.atomic():
            last_release = (
                ReleaseModel.objects.select_for_update()
                .filter(loan__series=series)
                .order_by("-release_id")
                .first()
            )

            last_sequence = cls._extract_sequence(last_release, prefix)
            next_sequence = (last_sequence + 1) if last_sequence else 1

            return cls._format(prefix, next_sequence, series.max_limit)

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
