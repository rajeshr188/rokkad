"""Shared checks for usable saved assessment amounts; no recalculation or writes."""
from decimal import Decimal
import re

from django.db.models import Case, DecimalField, F, Q, When
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast

AMOUNT_PATTERN = r"^[0-9]{1,18}(\.[0-9]{1,8})?$"
COVERAGE_STATUSES = ("WITHIN_LIMIT", "BREACH", "REFERENCE_LIMIT_UNAVAILABLE")


def _evidence_amount(path):
    # Missing, malformed or non-finite JSON amounts remain unavailable. CASE keeps
    # malformed strings away from PostgreSQL's numeric cast.
    lookup = "risk_snapshot__source_provenance__" + path
    keys = path.split("__")
    expression = F("risk_snapshot__source_provenance")
    for key in keys[:-1]:
        expression = KeyTransform(key, expression)
    amount = KeyTextTransform(keys[-1], expression)
    number = DecimalField(max_digits=28, decimal_places=8)
    return Case(
        When(**{lookup + "__regex": AMOUNT_PATTERN},
             then=Cast(amount, number)),
        output_field=number,
    )


def with_assessment_amounts(queryset):
    return queryset.annotate(
        projected=_evidence_amount("financial__projected_interest"),
        recorded=_evidence_amount("financial__recorded_total_due"),
        coverage_exposure=_evidence_amount("coverage__exposure"),
        shortfall=_evidence_amount("coverage__shortfall"),
    )


def usable_financial_assessment():
    return (Q(assessment_status="CURRENT", projected__isnull=False, recorded__isnull=False,
        risk_snapshot__source_provenance__financial__integrity_findings=[],
        risk_snapshot__exposure=F("recorded") + F("projected"))
        & (Q(risk_snapshot__source_provenance__financial__calculation_status="SUPPORTED")
           | Q(risk_snapshot__source_provenance__financial__calculation_status__isnull=True)))


def usable_coverage_assessment():
    return (usable_financial_assessment() & Q(coverage_exposure__isnull=False, shortfall__isnull=False,
        risk_snapshot__collateral_value__gte=0, risk_snapshot__ltv_ratio__isnull=False,
        risk_snapshot__source_provenance__coverage__blockers=[],
        risk_snapshot__source_provenance__coverage__status__in=COVERAGE_STATUSES))


def snapshot_financial_usable(snapshot):
    if not isinstance(snapshot.source_provenance, dict):
        return False
    financial = snapshot.source_provenance.get("financial", {})
    if not isinstance(financial, dict):
        return False
    amounts = [financial.get(key) for key in ("recorded_total_due", "projected_interest")]
    return (financial.get("calculation_status") in (None, "SUPPORTED")
        and financial.get("integrity_findings") == []
        and all(re.fullmatch(AMOUNT_PATTERN, str(value)) for value in amounts)
        and snapshot.exposure == sum((Decimal(str(value)) for value in amounts), Decimal(0)))


def snapshot_coverage_usable(snapshot):
    if not isinstance(snapshot.source_provenance, dict):
        return False
    coverage = snapshot.source_provenance.get("coverage", {})
    if not isinstance(coverage, dict):
        return False
    return bool(snapshot_financial_usable(snapshot) and snapshot.ltv_ratio is not None
        and snapshot.collateral_value is not None and snapshot.collateral_value >= 0
        and coverage.get("status") in COVERAGE_STATUSES and coverage.get("blockers") == []
        and all(re.fullmatch(AMOUNT_PATTERN, str(coverage.get(key))) for key in ("exposure", "shortfall")))
