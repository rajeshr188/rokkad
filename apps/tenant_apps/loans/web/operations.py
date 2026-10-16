"""Read-only operations, monitoring, and notice-ledger HTTP endpoints."""

from django.core.paginator import Paginator
from django.db.models import Case, When, Value, IntegerField
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.filters import (
    PawnLoanNoticeFilter,
)
from apps.tenant_apps.loans.models import (
    LoanRiskAlert,
    PawnLoanNotice,
)
from apps.tenant_apps.loans.selectors import (
    build_pawn_loan_notice_rows,
    get_pawn_loan_operations_snapshot,
    get_risk_portfolio,
    get_risk_portfolio_summary,
)
from apps.tenant_apps.loans.services.risk_communication_readiness import (
    assess_risk_alert_communication_readiness,
    get_email_provider_readiness,
)
from apps.tenant_apps.loans.services.risk_email_pilot import assess_risk_email_pilot
from apps.tenant_apps.loans.services.risk_whatsapp_pilot import assess_risk_whatsapp_pilot


@loans_setup_required
def pawn_operations_console(request):
    risk_notice_rows = build_pawn_loan_notice_rows(
        PawnLoanNotice.objects.filter(
            workspace=request.loans_workspace,
            source_risk_alert__isnull=False,
        ).select_related("loan", "loan__borrower").order_by("-created_at", "-pk")[:50]
    )
    risk_email_pilot = assess_risk_email_pilot()
    return render(request, "loans/setup/operations_console.html", {
        "snapshot": get_pawn_loan_operations_snapshot(),
        "email_provider": get_email_provider_readiness(),
        "latest_risk_notice_success": next((row for row in risk_notice_rows if row.status == "SENT"), None),
        "latest_risk_notice_failure": next((row for row in risk_notice_rows if row.status in {"FAILED", "MISSING"}), None),
        "risk_email_pilot": risk_email_pilot,
    })


@loans_setup_required
@require_GET
def pawn_risk_guide(request):
    """Owner reference only; never calculate, refresh or post loan activity."""
    return render(request, "loans/setup/risk_guide.html")


@loans_setup_required
def pawn_risk_portfolio(request):
    from apps.tenant_apps.loans.selectors.monitoring_readiness import get_monitoring_readiness
    allowed_statuses = {"CURRENT", "STALE", "ERROR", "UNASSESSED"}
    status = (request.GET.get("status") or "").strip().upper()
    if status not in allowed_statuses:
        status = None
    severity = (request.GET.get("severity") or "").strip()
    attention = request.GET.get('attention','')
    if attention not in {'measured','evidence','transactions','assessment'}:
        attention = ''
    page_obj = get_risk_portfolio(
        page=request.GET.get("page", 1),
        status=status,
        severity=severity or None,
        attention=attention or None,
    )
    alerts_query = LoanRiskAlert.objects.filter(
        workspace=request.loans_workspace,
        status=LoanRiskAlert.Status.OPEN,
        loan__state="ACTIVE",
    ).select_related("loan", "loan__borrower", "source_event").annotate(priority=Case(
        When(severity='CRITICAL',then=Value(0)),When(severity='HIGH',then=Value(1)),
        When(severity='MEDIUM',then=Value(2)),default=Value(3),output_field=IntegerField(),
    )).order_by('priority','created_at','pk')
    alerts_page = Paginator(alerts_query,25).get_page(request.GET.get('alert_page',1))
    alert_rows = []
    for alert in alerts_page:
        readiness = (
            assess_risk_alert_communication_readiness(alert.pk)
            if alert.alert_kind in {LoanRiskAlert.Kind.DPD_WORSENING, LoanRiskAlert.Kind.MATURITY}
            else None
        )
        email = next((row for row in readiness.channels if row.channel == "EMAIL"), None) if readiness else None
        whatsapp = next((row for row in readiness.channels if row.channel == "WHATSAPP"), None) if readiness else None
        alert_rows.append((alert, email, whatsapp))
    readiness = get_monitoring_readiness(workspace=request.loans_workspace)
    return render(request, "loans/setup/risk_portfolio.html", {
        "page_obj": page_obj,
        "risk_rows": page_obj.object_list,
        "summary": readiness['summary'],
        "selected_status": status or "",
        "selected_severity": severity,
        "open_alert_rows": alert_rows,
        "monitoring_readiness": readiness,
        "alerts_page": alerts_page,
        "selected_attention": attention,
    })


@loans_setup_required
def pawn_loan_notice_list(request):
    notices = PawnLoanNotice.objects.filter(
        workspace=request.loans_workspace
    ).select_related("loan", "loan__borrower", "created_by").order_by(
        "-created_at", "-pk"
    )
    notice_filter = PawnLoanNoticeFilter(request.GET, queryset=notices)
    page_obj = Paginator(notice_filter.qs, 50).get_page(request.GET.get("page"))
    return render(request, "loans/setup/notices/list.html", {
        "notice_filter": notice_filter,
        "notice_rows": build_pawn_loan_notice_rows(page_obj.object_list),
        "page_obj": page_obj,
    })


@loans_setup_required
def pawn_operations_runbook(request):
    return render(request, "loans/setup/operations_runbook.html")


@loans_setup_required
def pawn_risk_whatsapp_pilot(request):
    return render(request, "loans/setup/risk_whatsapp_pilot.html", {
        "report": assess_risk_whatsapp_pilot(),
    })


__all__ = [
    "pawn_loan_notice_list",
    "pawn_operations_console",
    "pawn_operations_runbook",
    "pawn_risk_guide",
    "pawn_risk_portfolio",
    "pawn_risk_whatsapp_pilot",
]
