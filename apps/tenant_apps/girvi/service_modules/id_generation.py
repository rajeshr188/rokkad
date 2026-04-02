import logging
import re
from typing import Optional

from django.apps import apps
from django.db import transaction

from apps.tenant_apps.girvi.models import Series
from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan

logger = logging.getLogger(__name__)


class LoanIDGenerator:
    """
    Simplified loan ID generation service.
    Series is mandatory - generates formatted IDs like 'A00123'.

    Thread-safe using select_for_update locks.
    """

    @staticmethod
    def generate(series: Series) -> str:
        if not series:
            raise ValueError("Series is required for loan ID generation")

        with transaction.atomic():
            series = Series.objects.select_for_update().get(id=series.id)
            last_loan = GivenLoan.objects.filter(series=series).order_by("-loan_id").first()

            if last_loan:
                try:
                    last_num = int(last_loan.loan_id[len(series.prefix) :])
                    next_num = last_num + 1
                except (ValueError, IndexError):
                    next_num = 1
            else:
                next_num = 1

            return series.format_loan_id(next_num)


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
