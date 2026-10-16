from dataclasses import dataclass
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Case, CharField, Count, DateTimeField, F, Q, Sum, Value, When
from django.db.models.fields.json import KeyTextTransform, KeyTransform
from django.db.models.functions import Cast
from django.db.models.lookups import GreaterThan, IsNull
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .assessment_evidence import with_assessment_amounts, usable_financial_assessment, usable_coverage_assessment


SNAPSHOT_CONTRACT = "LOAN_RISK_SNAPSHOT_V13"


def snapshot_is_current(snapshot, as_of_date):
    provenance = getattr(snapshot, "source_provenance", {}) if snapshot else {}
    deadline = provenance.get("valuation", {}).get("next_evidence_at")
    if deadline is not None:
        try:
            deadline = parse_datetime(deadline)
        except (TypeError, ValueError):
            return False
        if deadline is None or timezone.is_naive(deadline) or deadline <= timezone.now():
            return False
    return bool(snapshot and snapshot.status == "CURRENT"
                and getattr(snapshot, "as_of_date", None) == as_of_date
                and provenance.get("calculation_contract") == SNAPSHOT_CONTRACT)


def current_snapshot_filter(as_of_date, prefix=""):
    deadline = Cast(KeyTextTransform("next_evidence_at",
        KeyTransform("valuation", F(f"{prefix}source_provenance"))), DateTimeField())
    return Q(**{
        f"{prefix}status": "CURRENT",
        f"{prefix}as_of_date": as_of_date,
        f"{prefix}source_provenance__calculation_contract": SNAPSHOT_CONTRACT,
    }) & (Q(IsNull(deadline, True)) | Q(GreaterThan(deadline, Value(timezone.now()))))


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
    provisional_count: int = 0
    unavailable_count: int = 0
    assumed_capture_count: int = 0
    inconsistent_calculation_count: int = 0
    financial_count: int = 0
    coverage_count: int = 0
    transaction_count: int = 0
    transaction_unknown_count: int = 0


def get_risk_portfolio(*, page=1, page_size=50, status=None, severity=None,
                       performance_class=None, min_dpd=None, max_dpd=None,
                       min_ltv=None, max_ltv=None, borrower_id=None,
                       product_version_id=None, maturity_from=None, maturity_to=None,
                       as_of_date=None, attention=None):
    queryset = _active_portfolio(as_of_date or timezone.localdate()).select_related(
        "borrower", "product_version__product", "risk_snapshot", "policy_snapshot"
    ).prefetch_related("transaction_reviews", "loan_events")
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
    if attention == 'assessment':
        queryset = queryset.exclude(assessment_status='CURRENT')
    elif attention == 'evidence':
        queryset = with_assessment_amounts(queryset).filter(assessment_status='CURRENT').filter(~usable_coverage_assessment())
    elif attention == 'transactions':
        queryset = queryset.filter(assessment_status='CURRENT').filter(
            Q(risk_snapshot__source_provenance__transactions__complete=False)
            | Q(risk_snapshot__source_provenance__transactions__complete__isnull=True)
            | Q(risk_snapshot__source_provenance__transactions__complete=None))
    elif attention == 'measured':
        flags = Q()
        for flag in ('DPD_SUBSTANDARD','PAYMENT_OVERDUE','PAST_MATURITY','MATURITY_APPROACHING',
                     'LTV_WARNING','LTV_BREACH','LTV_CRITICAL'):
            flags |= Q(risk_snapshot__flags__contains=[flag])
        queryset = queryset.filter(flags,assessment_status='CURRENT')
    # Metric filters describe current assessments only; old values aren't current facts.
    if any(value is not None and value != "" for value in
           (severity, performance_class, min_dpd, max_dpd, min_ltv, max_ltv)):
        queryset = queryset.filter(assessment_status="CURRENT")
    queryset = queryset.filter(**filters).distinct().order_by("assessment_status", "pk")
    result = Paginator(queryset, min(max(int(page_size), 1), 200)).get_page(page)
    from .evidence_quality import loan_evidence_quality
    for loan in result.object_list:
        loan.evidence_quality = loan_evidence_quality(loan, as_of_date=as_of_date or timezone.localdate())
    return result


def get_risk_portfolio_summary(*, as_of_date=None):
    queryset = with_assessment_amounts(_active_portfolio(as_of_date or timezone.localdate()))
    current = Q(assessment_status="CURRENT")
    usable = usable_financial_assessment()
    coverage = usable_coverage_assessment()
    totals = queryset.aggregate(
        loan_count=Count("pk"), current_count=Count("pk", filter=current),
        unassessed_count=Count("pk", filter=Q(assessment_status="UNASSESSED")),
        stale_count=Count("pk", filter=Q(assessment_status="STALE")),
        error_count=Count("pk", filter=Q(assessment_status="ERROR")),
        financial_count=Count("pk", filter=usable),
        coverage_count=Count("pk", filter=coverage),
        unknown_coverage_count=Count("pk", filter=current & ~coverage),
        transaction_count=Count("pk", filter=current & Q(risk_snapshot__source_provenance__transactions__complete=True)),
        provisional_count=Count("pk", filter=current & Q(risk_snapshot__source_provenance__transactions__complete=False)),
        assumed_capture_count=Count("pk", filter=current & (
            Q(risk_snapshot__source_provenance__transactions__capture_basis="SYSTEM_CAPTURE_ASSUMPTION")
            | Q(risk_snapshot__source_provenance__transactions__book_review__capture_basis="SYSTEM_CAPTURE_ASSUMPTION"))),
        inconsistent_calculation_count=Count("pk", filter=Q(assessment_status__in=("CURRENT", "ERROR"), risk_snapshot__source_provenance__financial__calculation_status="INCONSISTENT")),
        unavailable_count=Count("pk", filter=~usable | Q(risk_snapshot__exposure__isnull=True) | Q(risk_snapshot__overdue__isnull=True)),
        total_exposure=Sum("risk_snapshot__exposure", filter=usable),
        total_overdue=Sum("risk_snapshot__overdue", filter=usable),
    )
    totals["transaction_unknown_count"] = totals["current_count"] - totals["transaction_count"] - totals["provisional_count"]
    complete = totals["unavailable_count"] == 0 and totals["transaction_count"] == totals["loan_count"] and totals["inconsistent_calculation_count"] == 0
    for field in ("total_exposure", "total_overdue"):
        if totals["loan_count"] == 0:
            totals[field] = Decimal("0")
    assessed = queryset.filter(usable)
    return RiskPortfolioSummary(
        **totals, totals_complete=complete,
        by_severity=tuple(assessed.values(severity=F("risk_snapshot__severity")).annotate(count=Count("pk"), exposure=Sum("risk_snapshot__exposure")).order_by("severity")),
        by_product=tuple(assessed.values("product_version_id", "product_version__product__name").annotate(count=Count("pk"), exposure=Sum("risk_snapshot__exposure")).order_by("product_version_id")),
    )
