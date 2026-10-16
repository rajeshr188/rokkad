"""One aggregate over current saved assessments; never refresh during a GET."""
from decimal import Decimal

from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .risk_portfolio import _active_portfolio
from .assessment_evidence import with_assessment_amounts, usable_financial_assessment, usable_coverage_assessment


def get_dashboard_health_summary(*, workspace):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Dashboard health requires the matching Workspace context.")
    today = timezone.localdate()
    rows = with_assessment_amounts(_active_portfolio(today))
    current = Q(assessment_status="CURRENT")
    financial = usable_financial_assessment()
    coverage = usable_coverage_assessment()
    totals = rows.aggregate(
        loan_count=Count("pk"), current_count=Count("pk", filter=current),
        transaction_count=Count("pk", filter=current & Q(risk_snapshot__source_provenance__transactions__complete=True)),
        book_reviewed_count=Count("pk", filter=current & Q(risk_snapshot__source_provenance__transactions__book_review__complete=True,
            risk_snapshot__source_provenance__transactions__book_review__status__in=("CONFIRMED", "ROKKAD_ONLY"))),
        provisional_count=Count("pk", filter=current & Q(risk_snapshot__source_provenance__transactions__complete=False)),
        assumed_capture_count=Count("pk", filter=current & (
            Q(risk_snapshot__source_provenance__transactions__capture_basis="SYSTEM_CAPTURE_ASSUMPTION")
            | Q(risk_snapshot__source_provenance__transactions__book_review__capture_basis="SYSTEM_CAPTURE_ASSUMPTION"))),
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
    totals["freshness_complete"] = totals["current_count"] == totals["loan_count"]
    totals["calculation_complete"] = totals["financial_count"] == totals["loan_count"]
    totals["valuation_complete"] = totals["coverage_count"] == totals["loan_count"]
    totals["transaction_unknown_count"] = totals["current_count"] - totals["transaction_count"] - totals["provisional_count"]
    totals["transactions_complete"] = totals["transaction_count"] == totals["loan_count"]
    totals["financial_complete"] = totals["calculation_complete"] and totals["transactions_complete"]
    totals["coverage_complete"] = totals["valuation_complete"] and totals["transactions_complete"]
    for field in ("projected_interest", "economic_exposure"):
        if totals["loan_count"] == 0:
            totals[field] = Decimal("0")
    for field in ("collateral_value", "full_shortfall"):
        if totals["loan_count"] == 0:
            totals[field] = Decimal("0")
    return {"as_of_date": today, **totals}
