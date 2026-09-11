"""Risk refresh; existing services own business rules."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import (
    get_object_or_404,
    redirect,
)
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services import (
    RiskSnapshotRefreshError,
    reassess_pawn_loans_batch,
    refresh_loan_risk_snapshot,
)


@require_POST
@loans_setup_required
def pawn_risk_refresh_batch(request):
    as_of_date = _risk_refresh_date(request)
    if as_of_date is None:
        messages.error(request, "Risk assessment date must use YYYY-MM-DD.")
    else:
        try:
            result = reassess_pawn_loans_batch(
                workspace_id=request.loans_workspace.pk,
                as_of_date=as_of_date,
                batch_size=50,
            )
        except RiskSnapshotRefreshError as exc:
            messages.error(request, str(exc))
        else:
            if result["errors"]:
                messages.warning(
                    request,
                    f"Refreshed {result['current']} of {result['selected']} selected loans; "
                    f"{len(result['errors'])} assessment(s) need review.",
                )
            else:
                messages.success(
                    request,
                    f"Refreshed {result['current']} of {result['selected']} selected risk assessments.",
                )
    return _risk_portfolio_redirect(request)


@require_POST
@loans_setup_required
def pawn_risk_refresh_one(request, pk):
    loan = get_object_or_404(
        PawnLoan.objects.filter(
            workspace=request.loans_workspace,
            state=PawnLoanState.ACTIVE.value,
        ),
        pk=pk,
    )
    as_of_date = _risk_refresh_date(request)
    if as_of_date is None:
        messages.error(request, "Risk assessment date must use YYYY-MM-DD.")
    else:
        try:
            refresh_loan_risk_snapshot(loan.pk, as_of_date=as_of_date)
        except RiskSnapshotRefreshError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(
                request,
                f"Risk assessment refreshed for {loan.loan_number} as of {as_of_date}.",
            )
    return _risk_portfolio_redirect(request)


def _risk_refresh_date(request):
    raw = (request.POST.get("as_of") or timezone.localdate().isoformat()).strip()
    return parse_date(raw)


def _risk_portfolio_redirect(request):
    if request.headers.get("HX-Request") == "true":
        response = HttpResponse(status=204)
        response["HX-Redirect"] = reverse('workspace_loans:pawn_risk_portfolio', kwargs={'workspace_slug': request.workspace.slug})
        return response
    return redirect('workspace_loans:pawn_risk_portfolio', workspace_slug=request.workspace.slug)
