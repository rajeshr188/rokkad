"""Pawn reads; existing services own business rules."""

from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.domain import (
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.filters import PawnLoanFilter
from apps.tenant_apps.loans.models import (
    CollateralAppraisal,
    PawnLoan,
    PawnLoanEvent,
    PawnLoanRenewal,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_balance,
    get_pawn_loan_collateral_valuation,
    get_pawn_loan_delinquency,
    get_pawn_loan_exposure,
    get_pawn_loan_notice_rows,
    get_pawn_loan_risk_assessment,
    get_pawn_loan_series_navigation,
)
from apps.tenant_apps.loans.services import (
    assess_pawn_loan_event_reversal,
    preview_pawn_loan_accruals,
)
from apps.tenant_apps.loans.web.pawn_draft_actions import get_pawn_draft_readiness
from apps.tenant_apps.loans.web.pawn_read_helpers import (
    _can_administer,
    _can_manage_storage,
    _pawn_loan_for_workspace,
)


@loans_workspace_required
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).order_by("-created_at")
    loan_filter = PawnLoanFilter(
        request.GET,
        queryset=loans,
        workspace=request.loans_workspace,
    )
    page_obj = Paginator(loan_filter.qs, 25).get_page(request.GET.get("page"))
    readiness = get_pawn_draft_readiness(request.loans_workspace)
    return render(
        request,
        "loans/pawn/list.html",
        {
            "loans": page_obj.object_list,
            "loan_filter": loan_filter,
            "page_obj": page_obj,
            "readiness": readiness,
            "can_manage_loan_setup": request.loans_workspace_access.can("workspace.settings.manage"),
        },
    )


@loans_workspace_required
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    series_navigation = get_pawn_loan_series_navigation(loan)
    context = {
        "loan": loan,
        "previous_loan": series_navigation.previous,
        "next_loan": series_navigation.next,
        "today": timezone.localdate(),
        "can_administer": _can_administer(request),
        "can_manage_storage": _can_manage_storage(request),
        "notice_rows": get_pawn_loan_notice_rows(loan),
        "auctions": loan.auctions.select_related("loan_event").order_by("-attempt_number"),
        "renewals": PawnLoanRenewal.objects.filter(
            Q(source_loan=loan) | Q(successor_loan=loan)
        ).select_related(
            "source_loan",
            "successor_loan",
            "settlement_event",
            "opening_event",
        ),
    }
    approval = loan.approval_snapshots.order_by("-version").first()
    if approval:
        evidence = approval.payload.get("origination_rates", {})
        context["approved_quote_rows"] = [dict(quote,
            effective_time=parse_datetime(quote["effective_at"]))
            for quote in evidence.get("quotes", {}).values()]
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value}:
        try:
            context["balance"] = get_pawn_loan_balance(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["balance_error"] = str(exc)
        try:
            context["exposure"] = get_pawn_loan_exposure(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["exposure_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            context["delinquency"] = get_pawn_loan_delinquency(loan.pk, as_of_date=context["today"])
            context["collateral_valuation"] = get_pawn_loan_collateral_valuation(loan.pk, as_of_date=context["today"])
            context["risk_assessment"] = get_pawn_loan_risk_assessment(loan.pk, as_of_date=context["today"])
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["risk_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            context["accrual_previews"] = preview_pawn_loan_accruals(
                loan.pk,
                as_of_date=context["today"],
                include_partial=True,
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["accrual_error"] = str(exc)
    context["event_rows"] = _event_rows(
        loan,
        can_administer=context["can_administer"],
    )
    for action in ("repay", "release", "accrue", "capitalize"):
        context["can_" + action] = request.loans_workspace_access.can("loan." + action)
    context["can_renew"] = all(
        request.loans_workspace_access.can(action)
        for action in ("loan.release", "loan.approve", "loan.disburse")
    )
    context["can_send_notice"] = request.loans_workspace_access.can("data.edit")
    context["can_edit_loan"] = request.loans_workspace_access.can("data.edit")
    context["can_split_draft"] = context["can_edit_loan"] and request.loans_workspace_access.can("data.create")
    context["can_delete_draft_photos"] = loan.state == "DRAFT" and request.loans_workspace_access.can("data.edit")
    context["can_approve"] = request.loans_workspace_access.can("loan.approve")
    context["can_reappraise"] = loan.state == "ACTIVE" and context["can_approve"] and context["can_edit_loan"]
    current_appraisals = {}
    for appraisal in CollateralAppraisal.objects.filter(workspace=request.loans_workspace,
            collateral_item__loan=loan, status="APPROVED", effective_at__date__lte=context["today"]).order_by("-effective_at", "-version"):
        current_appraisals.setdefault(appraisal.collateral_item_id, appraisal)
    for item in loan.collateral_items.all():
        item.current_appraisal = current_appraisals.get(item.pk)
    context["can_disburse"] = request.loans_workspace_access.can("loan.disburse")
    context["simple_owner"] = request.loans_workspace.loan_workflow == "SIMPLE" and request.loans_workspace_access.can("workspace.transfer")
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        if context.get("simple_owner"):
            return {"label": "Review and disburse", "url": reverse('workspace_loans:pawn_loan_review_disburse', args=[loan.workspace.slug, loan.pk]), "message": "Review the summary and confirm payment in one action."}
        if not context.get("can_approve", False):
            return None
        return {
            "label": "Approve loan",
            "url": reverse('workspace_loans:pawn_loan_approve', args=[loan.workspace.slug, loan.pk]),
            "method": "post",
            "message": "Review the frozen terms, then approve this draft.",
        }
    if loan.state == PawnLoanState.APPROVED.value:
        if not context.get("can_disburse", False):
            return None
        return {
            "label": "Disburse loan",
            "url": reverse('workspace_loans:pawn_loan_disburse', args=[loan.workspace.slug, loan.pk]),
            "message": "Record disbursal to activate the loan.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        if not context.get("can_repay", False):
            return None
        return {
            "label": "Record repayment",
            "url": reverse('workspace_loans:pawn_loan_repay', args=[loan.workspace.slug, loan.pk]),
            "message": "Continue with repayment, accrual, or collateral release.",
        }
    if loan.state == PawnLoanState.CLOSED.value:
        return {
            "label": "Review event history",
            "url": "#business-events",
            "message": "This loan is closed. Administrators can reverse eligible events in order.",
        }
    return None


def _event_rows(loan, *, can_administer):
    events = tuple(
        loan.loan_events.select_related(
            "reversed_by_event", "loan__workspace"
        ).order_by("-effective_date", "-pk")
    )
    latest_event_id = next(
        (
            event.pk
            for event in events
            if event.event_kind != TransactionKind.REVERSAL.value
            and not hasattr(event, "reversed_by_event")
        ),
        None,
    )
    rows = []
    for event in events:
        try:
            reversed_event = event.reversed_by_event
        except PawnLoanEvent.DoesNotExist:
            reversed_event = None
        readiness = assess_pawn_loan_event_reversal(
            event, latest_event_id=latest_event_id
        )
        rows.append(
            {
                "event": event,
                "can_reverse": can_administer and readiness.can_reverse,
                "reversal_blocker": readiness.blocker,
                "reversed_event": reversed_event,
            }
        )
    return rows
