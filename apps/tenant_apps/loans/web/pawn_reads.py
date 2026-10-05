"""Pawn reads; existing services own business rules."""

from apps.subscriptions.access_policy import workspace_activity

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
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_headers
from apps.tenant_apps.loans.services.loan_workflow import make_review
from apps.tenant_apps.loans.services.pawn_disbursal import preview_approved_disbursal
from apps.tenant_apps.party.selectors import party_identification

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
@never_cache
@vary_on_headers("HX-Request", "HX-Target", "HX-History-Restore-Request", "HX-Boosted")
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).prefetch_related("series__number_sequences").order_by("-created_at", "-pk")
    loan_filter = PawnLoanFilter(
        request.GET,
        queryset=loans,
        workspace=request.loans_workspace,
    )
    valid = loan_filter.is_valid()
    page_obj = Paginator(loan_filter.qs if valid else loans.none(), 25).get_page(request.GET.get("page"))
    readiness = get_pawn_draft_readiness(request.loans_workspace)
    fragment = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "loan-results"
        and request.headers.get("HX-History-Restore-Request") != "true"
        and request.headers.get("HX-Boosted") != "true"
    )
    response = render(
        request,
        "loans/pawn/list.html#results" if fragment else "loans/pawn/list.html",
        {
            "loans": page_obj.object_list,
            "loan_filter": loan_filter,
            "selected_borrower": loan_filter.form.cleaned_data.get("borrower") if valid else None,
            "page_obj": page_obj,
            "readiness": readiness,
            "can_create_loans": workspace_activity(request.loans_workspace).can_write and request.loans_workspace_access.can("data.create"),
            "can_review_paper_backlog": request.loans_workspace_access.can("data.edit"),
            "more_filters_open": any(request.GET.get(key) for key in ("license", "series", "loan_date_from", "loan_date_to")),
            "can_manage_loan_setup": request.loans_workspace_access.can("workspace.settings.manage"),
        },
    )
    if fragment:
        response["X-Rokkad-Fragment"] = "loan-results"
    return response


@loans_workspace_required
@never_cache
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    opening = next((event for event in loan.loan_events.all() if event.event_kind == "MIGRATION_OPENING"), None)
    series_navigation = get_pawn_loan_series_navigation(loan)
    context = {
        "loan": loan,
        "borrower_identity": party_identification(loan.borrower),
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
    approval = max(loan.approval_snapshots.all(), key=lambda row: row.version, default=None)
    from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release, restated_renewal
    context["renewals"] = [restated_renewal(row) for row in context["renewals"]]
    context["releases"] = [restated_release(row) for row in loan.releases.all()]
    context["latest_approval"] = approval
    from .portable_documents import source_copies
    context['source_document_copies'] = source_copies(loan)
    from apps.tenant_apps.loans.services.valuation_review import valuation_refresh_reason
    context["valuation_refresh_reason"] = valuation_refresh_reason(loan, approval)
    context["can_record_earlier_payout"] = (loan.state == "DRAFT" and not opening
        and loan.loan_date < context["today"] and all(request.loans_workspace_access.can(action)
            for action in ("workspace.settings.manage", "data.edit", "loan.approve", "loan.disburse")))
    context["can_record_completed_payout"] = (loan.state in ("DRAFT", "APPROVED") and not loan.loan_events.exists()
        and all(request.loans_workspace_access.can(action) for action in ("data.create", "data.edit", "loan.disburse")))
    context["can_print_ticket"] = loan.state != "DRAFT" and approval is not None
    context["can_preview_imported_ticket"] = opening is not None and approval is None
    context["can_print_schedule"] = loan.repayment_schedules.exists()
    if loan.state in {"DRAFT", "APPROVED"}:
        try:
            if loan.state == "DRAFT":
                if not (context["can_record_completed_payout"] and loan.loan_date < context["today"]):
                    context["economics"], _token = make_review(loan)
            else:
                context["economics"] = preview_approved_disbursal(loan)
        except (ValidationError, ValueError) as exc:
            context["review_error"] = str(exc)
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
    if loan.state == PawnLoanState.ACTIVE.value and not opening:
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
    if loan.state == "ACTIVE":
        from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
        context["renewal_eligibility"] = servicing_eligibility(loan, operation="RENEWAL",
            purpose="CURRENT", effective_date=context["today"])
        context["auction_eligibility"] = servicing_eligibility(loan, operation="AUCTION",
            purpose="CURRENT", effective_date=context["today"])
        context["can_renew"] = context["can_renew"] and context["renewal_eligibility"].ready
    context["can_send_notice"] = request.loans_workspace_access.can("data.edit")
    context["can_edit_loan"] = request.loans_workspace_access.can("data.edit")
    context["can_split_draft"] = context["can_edit_loan"] and request.loans_workspace_access.can("data.create")
    context["can_delete_draft_photos"] = loan.state == "DRAFT" and request.loans_workspace_access.can("data.edit")
    if loan.state == "DRAFT":
        from apps.tenant_apps.loans.services.origination_settings import collateral_photos_required
        context["photos_required"] = collateral_photos_required(loan.workspace_id)
    context["can_approve"] = request.loans_workspace_access.can("loan.approve")
    context["can_reappraise"] = loan.state == "ACTIVE" and context["can_approve"] and context["can_edit_loan"]
    current_appraisals = {}
    for appraisal in CollateralAppraisal.objects.filter(workspace=request.loans_workspace,
            collateral_item__loan=loan, status="APPROVED", effective_at__date__lte=context["today"]).order_by("-effective_at", "-version"):
        current_appraisals.setdefault(appraisal.collateral_item_id, appraisal)
    for item in loan.collateral_items.all():
        item.current_appraisal = current_appraisals.get(item.pk)
    context["can_disburse"] = request.loans_workspace_access.can("loan.disburse")
    from apps.tenant_apps.loans.services.recorded_collections import recording_for, collection_balance
    recorded = recording_for(loan)
    from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
    context["transaction_completeness"] = transaction_completeness(loan, context["today"])
    context["can_review_transactions"] = request.loans_workspace_access.can("data.edit") and loan.state in ("ACTIVE", "CLOSED")
    context["can_confirm_paper_handover"] = (loan.state == "CLOSED" and request.loans_workspace_access.can("loan.release")
        and loan.collateral_items.filter(custody_state="PAPER_CLOSED").exists())
    from apps.tenant_apps.loans.services.servicing_eligibility import servicing_eligibility
    context["can_record_paper_closure"] = (loan.state == "ACTIVE" and context["can_release"]
        and servicing_eligibility(loan, operation="FULL_RELEASE", purpose="PAPER", effective_date=context["today"]).ready)
    if recorded:
        context["recorded_history"] = recorded
        context["can_correct_paper_closing"] = loan.state == "CLOSED" and loan.releases.exists()
        context["source_history"] = loan.historical_import.document.get("loan") if hasattr(loan, "historical_import") else None
        context["archive_admission"] = loan.historical_import if hasattr(loan, "historical_import") and loan.historical_import.archive_evidence_id else None
        context["can_print_schedule"] = True
        context["can_print_ticket"] = True
        for action in ("accrue", "capitalize", "send_notice"):
            context["can_" + action] = False
        if loan.state == "ACTIVE":
            context["recorded_collection_balance"] = collection_balance(loan, context["today"])
    if opening:
        context["is_opening"] = True
        for action in ("accrue", "capitalize"):
            context["can_" + action] = False
        from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence
        try:
            review = read_opening_evidence(loan, opening)["review"]
            context["opening_review"] = review
            if loan.state == PawnLoanState.ACTIVE.value:
                from apps.tenant_apps.loans.services.opening_continuation import opening_interest_breakdown
                context["opening_interest_breakdown"] = opening_interest_breakdown(review, as_of_date=context["today"], loan=loan)
            context["opening_source_valuations"] = [row for row in review["collateral"] if row["valuation"].get("status") == "UNVERIFIED"]
        except ValueError as exc:
            context["balance_error"] = str(exc)
        if loan.state == PawnLoanState.ACTIVE.value:
            from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
            try:
                context["collection_quote"] = preview_pawn_loan_full_release(loan.pk)
            except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
                context["collection_error"] = str(exc)
    context["simple_owner"] = request.loans_workspace.loan_workflow == "SIMPLE" and request.loans_workspace_access.can("workspace.transfer")
    if not workspace_activity(request.loans_workspace).can_write:
        for key in tuple(context):
            if key.startswith("can_") and key not in {"can_print_ticket", "can_print_schedule"}:
                context[key] = False
        context["simple_owner"] = False
        # Rebuild reversal controls after removing mutation permission.
        context["event_rows"] = _event_rows(loan, can_administer=False)
    context["repayment_rows"] = [
        row for row in context["event_rows"]
        if row["event"].event_kind == TransactionKind.REPAYMENT.value
    ]
    context["current_disbursal"] = next((row["event"] for row in context["event_rows"]
        if row["event"].event_kind == "DISBURSAL" and not row["reversed_event"]), None)
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        if context.get("can_record_completed_payout") and loan.loan_date < context["today"]:
            return {"label": "Record completed payout", "url": reverse(
                "workspace_loans:pawn_loan_record_completed_payout", args=[loan.workspace.slug, loan.pk]),
                "message": "If the money was already paid, record the actual agreement against this draft. If still unpaid, correct the intended payment date before approval."}
        if context.get("simple_owner"):
            return {"label": "Review and disburse", "url": reverse('workspace_loans:pawn_loan_review_disburse', args=[loan.workspace.slug, loan.pk]), "message": "Review the summary and confirm payment in one action."}
        if not context.get("can_approve", False):
            return None
        return {
            "label": "Approve loan",
            "url": reverse('workspace_loans:pawn_loan_approve', args=[loan.workspace.slug, loan.pk]),
            "method": "post",
            "message": _("Check the customer, collateral photos and amounts below. Approval saves the terms; payment is recorded separately."),
        }
    if loan.state == PawnLoanState.APPROVED.value:
        if context.get("valuation_refresh_reason") and (context.get("can_approve") or context.get("can_disburse")):
            return {"label": "Review updated valuation", "url": reverse(
                "workspace_loans:pawn_loan_review_updated_valuation", args=[loan.workspace.slug, loan.pk]),
                "message": "Cash not yet paid? Compare the approved prices with today's prices and review the terms before payment. If cash was already paid earlier, keep the actual date and use the earlier-payout workflow."}
        if not context.get("can_disburse", False):
            return None
        return {
            "label": "Disburse loan",
            "url": reverse('workspace_loans:pawn_loan_disburse', args=[loan.workspace.slug, loan.pk]),
            "message": "Record disbursal to activate the loan.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        if context.get("is_opening"):
            if not context.get("can_release"):
                return None
            return {"label": "Collect and release", "url": reverse(
                'workspace_loans:pawn_loan_release_full', args=[loan.workspace.slug, loan.pk]),
                "message": "Review the amount to collect, record any interest concession and return the collateral."}
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
            "reversed_by_event", "loan__workspace", "created_by"
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
