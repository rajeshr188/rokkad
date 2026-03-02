"""Release ID generation utilities."""
from __future__ import annotations

import logging
import re
from typing import Optional, TYPE_CHECKING

from django.apps import apps
from django.db import transaction

if TYPE_CHECKING:  # pragma: no cover - hints only
    from .models import Release, Series


logger = logging.getLogger(__name__)


class ReleaseIDGenerator:
    """Thread-safe release ID generator scoped per series."""

    DEFAULT_PREFIX = "RL"
    OPTIONAL_DELIMITER = "-"
    _TRAILING_DIGITS_RE = re.compile(r"(\d+)$")

    @classmethod
    def generate(cls, series: "Series") -> str:
        """Return the next release ID for the given series."""
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
            return int(match.group(1))

        fallback = cls._TRAILING_DIGITS_RE.search(release_id)
        if fallback:
            logger.warning(
                "Release ID '%s' does not match prefix '%s'. Falling back to trailing digits.",
                release_id,
                prefix,
            )
            return int(fallback.group(1))

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
