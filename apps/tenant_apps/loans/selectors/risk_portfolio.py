from dataclasses import dataclass
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Case, CharField, Count, F, Q, Sum, Value, When
from django.utils import timezone

from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id


SNAPSHOT_CONTRACT = "LOAN_RISK_SNAPSHOT_V2"


def snapshot_is_current(snapshot, as_of_date):
    return bool(snapshot and snapshot.status == "CURRENT"
                and getattr(snapshot, "as_of_date", None) == as_of_date
                and getattr(snapshot, "source_provenance", {}).get("calculation_contract") == SNAPSHOT_CONTRACT)


def current_snapshot_filter(as_of_date, prefix=""):
    return Q(**{
        f"{prefix}status": "CURRENT",
        f"{prefix}as_of_date": as_of_date,
        f"{prefix}source_provenance__calculation_contract": SNAPSHOT_CONTRACT,
    })


def _active_portfolio(as_of_date):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Risk portfolio requires an explicit Workspace context.")
    return PawnLoan.objects.filter(workspace_id=workspace_id, state="ACTIVE").annotate(
        assessment_status=Case(
            When(risk_snapshot__isnull=True, then=Value("UNASSESSED")),
            When(risk_snapshot__status="ERROR", then=Value("ERROR")),
            When(current_snapshot_filter(as_of_date, "risk_snapshot__"), then=Value("CURRENT")),
            default=Value("STALE"), output_field=CharField(),
        )
    )


@dataclass(frozen=True)
class RiskPortfolioSummary:
    loan_count: int
    total_exposure: Decimal | None
    total_overdue: Decimal | None
    error_count: int
    stale_count: int
    unassessed_count: int
    current_count: int
    unknown_coverage_count: int
    totals_complete: bool
    by_severity: tuple[dict, ...]
    by_product: tuple[dict, ...]


def get_risk_portfolio(*, page=1, page_size=50, status=None, severity=None,
                       performance_class=None, min_dpd=None, max_dpd=None,
                       min_ltv=None, max_ltv=None, borrower_id=None,
                       product_version_id=None, maturity_from=None, maturity_to=None,
                       as_of_date=None):
    queryset = _active_portfolio(as_of_date or timezone.localdate()).select_related(
        "borrower", "product_version__product", "risk_snapshot"
    )
    filters = {}
    if status: filters["assessment_status"] = status
    if severity: filters["risk_snapshot__severity"] = severity
    if performance_class: filters["risk_snapshot__performance_class"] = performance_class
    if min_dpd is not None: filters["risk_snapshot__days_past_due__gte"] = min_dpd
    if max_dpd is not None: filters["risk_snapshot__days_past_due__lte"] = max_dpd
    if min_ltv is not None: filters["risk_snapshot__ltv_ratio__gte"] = min_ltv
    if max_ltv is not None: filters["risk_snapshot__ltv_ratio__lte"] = max_ltv
    if borrower_id: filters["borrower_id"] = borrower_id
    if product_version_id: filters["product_version_id"] = product_version_id
    if maturity_from: filters["repayment_schedules__maturity_date__gte"] = maturity_from
    if maturity_to: filters["repayment_schedules__maturity_date__lte"] = maturity_to
    # Metric filters describe current assessments only; old values aren't current facts.
    if any(value is not None and value != "" for value in
           (severity, performance_class, min_dpd, max_dpd, min_ltv, max_ltv)):
        queryset = queryset.filter(assessment_status="CURRENT")
    queryset = queryset.filter(**filters).distinct().order_by("assessment_status", "pk")
    return Paginator(queryset, min(max(int(page_size), 1), 200)).get_page(page)


def get_risk_portfolio_summary(*, as_of_date=None):
    queryset = _active_portfolio(as_of_date or timezone.localdate())
    current = Q(assessment_status="CURRENT")
    totals = queryset.aggregate(
        loan_count=Count("pk"), current_count=Count("pk", filter=current),
        unassessed_count=Count("pk", filter=Q(assessment_status="UNASSESSED")),
        stale_count=Count("pk", filter=Q(assessment_status="STALE")),
        error_count=Count("pk", filter=Q(assessment_status="ERROR")),
        unknown_coverage_count=Count("pk", filter=current & Q(risk_snapshot__ltv_ratio__isnull=True)),
        incomplete_money=Count("pk", filter=~current | Q(risk_snapshot__exposure__isnull=True) | Q(risk_snapshot__overdue__isnull=True)),
        total_exposure=Sum("risk_snapshot__exposure", filter=current),
        total_overdue=Sum("risk_snapshot__overdue", filter=current),
    )
    complete = totals.pop("incomplete_money") == 0
    for field in ("total_exposure", "total_overdue"):
        totals[field] = (totals[field] or Decimal("0")) if complete else None
    assessed = queryset.filter(current)
    return RiskPortfolioSummary(
        **totals, totals_complete=complete,
        by_severity=tuple(assessed.values(severity=F("risk_snapshot__severity")).annotate(count=Count("pk"), exposure=Sum("risk_snapshot__exposure")).order_by("severity")),
        by_product=tuple(assessed.values("product_version_id", "product_version__product__name").annotate(count=Count("pk"), exposure=Sum("risk_snapshot__exposure")).order_by("product_version_id")),
    )
