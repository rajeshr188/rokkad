from dataclasses import dataclass
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Sum

from apps.tenant_apps.loans.models import LoanRiskSnapshot, current_tenant_workspace_id


@dataclass(frozen=True)
class RiskPortfolioSummary:
    loan_count: int
    total_exposure: Decimal
    total_overdue: Decimal
    error_count: int
    stale_count: int
    by_severity: tuple[dict, ...]
    by_product: tuple[dict, ...]


def get_risk_portfolio(*, page=1, page_size=50, status=None, severity=None,
                       performance_class=None, min_dpd=None, max_dpd=None,
                       min_ltv=None, max_ltv=None, borrower_id=None,
                       product_version_id=None, maturity_from=None, maturity_to=None):
    workspace_id = current_tenant_workspace_id()
    queryset = LoanRiskSnapshot.objects.filter(workspace_id=workspace_id).select_related(
        "loan__borrower", "loan__product_version__product"
    )
    filters = {}
    if status: filters["status"] = status
    if severity: filters["severity"] = severity
    if performance_class: filters["performance_class"] = performance_class
    if min_dpd is not None: filters["days_past_due__gte"] = min_dpd
    if max_dpd is not None: filters["days_past_due__lte"] = max_dpd
    if min_ltv is not None: filters["ltv_ratio__gte"] = min_ltv
    if max_ltv is not None: filters["ltv_ratio__lte"] = max_ltv
    if borrower_id: filters["loan__borrower_id"] = borrower_id
    if product_version_id: filters["loan__product_version_id"] = product_version_id
    if maturity_from: filters["loan__repayment_schedules__maturity_date__gte"] = maturity_from
    if maturity_to: filters["loan__repayment_schedules__maturity_date__lte"] = maturity_to
    queryset = queryset.filter(**filters).distinct().order_by("-severity", "-days_past_due", "loan_id")
    return Paginator(queryset, min(max(int(page_size), 1), 200)).get_page(page)


def get_risk_portfolio_summary():
    workspace_id = current_tenant_workspace_id()
    queryset = LoanRiskSnapshot.objects.filter(workspace_id=workspace_id)
    totals = queryset.aggregate(loan_count=Count("pk"), total_exposure=Sum("exposure"), total_overdue=Sum("overdue"))
    return RiskPortfolioSummary(
        loan_count=totals["loan_count"], total_exposure=totals["total_exposure"] or Decimal("0"),
        total_overdue=totals["total_overdue"] or Decimal("0"),
        error_count=queryset.filter(status=LoanRiskSnapshot.Status.ERROR).count(),
        stale_count=queryset.filter(status=LoanRiskSnapshot.Status.STALE).count(),
        by_severity=tuple(queryset.values("severity").annotate(count=Count("pk"), exposure=Sum("exposure")).order_by("severity")),
        by_product=tuple(queryset.values("loan__product_version_id", "loan__product_version__product__name").annotate(count=Count("pk"), exposure=Sum("exposure")).order_by("loan__product_version__product__name")),
    )
