"""One aggregate over current saved assessments; never refresh during a GET."""
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Min, Q, Sum, When
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast
from django.utils import timezone

from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .risk_portfolio import _active_portfolio


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
        When(**{lookup + "__regex": r"^[0-9]{1,18}(\.[0-9]{1,8})?$"},
             then=Cast(amount, number)),
        output_field=number,
    )


def get_dashboard_health_summary(*, workspace):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Dashboard health requires the matching Workspace context.")
    today = timezone.localdate()
    rows = _active_portfolio(today).annotate(
        projected=_evidence_amount("financial__projected_interest"),
        recorded=_evidence_amount("financial__recorded_total_due"),
        coverage_exposure=_evidence_amount("coverage__exposure"),
        shortfall=_evidence_amount("coverage__shortfall"),
    )
    current = Q(assessment_status="CURRENT")
    financial = (current & Q(projected__isnull=False, recorded__isnull=False,
        risk_snapshot__source_provenance__financial__integrity_findings=[],
        risk_snapshot__exposure=F("recorded") + F("projected")))
    coverage = (financial & Q(coverage_exposure__isnull=False, shortfall__isnull=False,
        risk_snapshot__collateral_value__gte=0, risk_snapshot__ltv_ratio__isnull=False,
        risk_snapshot__source_provenance__coverage__blockers=[],
        risk_snapshot__source_provenance__coverage__status__in=("WITHIN_LIMIT", "BREACH")))
    totals = rows.aggregate(
        loan_count=Count("pk"), current_count=Count("pk", filter=current),
        stale_count=Count("pk", filter=Q(assessment_status="STALE")),
        error_count=Count("pk", filter=Q(assessment_status="ERROR")),
        unassessed_count=Count("pk", filter=Q(assessment_status="UNASSESSED")),
        financial_count=Count("pk", filter=financial),
        coverage_count=Count("pk", filter=coverage),
        unknown_coverage_count=Count("pk", filter=current & ~coverage),
        undercovered_count=Count("pk", filter=coverage & Q(shortfall__gt=0)),
        projected_interest=Sum("projected", filter=financial),
        economic_exposure=Sum("risk_snapshot__exposure", filter=financial),
        collateral_value=Sum("risk_snapshot__collateral_value", filter=coverage),
        full_shortfall=Sum("shortfall", filter=coverage),
        oldest_assessed_at=Min("risk_snapshot__assessed_at", filter=current),
    )
    totals["financial_complete"] = totals["financial_count"] == totals["loan_count"]
    totals["coverage_complete"] = totals["coverage_count"] == totals["loan_count"]
    for field in ("projected_interest", "economic_exposure"):
        totals[field] = (totals[field] or Decimal("0")) if totals["financial_complete"] else None
    for field in ("collateral_value", "full_shortfall"):
        totals[field] = (totals[field] or Decimal("0")) if totals["coverage_complete"] else None
    return {"as_of_date": today, **totals}
