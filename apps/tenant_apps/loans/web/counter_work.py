"""Dedicated overdue follow-up page using the dashboard's canonical queue."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work


@loans_workspace_required
@never_cache
@require_safe
def overdue_payments(request):
    workspace = request.loans_workspace
    work = get_workspace_counter_work(workspace=workspace)
    selected = work["queues"]["overdue"]
    dashboard_query = urlencode({key: request.GET[key]
        for key in ("period", "start", "end") if key in request.GET})
    return render(request, "loans/pawn/overdue_payments.html", {
        "workspace": workspace,
        "counter_work": work,
        "selected_queue": selected,
        "work_page": Paginator(selected["rows"], 20).get_page(request.GET.get("page")),
        "dashboard_query": dashboard_query,
    })
