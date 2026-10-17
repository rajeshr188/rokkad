"""Pawn reads; existing services own business rules."""

from apps.subscriptions.access_policy import workspace_activity

from django.core.exceptions import (
    ObjectDoesNotExist,
    PermissionDenied,
    ValidationError,
)
from django.db.models import Q
from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
from django.utils.http import content_disposition_header
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
from apps.tenant_apps.loans.selectors.directory import loan_directory_page
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
@require_GET
@never_cache
@vary_on_headers("HX-Request", "HX-Target", "HX-History-Restore-Request", "HX-Boosted")
def pawn_loan_list(request):
    export_format = request.GET.get("export")
    if export_format is not None:
        request.loans_workspace_access.require("report.export")
        if export_format != "xlsx":
            return HttpResponse(
                "Choose Excel (xlsx) for the filtered loan export.", status=400
            )
    loans = (
        PawnLoan.objects.filter(workspace=request.loans_workspace)
        .select_related("borrower", "license", "series")
        .prefetch_related("series__number_sequences")
        .order_by("-created_at", "-pk")
    )
    loan_filter = PawnLoanFilter(
        request.GET,
        queryset=loans,
        workspace=request.loans_workspace,
    )
    valid = loan_filter.is_valid()
    if export_format:
        if not valid:
            return HttpResponse(
                "Correct the loan filters before exporting.", status=400
            )
        from apps.tenant_apps.loans.services.directory_export import (
            export_loan_directory,
        )

        today = timezone.localdate()
        content = export_loan_directory(
            workspace=request.loans_workspace, loan_filter=loan_filter, as_of_date=today
        )
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = content_disposition_header(
            True, f"filtered-loans-{today}.xlsx"
        )
        return response
    page_obj, historical_mapping_filter = loan_directory_page(
        workspace_id=request.loans_workspace.pk,
        loan_filter=loan_filter,
        page=request.GET.get("page"),
    )
    fragment = (
        request.headers.get("HX-Request") == "true"
        and request.headers.get("HX-Target") == "loan-results"
        and request.headers.get("HX-History-Restore-Request") != "true"
        and request.headers.get("HX-Boosted") != "true"
    )
    readiness = None if fragment else get_pawn_draft_readiness(request.loans_workspace)
    active_rows = [
        row
        for row in page_obj.object_list
        if row["kind"] == "ordinary" and row["loan"].state == "ACTIVE"
    ]
    show_amounts = (
        request.GET.get(
            "amounts",
            (
                "1"
                if request.GET.get("borrower")
                or (request.GET.get("q") and len(active_rows) <= 3)
                else "0"
            ),
        )
        == "1"
    )
    if show_amounts:
        from apps.tenant_apps.loans.selectors.servicing_contract import (
            get_servicing_position,
        )

        for row in active_rows:
            try:
                row["collection_position"] = get_servicing_position(
                    row["loan"], as_of_date=timezone.localdate()
                )
            except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
                row["collection_error"] = str(exc)
    context = {
        "loans": [r["loan"] for r in page_obj.object_list if r["kind"] == "ordinary"],
        "directory_rows": page_obj.object_list,
        "historical_mapping_filter": historical_mapping_filter,
        "has_retained_source_rows": any(
            r["kind"] == "historical" for r in page_obj.object_list
        ),
        "loan_filter": loan_filter,
        "selected_borrower": (
            loan_filter.form.cleaned_data.get("borrower") if valid else None
        ),
        "page_obj": page_obj,
        "can_export": request.loans_workspace_access.can("report.export"),
        "show_amounts": show_amounts,
        "amounts_date": timezone.localdate(),
        "can_collect": workspace_activity(request.loans_workspace).can_write
        and request.loans_workspace_access.can("loan.repay"),
        "applied_scope_filters": [],
    }
    if valid:
        for key in (
            "borrower",
            "state",
            "records",
            "license",
            "series",
            "loan_date_from",
            "loan_date_to",
        ):
            value = loan_filter.form.cleaned_data.get(key)
            if value:
                field = loan_filter.form.fields[key]
                label = (
                    dict(field.choices).get(value, value)
                    if key in {"records", "state"}
                    else getattr(value, "display_name", None)
                    or getattr(value, "pawn_display_name", None)
                    or getattr(value, "license_number", None)
                    or value
                )
                context["applied_scope_filters"].append(f"{field.label}: {label}")
    if not fragment:
        context.update(
            {
                "readiness": readiness,
                "can_create_loans": workspace_activity(
                    request.loans_workspace
                ).can_write
                and request.loans_workspace_access.can("data.create"),
                "can_review_paper_backlog": request.loans_workspace_access.can(
                    "data.edit"
                ),
                "more_filters_open": any(
                    request.GET.get(key)
                    for key in ("license", "series", "loan_date_from", "loan_date_to")
                ),
                "can_manage_loan_setup": request.loans_workspace_access.can(
                    "workspace.settings.manage"
                ),
            }
        )
    response = render(
        request,
        "loans/pawn/list.html#results" if fragment else "loans/pawn/list.html",
        context,
    )
    if fragment:
        response["X-Rokkad-Fragment"] = "loan-results"
    return response


@loans_workspace_required
@never_cache
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if loan.is_imported_closed_position:
        from datetime import date
        from apps.tenant_apps.loans.services.closed_position import read_position
        from apps.tenant_apps.loans.selectors.archive import historical_loan_details

        position = read_position(loan)
        evidence = loan.historical_import.archive_evidence
        return render(
            request,
            "loans/pawn/closed_position_detail.html",
            dict(
                loan=loan,
                position=position,
                position_as_of=date.fromisoformat(position["position"]["as_of"]),
                closed_on=(
                    date.fromisoformat(position["loan"]["closed_on"])
                    if position["loan"]["closed_on"]
                    else None
                ),
                returned=position["position"]["custody"] == "RETURNED_TO_BORROWER",
                source_details=(
                    historical_loan_details(position["retained_evidence"])
                    if evidence
                    else None
                ),
                evidence=evidence,
                attachments=(
                    evidence.attachments.filter(workspace_id=loan.workspace_id)
                    if evidence
                    else ()
                ),
                can_export=(
                    request.loans_workspace_access.can("workspace.settings.manage")
                    and request.loans_workspace_access.can("data.export")
                ),
            ),
        )
    opening = next(
        (
            event
            for event in loan.loan_events.all()
            if event.event_kind == "MIGRATION_OPENING"
        ),
        None,
    )
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
        "auctions": loan.auctions.select_related("loan_event").order_by(
            "-attempt_number"
        ),
        "renewals": PawnLoanRenewal.objects.filter(
            Q(source_loan=loan) | Q(successor_loan=loan)
        ).select_related(
            "source_loan",
            "successor_loan",
            "settlement_event",
            "opening_event",
        ),
    }
    approval = max(
        loan.approval_snapshots.all(), key=lambda row: row.version, default=None
    )
    from apps.tenant_apps.loans.selectors.recorded_settlements import (
        restated_release,
        restated_renewal,
    )

    context["renewals"] = [restated_renewal(row) for row in context["renewals"]]
    context["releases"] = [restated_release(row) for row in loan.releases.all()]
    context["latest_approval"] = approval
    from .portable_documents import source_copies

    context["source_document_copies"] = source_copies(loan)
    from apps.tenant_apps.loans.services.valuation_review import (
        valuation_refresh_reason,
    )

    context["valuation_refresh_reason"] = valuation_refresh_reason(loan, approval)
    from apps.tenant_apps.loans.services.completed_payouts import (
        completed_payout_adapter,
    )

    adapter = completed_payout_adapter(loan)
    actions = (
        ("workspace.settings.manage", "data.edit", "loan.approve", "loan.disburse")
        if adapter == "RETAINED_NATIVE"
        else ("data.create", "data.edit", "loan.disburse")
    )
    context["can_record_completed_payout"] = adapter is not None and all(
        request.loans_workspace_access.can(action) for action in actions
    )
    context["completed_payout_blockers"] = ()
    if context["can_record_completed_payout"] and adapter == "RECORDED":
        from apps.tenant_apps.loans.services.completed_payouts import (
            completed_payout_profile_blockers,
        )

        context["completed_payout_blockers"] = completed_payout_profile_blockers(loan)
        context["can_record_completed_payout"] = not context[
            "completed_payout_blockers"
        ]
    if context.get("can_administer") and loan.state in {"ACTIVE", "CLOSED"}:
        if opening is not None:
            from apps.tenant_apps.loans.services.opening_corrections import (
                opening_correction_blockers,
            )

            context["financial_correction_blockers"] = opening_correction_blockers(loan)
        else:
            from apps.tenant_apps.loans.services.agreement_corrections import (
                correction_dependencies,
            )

            context["financial_correction_blockers"] = correction_dependencies(loan)[2]
        context["show_financial_correction_support"] = True
    context["can_correct_origination"] = False
    context["collateral_corrections"] = (
        loan.change_log.filter(event_kind="COLLATERAL_CORRECTED")
        .select_related("actor")
        .order_by("pk")
    )
    context["agreement_corrections"] = []
    for log in (
        loan.change_log.filter(
            Q(metadata__agreement_correction__isnull=False)
            | Q(metadata__history_correction__operation="CONTRACT")
        )
        .select_related("actor")
        .order_by("pk")
    ):
        evidence = (
            log.metadata.get("agreement_correction")
            or log.metadata["history_correction"]
        )
        context["agreement_corrections"].append(
            dict(
                log=log,
                reference=evidence.get("reference")
                or log.metadata.get("review", {}).get("reference"),
                review=evidence.get("review") or log.metadata.get("review", {}),
            )
        )
    if loan.state == "DRAFT" and all(
        request.loans_workspace_access.can(action)
        for action in (
            "workspace.settings.manage",
            "data.create",
            "data.edit",
            "loan.disburse",
        )
    ):
        from apps.tenant_apps.loans.services.origination_corrections import (
            correction_source,
        )

        try:
            correction_source(loan, actor=request.user)
        except ValueError, PermissionDenied:
            pass
        else:
            context["can_correct_origination"] = True
            context["can_record_completed_payout"] = False
    from apps.tenant_apps.loans.services.recorded_collections import recording_for

    recorded_contract = recording_for(loan)
    context["can_print_ticket"] = loan.state != "DRAFT" and (
        approval is not None or recorded_contract is not None
    )
    context["ticket_is_recorded"] = recorded_contract is not None
    context["can_preview_imported_ticket"] = opening is not None and approval is None
    context["can_print_schedule"] = loan.repayment_schedules.exists()
    if loan.state in {"DRAFT", "APPROVED"}:
        try:
            if loan.state == "DRAFT":
                if not (
                    context["can_record_completed_payout"]
                    and loan.loan_date < context["today"]
                ):
                    context["economics"], _token = make_review(loan)
            else:
                context["economics"] = preview_approved_disbursal(loan)
        except (ValidationError, ValueError) as exc:
            context["review_error"] = str(exc)
    from apps.tenant_apps.loans.services.origination_settings import (
        maximum_quote_age_days,
    )

    context["maximum_quote_age_days"] = maximum_quote_age_days(loan.workspace_id)
    if approval:
        evidence = approval.payload.get("origination_rates", {})
        from apps.tenant_apps.loans.selectors.origination_rates import LEGACY_RULE

        context["approved_quote_age_limit"] = (
            0
            if evidence.get("rule") == LEGACY_RULE
            else evidence.get("maximum_quote_age_days")
        )
        context["approved_quote_rows"] = [
            dict(
                quote,
                effective_time=parse_datetime(quote["effective_at"]),
                age_at_approval=evidence.get("quote_ages_days", {}).get(metal),
            )
            for metal, quote in evidence.get("quotes", {}).items()
        ]
    financial_inputs = None
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value}:
        from apps.tenant_apps.loans.selectors.financial_inputs import (
            get_pawn_loan_financial_inputs,
        )

        try:
            financial_inputs = get_pawn_loan_financial_inputs(
                loan.pk, as_of_date=context["today"]
            )
        except ObjectDoesNotExist, ValidationError, ValueError:
            pass  # Narrower recorded/collection reads can still be supported.
        try:
            context["balance"] = (
                financial_inputs.balance
                if financial_inputs is not None
                else get_pawn_loan_balance(
                    loan.pk,
                    as_of_date=context["today"],
                )
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["balance_error"] = str(exc)
        try:
            context["exposure"] = get_pawn_loan_exposure(
                loan.pk,
                as_of_date=context["today"],
                financial_inputs=financial_inputs,
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["exposure_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        from apps.tenant_apps.loans.selectors.servicing_contract import (
            get_servicing_position,
        )

        try:
            context["collection_position"] = get_servicing_position(
                loan, as_of_date=context["today"], financial_inputs=financial_inputs
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["collection_error"] = str(exc)
        try:
            context["delinquency"] = get_pawn_loan_delinquency(
                loan.pk, as_of_date=context["today"], financial_inputs=financial_inputs
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["risk_error"] = str(exc)
        try:
            context["collateral_valuation"] = get_pawn_loan_collateral_valuation(
                loan.pk, as_of_date=context["today"], _exposure=context.get("exposure")
            )
        except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
            context["risk_error"] = str(exc)
            from apps.tenant_apps.loans.selectors.collateral_valuation import (
                get_pawn_loan_collateral_observation,
            )

            try:
                context["collateral_observation"] = (
                    get_pawn_loan_collateral_observation(
                        loan.pk, as_of_date=context["today"]
                    )
                )
            except ObjectDoesNotExist, ValidationError, ValueError:
                pass  # The reported failure remains visible; no value is invented.
        try:
            context["risk_assessment"] = get_pawn_loan_risk_assessment(
                loan.pk,
                as_of_date=context["today"],
                _exposure=context.get("exposure"),
                _delinquency=context.get("delinquency"),
                _collateral=context.get("collateral_valuation"),
                financial_inputs=financial_inputs,
            )
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
        from apps.tenant_apps.loans.services.servicing_eligibility import (
            servicing_eligibility,
        )

        context["renewal_eligibility"] = servicing_eligibility(
            loan,
            operation="RENEWAL",
            purpose="CURRENT",
            effective_date=context["today"],
        )
        context["auction_eligibility"] = servicing_eligibility(
            loan,
            operation="AUCTION",
            purpose="CURRENT",
            effective_date=context["today"],
        )
        context["can_renew"] = (
            context["can_renew"] and context["renewal_eligibility"].ready
        )
    context["can_send_notice"] = request.loans_workspace_access.can("data.edit")
    context["can_edit_loan"] = request.loans_workspace_access.can("data.edit")
    context["can_split_draft"] = context[
        "can_edit_loan"
    ] and request.loans_workspace_access.can("data.create")
    context["can_delete_draft_photos"] = (
        loan.state == "DRAFT" and request.loans_workspace_access.can("data.edit")
    )
    if loan.state == "DRAFT":
        from apps.tenant_apps.loans.services.origination_settings import (
            collateral_photos_required,
        )

        context["photos_required"] = collateral_photos_required(loan.workspace_id)
    context["can_approve"] = request.loans_workspace_access.can("loan.approve")
    context["can_reappraise"] = (
        loan.state == "ACTIVE" and context["can_approve"] and context["can_edit_loan"]
    )
    current_appraisals = {}
    valuation_read = context.get("collateral_valuation") or context.get(
        "collateral_observation"
    )
    appraisal_cutoff = (
        valuation_read.evidence_at if valuation_read is not None else timezone.now()
    )
    from apps.tenant_apps.loans.services.collateral_corrections import (
        invalidated_appraisal_versions,
    )

    invalidated_appraisals = invalidated_appraisal_versions(loan)
    for appraisal in CollateralAppraisal.objects.filter(
        workspace=request.loans_workspace,
        collateral_item__loan=loan,
        status="APPROVED",
        effective_at__lte=appraisal_cutoff,
    ).order_by("-effective_at", "-version"):
        if appraisal.version <= invalidated_appraisals.get(
            appraisal.collateral_item_id, -1
        ):
            continue
        current_appraisals.setdefault(appraisal.collateral_item_id, appraisal)
    for item in loan.collateral_items.all():
        item.current_appraisal = current_appraisals.get(item.pk)
    context["can_disburse"] = request.loans_workspace_access.can("loan.disburse")
    from apps.tenant_apps.loans.services.recorded_collections import (
        recording_for,
        collection_balance,
    )

    recorded = recording_for(loan)
    from apps.tenant_apps.loans.selectors.transaction_completeness import (
        transaction_completeness,
    )

    context["transaction_completeness"] = transaction_completeness(
        loan, context["today"]
    )
    if loan.state in ("ACTIVE", "CLOSED"):
        from apps.tenant_apps.loans.selectors.evidence_quality import (
            loan_evidence_quality,
        )
        from apps.tenant_apps.loans.selectors.transaction_coverage import (
            recorded_position_coverage,
        )

        coverage = recorded_position_coverage(
            loan,
            context["today"],
            book_review=context["transaction_completeness"],
            servicing_position=context.get("collection_position"),
        )
        context["evidence_quality"] = loan_evidence_quality(
            loan,
            as_of_date=context["today"],
            exposure=context.get("exposure"),
            observation=context.get("collateral_valuation")
            or context.get("collateral_observation"),
            risk=context.get("risk_assessment"),
            live_error=context.get("risk_error", ""),
            transaction_coverage=coverage,
        )
    context["can_review_transactions"] = request.loans_workspace_access.can(
        "data.edit"
    ) and loan.state in ("ACTIVE", "CLOSED")
    context["can_confirm_paper_handover"] = (
        loan.state == "CLOSED"
        and request.loans_workspace_access.can("loan.release")
        and loan.collateral_items.filter(custody_state="PAPER_CLOSED").exists()
    )
    from apps.tenant_apps.loans.services.servicing_eligibility import (
        servicing_eligibility,
    )

    context["can_record_paper_closure"] = (
        loan.state == "ACTIVE"
        and context["can_release"]
        and servicing_eligibility(
            loan,
            operation="FULL_RELEASE",
            purpose="PAPER",
            effective_date=context["today"],
        ).ready
    )
    if recorded:
        context["recorded_history"] = recorded
        context["can_correct_paper_closing"] = (
            loan.state == "CLOSED" and loan.releases.exists()
        )
        context["source_history"] = (
            loan.historical_import.document.get("loan")
            if hasattr(loan, "historical_import")
            else None
        )
        context["archive_admission"] = (
            loan.historical_import
            if hasattr(loan, "historical_import")
            and loan.historical_import.archive_evidence_id
            else None
        )
        context["can_print_schedule"] = True
        context["can_print_ticket"] = True
        for action in ("accrue", "capitalize", "send_notice"):
            context["can_" + action] = False
        if loan.state == "ACTIVE":
            context["recorded_collection_balance"] = collection_balance(
                loan, context["today"]
            )
    if opening:
        context["is_opening"] = True
        for action in ("accrue", "capitalize"):
            context["can_" + action] = False
        from apps.tenant_apps.loans.services.opening_evidence import (
            read_opening_evidence,
        )

        try:
            review = read_opening_evidence(loan, opening)["review"]
            context["opening_review"] = review
            if review["profile"] == "loan-terminal-review/1":
                context["terminal_position"] = review
                context["can_confirm_paper_handover"] = False
                context["can_review_transactions"] = False
                context["can_print_schedule"] = False
            if loan.state == PawnLoanState.ACTIVE.value:
                from apps.tenant_apps.loans.services.opening_continuation import (
                    opening_interest_breakdown,
                )

                context["opening_interest_breakdown"] = opening_interest_breakdown(
                    review, as_of_date=context["today"], loan=loan
                )
            context["opening_source_valuations"] = [
                row
                for row in review["collateral"]
                if row.get("valuation", {}).get("status") == "UNVERIFIED"
            ]
        except ValueError as exc:
            context["balance_error"] = str(exc)
        if loan.state == PawnLoanState.ACTIVE.value:
            from apps.tenant_apps.loans.services.pawn_release import (
                preview_pawn_loan_full_release,
            )

            try:
                context["collection_quote"] = preview_pawn_loan_full_release(loan.pk)
            except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
                context["collection_error"] = str(exc)
    context["simple_owner"] = (
        request.loans_workspace.loan_workflow == "SIMPLE"
        and request.loans_workspace_access.can("workspace.transfer")
    )
    if not workspace_activity(request.loans_workspace).can_write:
        for key in tuple(context):
            if key.startswith("can_") and key not in {
                "can_print_ticket",
                "can_print_schedule",
            }:
                context[key] = False
        context["simple_owner"] = False
        # Rebuild reversal controls after removing mutation permission.
        context["event_rows"] = _event_rows(loan, can_administer=False)
    context["repayment_rows"] = [
        row
        for row in context["event_rows"]
        if row["event"].event_kind == TransactionKind.REPAYMENT.value
    ]
    context["current_disbursal"] = next(
        (
            row["event"]
            for row in context["event_rows"]
            if row["event"].event_kind == "DISBURSAL" and not row["reversed_event"]
        ),
        None,
    )
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        if (
            context.get("can_record_completed_payout")
            and loan.loan_date < context["today"]
        ):
            return {
                "label": "Record completed payout",
                "url": reverse(
                    "workspace_loans:pawn_loan_record_completed_payout",
                    args=[loan.workspace.slug, loan.pk],
                ),
                "message": "If the money was already paid, record the actual agreement against this draft. If still unpaid, correct the intended payment date before approval.",
            }
        if context.get("simple_owner"):
            return {
                "label": "Review and disburse",
                "url": reverse(
                    "workspace_loans:pawn_loan_review_disburse",
                    args=[loan.workspace.slug, loan.pk],
                ),
                "message": "Review the summary and confirm payment in one action.",
            }
        if not context.get("can_approve", False):
            return None
        return {
            "label": "Approve loan",
            "url": reverse(
                "workspace_loans:pawn_loan_approve", args=[loan.workspace.slug, loan.pk]
            ),
            "method": "post",
            "message": _(
                "Check the customer, collateral photos and amounts below. Approval saves the terms; payment is recorded separately."
            ),
        }
    if loan.state == PawnLoanState.APPROVED.value:
        if context.get("valuation_refresh_reason") and (
            context.get("can_approve") or context.get("can_disburse")
        ):
            return {
                "label": "Review updated valuation",
                "url": reverse(
                    "workspace_loans:pawn_loan_review_updated_valuation",
                    args=[loan.workspace.slug, loan.pk],
                ),
                "message": "Cash not yet paid? Compare the approved prices with today's prices and review the terms before payment. If cash was already paid earlier, keep the actual date and use Record completed payout.",
            }
        if not context.get("can_disburse", False):
            return None
        return {
            "label": "Disburse loan",
            "url": reverse(
                "workspace_loans:pawn_loan_disburse",
                args=[loan.workspace.slug, loan.pk],
            ),
            "message": "Record disbursal to activate the loan.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        if context.get("is_opening"):
            if not context.get("can_release"):
                return None
            return {
                "label": "Close / release loan",
                "url": reverse(
                    "workspace_loans:pawn_loan_close",
                    args=[loan.workspace.slug, loan.pk],
                ),
                "message": "Collect and return collateral now, or record a settlement already completed.",
            }
        if not context.get("can_repay", False):
            return None
        return {
            "label": "Record repayment",
            "url": reverse(
                "workspace_loans:pawn_loan_repay", args=[loan.workspace.slug, loan.pk]
            ),
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
        readiness = (
            assess_pawn_loan_event_reversal(event, latest_event_id=latest_event_id)
            if can_administer
            else None
        )
        rows.append(
            {
                "event": event,
                "can_reverse": bool(readiness and readiness.can_reverse),
                "reversal_blocker": readiness.blocker if readiness else "",
                "reversed_event": reversed_event,
            }
        )
    return rows
