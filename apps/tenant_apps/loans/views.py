import uuid
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.domain import (
    LoanDocumentKind,
    LoanOutboxStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.feature_flags import (
    get_loan_module_feature_state,
    set_new_loans_enabled,
)
from apps.tenant_apps.loans.forms import (
    LoanLicenseForm,
    LoanModuleFeatureGateForm,
    LoanSeriesSetupForm,
    PawnEconomicConfigurationForm,
    PawnFeePolicyForm,
    PawnAccrualForm,
    PawnAdditionalCollateralFormSet,
    PawnCapitalizationForm,
    PawnCollateralDraftFormSet,
    PawnDisbursalForm,
    PawnDraftForm,
    PawnFullReleaseForm,
    PawnLoanNoticeForm,
    PawnAuctionInitiateForm,
    PawnAuctionCompletionForm,
    PawnRenewalForm,
    PawnRenewalRetainedItemFormSet,
    PawnRepaymentForm,
    PawnReversalForm,
    PawnSetupTransferForm,
    PawnTransitionReasonForm,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanSeries,
    PawnLoanEconomicPolicy,
    PawnLoanFeePolicy,
    PawnMetalInterestRatePolicy,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanNotice,
    PawnLoanAuction,
    PawnLoanRenewal,
    PawnLoanRelease,
)
from apps.tenant_apps.loans.selectors import (
    get_pawn_loan_balance,
    get_pawn_loan_notice_rows,
    get_pawn_loan_operations_snapshot,
    get_pawn_loan_release_readiness,
    get_pawn_loan_reports,
    get_unified_loan_portfolio,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    LicenseSeriesError,
    LoanAccountingOutboxError,
    NumberAllocationError,
    PawnBorrowerAccountingSetupError,
    PawnDraftError,
    PawnLifecycleError,
    PawnLoanDocumentError,
    PawnLoanDocumentService,
    PawnLoanNoticeError,
    PawnAuctionError,
    PawnRenewalError,
    RetainedCollateralInput,
    UpdatePawnDraftCommand,
    activate_license,
    approve_pawn_loan,
    assess_pawn_loan_accounting_readiness,
    cancel_pawn_loan,
    capitalize_pawn_loan_interest,
    configure_sequence,
    create_license,
    create_pawn_draft,
    create_pawn_loan_economic_policy,
    create_pawn_loan_fee_policy,
    create_pawn_metal_interest_rate_policy,
    create_pawn_loan_notice,
    create_series,
    disburse_pawn_loan,
    dispatch_pawn_loan_notice,
    ensure_pawn_borrower_accounting,
    initiate_pawn_loan_auction,
    start_pawn_loan_auction,
    cancel_pawn_loan_auction,
    complete_pawn_loan_auction,
    reverse_pawn_loan_auction,
    renew_pawn_loan,
    reverse_pawn_loan_renewal,
    expire_license,
    finalize_pawn_loan_accrual,
    preview_number,
    preview_pawn_loan_accruals,
    record_pawn_loan_repayment,
    resolve_pawn_draft_economics,
    resolve_pawn_loan_economic_policy,
    resolve_pawn_metal_interest_rate_policy,
    release_pawn_loan_in_full,
    reopen_pawn_loan,
    retry_failed_outbox_event,
    reverse_pawn_loan_event,
    set_series_active,
    transfer_expired_draft_setup,
    update_license,
    update_pawn_draft,
    update_series,
)
from apps.tenant_apps.loans.services.pawn_tranches import (
    PawnTrancheBalanceError,
    get_pawn_principal_tranche_balances,
)


@loans_workspace_required
def pawn_loan_list(request):
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace).select_related(
        "borrower", "license", "series"
    ).order_by("-created_at")
    readiness = _draft_readiness(request.loans_workspace)
    return render(request, "loans/pawn/list.html", {"loans": loans, "readiness": readiness})


@loans_workspace_required
def pawn_loan_reports(request):
    report = get_pawn_loan_reports(as_of_date=timezone.localdate())
    return render(
        request,
        "loans/pawn/reports.html",
        {"report": report, "can_administer": _can_administer(request)},
    )


@loans_workspace_required
def unified_loan_portfolio(request):
    portfolio = get_unified_loan_portfolio(as_of_date=timezone.localdate())
    return render(
        request,
        "loans/pawn/coexistence.html",
        {"portfolio": portfolio},
    )


@loans_setup_required
def loan_module_feature_gate(request):
    state = get_loan_module_feature_state(request.loans_workspace)
    form = LoanModuleFeatureGateForm(
        request.POST if request.method == "POST" else None,
        initial={"enabled": state.enabled},
    )
    if request.method == "POST" and form.is_valid():
        state = set_new_loans_enabled(
            request.loans_workspace,
            enabled=form.cleaned_data["enabled"],
            actor=request.user,
        )
        if state.enabled:
            messages.success(
                request,
                "Loans is now the new-loan entrypoint. Existing Girvi loans remain serviceable in Girvi.",
            )
        else:
            messages.success(
                request,
                "Girvi is again the new-loan entrypoint. Existing Loans records were preserved.",
            )
        return redirect("loans:loan_module_feature_gate")
    return render(
        request,
        "loans/setup/feature_gate.html",
        {"form": form, "feature_state": state},
    )


@loans_workspace_required
def pawn_loan_ticket_pdf(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        result = PawnLoanDocumentService.render_loan_ticket(loan)
    except PawnLoanDocumentError as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_repayment_receipt_pdf(request, pk, event_pk):
    event = get_object_or_404(
        PawnLoanAccountingEvent.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "outbox",
            "reversed_by_event",
        ),
        pk=event_pk,
        loan_id=pk,
        loan__workspace=request.loans_workspace,
        event_kind=TransactionKind.REPAYMENT.value,
    )
    return PawnLoanDocumentService.build_pdf_response(
        PawnLoanDocumentService.render_repayment_receipt(event)
    )


@loans_workspace_required
def pawn_release_memo_pdf(request, release_pk):
    release = get_object_or_404(
        PawnLoanRelease.objects.select_related(
            "workspace",
            "loan",
            "loan__license",
            "loan__borrower",
            "accounting_event",
            "accounting_event__outbox",
            "reversal",
        ).prefetch_related("items__collateral_item"),
        pk=release_pk,
        workspace=request.loans_workspace,
    )
    return PawnLoanDocumentService.build_pdf_response(
        PawnLoanDocumentService.render_release_memo(release)
    )


@loans_workspace_required
def pawn_loan_create(request):
    readiness = _draft_readiness(request.loans_workspace)
    if not readiness["ready"]:
        return render(request, "loans/pawn/blocked.html", {"readiness": readiness})
    initial = {"loan_date": timezone.localdate()}
    if request.method == "GET" and request.GET.get("party"):
        initial["borrower"] = request.GET["party"]
    form = PawnDraftForm(
        request.POST or None,
        workspace=request.loans_workspace,
        initial=initial,
    )
    formset = PawnCollateralDraftFormSet(request.POST or None, prefix="collateral")
    economics_preview = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        command = _create_command(request.loans_workspace.pk, form, formset)
        try:
            if request.POST.get("action") == "preview":
                economics_preview = resolve_pawn_draft_economics(
                    workspace_id=request.loans_workspace.pk,
                    license_id=command.license_id,
                    as_of_date=command.loan_date,
                    collateral=command.collateral,
                )
                loan = None
            else:
                loan = create_pawn_draft(command, actor=request.user)
        except (PawnDraftError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            if loan is not None:
                messages.success(request, f"Draft {loan.loan_number} created.")
                return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/form.html",
        {"form": form, "formset": formset, "economics_preview": economics_preview},
    )


@loans_workspace_required
def pawn_loan_update(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if loan.state != PawnLoanState.DRAFT.value:
        messages.error(request, "Only draft PawnLoans can be edited.")
        return redirect("loans:pawn_loan_detail", pk=loan.pk)
    form = PawnDraftForm(request.POST or None, workspace=request.loans_workspace, instance=loan)
    initial = [
        {
            "description": item.description,
            "metal": item.metal,
            "gross_weight": item.gross_weight,
            "net_weight": item.net_weight,
            "purity_percentage": item.purity_percentage,
            "latest_appraised_value": item.latest_appraised_value,
            "allocated_principal": item.allocated_principal,
        }
        for item in loan.collateral_items.all()
    ]
    formset = PawnCollateralDraftFormSet(
        request.POST or None, prefix="collateral", initial=None if request.method == "POST" else initial
    )
    economics_preview = None
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        command = _update_command(form, formset)
        try:
            if request.POST.get("action") == "preview":
                economics_preview = resolve_pawn_draft_economics(
                    workspace_id=request.loans_workspace.pk,
                    license_id=loan.license_id,
                    as_of_date=command.loan_date,
                    collateral=command.collateral,
                )
            else:
                update_pawn_draft(loan.pk, command, actor=request.user)
        except (PawnDraftError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            if request.POST.get("action") != "preview":
                messages.success(request, f"Draft {loan.loan_number} updated.")
                return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/form.html",
        {
            "form": form,
            "formset": formset,
            "loan": loan,
            "economics_preview": economics_preview,
        },
    )


@loans_workspace_required
def pawn_loan_detail(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    context = {
        "loan": loan,
        "today": timezone.localdate(),
        "can_administer": _can_administer(request),
        "notice_rows": get_pawn_loan_notice_rows(loan),
        "auctions": loan.auctions.select_related("accounting_event__outbox").order_by("-attempt_number"),
        "renewals": PawnLoanRenewal.objects.filter(
            Q(source_loan=loan) | Q(successor_loan=loan)
        ).select_related(
            "source_loan",
            "successor_loan",
            "settlement_event__outbox",
            "opening_event__outbox",
        ),
    }
    if loan.state in {PawnLoanState.ACTIVE.value, PawnLoanState.CLOSED.value}:
        try:
            context["balance"] = get_pawn_loan_balance(
                loan.pk,
                as_of_date=context["today"],
            )
        except (ValidationError, ValueError) as exc:
            context["balance_error"] = str(exc)
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            context["accrual_previews"] = preview_pawn_loan_accruals(
                loan.pk,
                as_of_date=context["today"],
                include_partial=True,
            )
        except (ValidationError, ValueError) as exc:
            context["accrual_error"] = str(exc)
    context["accounting_rows"] = _accounting_rows(
        loan,
        can_administer=context["can_administer"],
    )
    context["primary_action"] = _primary_action(loan, context)
    return render(request, "loans/pawn/detail.html", context)


@loans_workspace_required
@require_POST
def pawn_loan_approve(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        approve_pawn_loan(loan.pk, actor=request.user)
        messages.success(request, f"{loan.loan_number} approved. Its economic payload is frozen.")
    except (PawnLifecycleError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect("loans:pawn_loan_detail", pk=loan.pk)


@loans_workspace_required
def pawn_loan_reopen(request, pk):
    return _reason_transition(request, pk, "reopen")


@loans_workspace_required
def pawn_loan_cancel(request, pk):
    return _reason_transition(request, pk, "cancel")


@loans_workspace_required
def pawn_loan_disburse(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnDisbursalForm(
        request.POST or None,
        initial={"effective_date": timezone.localdate()},
    )
    if request.method == "POST" and form.is_valid():
        try:
            disburse_pawn_loan(
                loan.pk,
                effective_date=form.cleaned_data["effective_date"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{loan.loan_number} disbursed and queued for accounting.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    readiness = None
    readiness_error = ""
    effective_date = (
        form.cleaned_data.get("effective_date")
        if form.is_bound and form.is_valid()
        else timezone.localdate()
    )
    try:
        readiness = assess_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
        )
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        readiness_error = str(exc)
    return _render_action(
        request,
        loan,
        form,
        "Disburse loan",
        "This posts the approved principal through DEA and activates the loan.",
        {
            "accounting_readiness": readiness,
            "accounting_readiness_error": readiness_error,
            "can_administer": _can_administer(request),
        },
    )


@loans_setup_required
def pawn_borrower_account_setup(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    if request.method == "POST":
        try:
            result = ensure_pawn_borrower_accounting(
                loan.pk,
                actor=request.user,
                request=request,
            )
        except PawnBorrowerAccountingSetupError as exc:
            messages.error(request, str(exc))
        else:
            if result.mapping_created:
                messages.success(
                    request,
                    f"Borrower accounting account {result.account} is ready.",
                )
            else:
                messages.info(request, "The borrower accounting mapping was already ready.")
            return redirect("loans:pawn_loan_disburse", pk=loan.pk)
    return render(
        request,
        "loans/pawn/borrower_account_setup.html",
        {"loan": loan},
    )


@loans_workspace_required
def pawn_loan_repay(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnRepaymentForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            result = record_pawn_loan_repayment(
                loan.pk,
                amount=form.cleaned_data["amount"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Repayment {result.allocation.amount_received} recorded and queued.",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    balance = _safe_balance(loan)
    return _render_action(
        request,
        loan,
        form,
        "Record repayment",
        "Allocation is fixed: fees, overdue interest, current interest, then principal.",
        {"balance": balance},
    )


@loans_workspace_required
def pawn_loan_accrue(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    previews = _safe_accrual_previews(loan, include_partial=False)
    initial = {"period_number": previews[0].period_number} if previews else None
    form = PawnAccrualForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            finalize_pawn_loan_accrual(
                loan.pk,
                period_number=form.cleaned_data["period_number"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Interest accrual finalized and queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Finalize interest accrual",
        "Only the next eligible completed monthly period can be finalized.",
        {"previews": previews},
    )


@loans_workspace_required
def pawn_loan_capitalize(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnCapitalizationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            capitalize_pawn_loan_interest(
                loan.pk,
                through_period_number=form.cleaned_data["through_period_number"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Interest capitalization recorded and queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Capitalize interest",
        "Available only at the snapshotted compound-interest boundary.",
    )


@loans_workspace_required
def pawn_loan_release_full(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    quote = _full_release_quote(loan)
    initial = {"request_key": uuid.uuid4().hex}
    minimum_settlement = (
        quote.get("minimum_settlement")
        if isinstance(quote, dict)
        else quote.minimum_settlement
    )
    if minimum_settlement is not None:
        initial["settlement_amount"] = minimum_settlement
    form = PawnFullReleaseForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            release_pawn_loan_in_full(
                loan.pk,
                settlement_amount=form.cleaned_data["settlement_amount"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Full settlement and collateral return recorded.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Full release",
        "Collect the exact displayed settlement before returning all remaining collateral.",
        {"quote": quote},
    )


@loans_workspace_required
def pawn_loan_release_partial(request, pk):
    _pawn_loan_for_workspace(request, pk)
    return HttpResponseGone(
        "Partial collateral release is no longer supported. "
        "Use full release or release and renew into a newly numbered PawnLoan."
    )


@loans_workspace_required
def pawn_loan_reverse_event(request, pk, event_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    event = get_object_or_404(
        PawnLoanAccountingEvent,
        pk=event_pk,
        loan=loan,
    )
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_event(
                event.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Reversal recorded and queued through DEA.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        f"Reverse {event.get_event_kind_display()}",
        "Administrator-only. Later dependent events must be reversed first.",
        {"accounting_event": event},
    )


@loans_workspace_required
def pawn_loan_notice_create(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnLoanNoticeForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            notice = create_pawn_loan_notice(
                loan.pk,
                notice_kind=form.cleaned_data["notice_kind"],
                channel=form.cleaned_data["channel"],
                scheduled_for=form.cleaned_data.get("scheduled_for"),
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"{notice.get_notice_kind_display()} queued through Notify.",
            )
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Create loan notice",
        "Loans records notice intent; Notify owns templates, provider delivery, and attempts.",
    )


@loans_workspace_required
@require_POST
def pawn_loan_notice_retry(request, pk, notice_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    notice = get_object_or_404(
        PawnLoanNotice,
        pk=notice_pk,
        loan=loan,
        workspace=request.loans_workspace,
    )
    try:
        result = dispatch_pawn_loan_notice(notice.pk)
    except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        if result.delivery.status == "SENT":
            messages.success(request, "PawnLoan notice sent.")
        elif result.delivery.status == "FAILED":
            messages.error(
                request,
                result.delivery.failure_reason or "Notice delivery failed.",
            )
        else:
            messages.info(request, "PawnLoan notice remains queued.")
    return redirect("loans:pawn_loan_detail", pk=loan.pk)


@loans_workspace_required
def pawn_loan_auction_initiate(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnAuctionInitiateForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            auction = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=form.cleaned_data["scheduled_date"],
                channel=form.cleaned_data["channel"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} initiated and notice queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Initiate auction recovery",
        "Administrator-only. The loan must be overdue and all collateral must remain in the vault.",
    )


@loans_workspace_required
@require_POST
def pawn_loan_auction_start(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        start_pawn_loan_auction(auction.pk, actor=request.user)
    except (PawnAuctionError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Auction {auction.auction_number} started.")
    return redirect("loans:pawn_loan_detail", pk=auction.loan_id)


@loans_workspace_required
def pawn_loan_auction_cancel(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} cancelled.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Cancel auction",
        "An initiated or in-progress auction can be cancelled. A reason is required.",
        {"auction": auction},
    )


@loans_workspace_required
def pawn_loan_auction_complete(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnAuctionCompletionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_pawn_loan_auction(
                auction.pk,
                recovery_amount=form.cleaned_data["recovery_amount"],
                buyer_name=form.cleaned_data["buyer_name"],
                buyer_reference=form.cleaned_data["buyer_reference"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} completed and recovery queued through DEA.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Complete auction recovery",
        "Recovery must exactly clear the canonical debt. Shortfall and surplus workflows fail closed.",
        {"auction": auction},
    )


@loans_workspace_required
def pawn_loan_auction_reverse(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} reversed.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Reverse auction recovery",
        "Administrator-only. Accounting and custody are restored through compensating evidence.",
        {"auction": auction},
    )


@loans_workspace_required
def pawn_loan_auction_notice_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    return PawnLoanDocumentService.build_pdf_response(
        PawnLoanDocumentService.render_auction_notice(auction)
    )


@loans_workspace_required
def pawn_loan_auction_recovery_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        result = PawnLoanDocumentService.render_auction_recovery_memo(auction)
    except PawnLoanDocumentError as exc:
        return HttpResponse(str(exc), status=409)
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_renew(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    source_items = tuple(
        loan.collateral_items.filter(custody_state="IN_VAULT").order_by("pk")
    )
    try:
        current_tranches = {
            row.collateral_item_id: row.principal_outstanding
            for row in get_pawn_principal_tranche_balances(loan)
        }
    except PawnTrancheBalanceError:
        current_tranches = {}
    retained_initial = [
        {
            "collateral_item_id": item.pk,
            "retain": True,
            "allocated_principal": current_tranches.get(
                item.pk, item.allocated_principal
            ),
        }
        for item in source_items
    ]
    initial = {
        "request_key": uuid.uuid4().hex,
        "successor_license": loan.license_id,
        "successor_series": loan.series_id,
        "tenure_months": loan.tenure_months,
    }
    form = PawnRenewalForm(
        request.POST or None,
        workspace=request.loans_workspace,
        initial=initial,
    )
    retained_formset = PawnRenewalRetainedItemFormSet(
        request.POST or None,
        prefix="retained",
        initial=retained_initial,
    )
    additional_formset = PawnAdditionalCollateralFormSet(
        request.POST or None,
        prefix="additional",
    )
    balance = None
    if loan.state == PawnLoanState.ACTIVE.value:
        try:
            balance = get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
        except (ValidationError, ValueError):
            pass
    if (
        request.method == "POST"
        and form.is_valid()
        and retained_formset.is_valid()
        and additional_formset.is_valid()
    ):
        retained = tuple(
            RetainedCollateralInput(
                collateral_item_id=row["collateral_item_id"],
                allocated_principal=row["allocated_principal"],
            )
            for row in retained_formset.cleaned_data
            if row and row.get("retain")
        )
        try:
            result = renew_pawn_loan(
                loan.pk,
                mode=form.cleaned_data["mode"],
                renewal_date=timezone.localdate(),
                principal_paid=form.cleaned_data["principal_paid"],
                top_up_amount=form.cleaned_data["top_up_amount"],
                successor_license_id=form.cleaned_data["successor_license"].pk,
                successor_series_id=form.cleaned_data["successor_series"].pk,
                tenure_months=form.cleaned_data["tenure_months"],
                request_key=form.cleaned_data["request_key"],
                retained_collateral=retained,
                additional_collateral=_collateral_inputs(additional_formset),
                actor=request.user,
            )
        except (PawnRenewalError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Renewal completed. Successor loan {result.successor_loan.loan_number} is active.",
            )
            return redirect("loans:pawn_loan_detail", pk=result.successor_loan.pk)
    return render(
        request,
        "loans/pawn/release_and_renew.html",
        {
            "loan": loan,
            "form": form,
            "retained_formset": retained_formset,
            "retained_rows": tuple(zip(source_items, retained_formset.forms)),
            "additional_formset": additional_formset,
            "balance": balance,
        },
    )


@loans_workspace_required
def pawn_loan_renewal_reverse(request, renewal_pk):
    renewal = _pawn_renewal_for_workspace(request, renewal_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_renewal(
                renewal.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnRenewalError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Renewal {renewal.renewal_number} reversed.")
            return redirect("loans:pawn_loan_detail", pk=renewal.source_loan_id)
    return _render_action(
        request,
        renewal.source_loan,
        form,
        "Reverse renewal",
        "Administrator-only. The successor must have no later activity and both collateral records must remain in compatible custody.",
        {"renewal": renewal},
    )


@loans_workspace_required
def pawn_loan_renewal_pdf(request, renewal_pk):
    renewal = _pawn_renewal_for_workspace(request, renewal_pk)
    return PawnLoanDocumentService.build_pdf_response(
        PawnLoanDocumentService.render_renewal_memo(renewal)
    )


@loans_workspace_required
def pawn_loan_transfer_setup(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnSetupTransferForm(request.POST or None, workspace=request.loans_workspace)
    if request.method == "POST" and form.is_valid():
        try:
            transfer_expired_draft_setup(
                loan.pk,
                license_id=form.cleaned_data["license"].pk,
                series_id=form.cleaned_data["series"].pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnLifecycleError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Draft moved to active license setup and requires approval again.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(request, "loans/pawn/transition_form.html", {"loan": loan, "form": form, "action_label": "Transfer setup"})


@loans_setup_required
@require_POST
def pawn_outbox_retry(request, pk):
    outbox = get_object_or_404(
        PawnLoanAccountingOutbox.objects.select_related("event__loan"),
        pk=pk,
        event__loan__workspace=request.loans_workspace,
    )
    try:
        retry_failed_outbox_event(outbox.pk)
        messages.success(request, f"Accounting outbox event #{outbox.pk} queued for retry.")
    except LoanAccountingOutboxError as exc:
        messages.error(request, str(exc))
    if request.POST.get("next") == "operations":
        return redirect("loans:pawn_operations_console")
    return redirect("loans:pawn_loan_detail", pk=outbox.event.loan_id)


@loans_setup_required
def pawn_operations_console(request):
    return render(
        request,
        "loans/setup/operations_console.html",
        {"snapshot": get_pawn_loan_operations_snapshot()},
    )


@loans_setup_required
def pawn_operations_runbook(request):
    return render(request, "loans/setup/operations_runbook.html")


@loans_setup_required
def license_list(request):
    licenses = LoanLicense.objects.filter(workspace=request.loans_workspace).prefetch_related(
        "series__number_sequences"
    )
    return render(request, "loans/setup/license_list.html", {"licenses": licenses})


@loans_setup_required
def pawn_economics_setup(request):
    action = request.POST.get("action") if request.method == "POST" else None
    configuration_form = PawnEconomicConfigurationForm(
        request.POST if action == "configuration" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="configuration",
    )
    fee_form = PawnFeePolicyForm(
        request.POST if action == "fee" else None,
        workspace=request.loans_workspace,
        initial={"effective_from": timezone.localdate()},
        prefix="fee",
    )
    if action == "configuration" and configuration_form.is_valid():
        data = configuration_form.cleaned_data
        try:
            with transaction.atomic():
                create_pawn_loan_economic_policy(
                    workspace=request.loans_workspace,
                    license=data["license"],
                    valuation_method=data["valuation_method"],
                    maximum_ltv_ratio=data["maximum_ltv_ratio"],
                    advance_interest_periods=data["advance_interest_periods"],
                    effective_from=data["effective_from"],
                    actor=request.user,
                )
                for metal, rate in (
                    ("GOLD", data["gold_monthly_interest_rate"]),
                    ("SILVER", data["silver_monthly_interest_rate"]),
                ):
                    create_pawn_metal_interest_rate_policy(
                        workspace=request.loans_workspace,
                        license=data["license"],
                        metal=metal,
                        monthly_interest_rate=rate,
                        effective_from=data["effective_from"],
                        actor=request.user,
                    )
        except (ValidationError, ValueError) as exc:
            configuration_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan economic configuration added.")
            return redirect("loans:pawn_economics_setup")
    if action == "fee" and fee_form.is_valid():
        try:
            create_pawn_loan_fee_policy(
                workspace=request.loans_workspace,
                actor=request.user,
                **fee_form.cleaned_data,
            )
        except (ValidationError, ValueError) as exc:
            fee_form.add_error(None, str(exc))
        else:
            messages.success(request, "PawnLoan fee policy added.")
            return redirect("loans:pawn_economics_setup")
    context = {
        "configuration_form": configuration_form,
        "fee_form": fee_form,
        "economic_policies": PawnLoanEconomicPolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "rate_policies": PawnMetalInterestRatePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
        "fee_policies": PawnLoanFeePolicy.objects.filter(
            workspace=request.loans_workspace
        ).select_related("license"),
    }
    return render(request, "loans/setup/economics.html", context)


@loans_setup_required
def license_detail(request, pk):
    license = _license_for_workspace(request, pk)
    series_rows = []
    for series in license.series.prefetch_related("number_sequences").all():
        series_rows.append(
            {
                "series": series,
                "loan_preview": _safe_preview(series, LoanDocumentKind.PAWN_LOAN),
                "release_preview": _safe_preview(
                    series, LoanDocumentKind.PAWN_LOAN_RELEASE
                ),
            }
        )
    return render(
        request,
        "loans/setup/license_detail.html",
        {"license": license, "series_rows": series_rows},
    )


@loans_setup_required
def license_create(request):
    form = LoanLicenseForm(request.POST or None)
    form.instance.workspace = request.loans_workspace
    if request.method == "POST" and form.is_valid():
        license = create_license(
            workspace=request.loans_workspace,
            actor=request.user,
            **form.cleaned_data,
        )
        messages.success(request, "Loan license created.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(request, "loans/setup/license_form.html", {"form": form})


@loans_setup_required
def license_update(request, pk):
    license = _license_for_workspace(request, pk)
    form = LoanLicenseForm(request.POST or None, instance=license)
    if request.method == "POST" and form.is_valid():
        update_license(license, actor=request.user, **form.cleaned_data)
        messages.success(request, "Loan license updated.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/license_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
@require_POST
def license_expire(request, pk):
    license = _license_for_workspace(request, pk)
    expire_license(license, actor=request.user)
    messages.success(request, "Loan license deactivated; existing loans remain linked.")
    return redirect("loans:license_detail", pk=license.pk)


@loans_setup_required
@require_POST
def license_activate(request, pk):
    license = _license_for_workspace(request, pk)
    try:
        activate_license(license, actor=request.user)
        messages.success(request, "Loan license activated.")
    except LicenseSeriesError as exc:
        messages.error(request, str(exc))
    return redirect("loans:license_detail", pk=license.pk)


@loans_setup_required
def series_create(request, license_pk):
    license = _license_for_workspace(request, license_pk)
    form = LoanSeriesSetupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            series = create_series(
                license=license,
                name=form.cleaned_data["name"],
                code=form.cleaned_data["code"],
                is_active=form.cleaned_data["is_active"],
            )
            _configure_both_sequences(series, form.cleaned_data, request)
        messages.success(request, "Loan series and numbering sequences created.")
        return redirect("loans:license_detail", pk=license.pk)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": license},
    )


@loans_setup_required
def series_update(request, pk):
    series = _series_for_workspace(request, pk)
    initial = _series_initial(series)
    form = LoanSeriesSetupForm(request.POST or None, instance=series, initial=initial)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            update_series(
                series,
                name=form.cleaned_data["name"],
                code=form.cleaned_data["code"],
            )
            set_series_active(series, is_active=form.cleaned_data["is_active"])
            _configure_both_sequences(series, form.cleaned_data, request)
        messages.success(request, "Loan series setup updated.")
        return redirect("loans:license_detail", pk=series.license_id)
    return render(
        request,
        "loans/setup/series_form.html",
        {"form": form, "license": series.license, "series": series},
    )


def _license_for_workspace(request, pk):
    return get_object_or_404(
        LoanLicense, pk=pk, workspace=request.loans_workspace
    )


def _series_for_workspace(request, pk):
    return get_object_or_404(
        LoanSeries.objects.select_related("license"),
        pk=pk,
        license__workspace=request.loans_workspace,
    )


def _safe_preview(series, kind):
    try:
        return {"value": preview_number(series=series, document_kind=kind).value}
    except NumberAllocationError as exc:
        return {"error": str(exc)}
    except ValueError as exc:
        return {"error": str(exc)}


def _series_initial(series):
    sequences = {item.document_kind: item for item in series.number_sequences.all()}
    loan = sequences.get(LoanDocumentKind.PAWN_LOAN.value)
    release = sequences.get(LoanDocumentKind.PAWN_LOAN_RELEASE.value)
    baseline = loan or release
    return {
        "pawn_loan_prefix": loan.prefix if loan else "PL-",
        "release_prefix": release.prefix if release else "RL-",
        "number_width": baseline.width if baseline else 5,
        "maximum_number": baseline.maximum_number if baseline else 10000,
    }


def _configure_both_sequences(series, cleaned_data, request):
    common = {
        "series": series,
        "width": cleaned_data["number_width"],
        "maximum_number": cleaned_data["maximum_number"],
        "actor": request.user,
        "request": request,
    }
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN,
        prefix=cleaned_data["pawn_loan_prefix"],
        **common,
    )
    configure_sequence(
        document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE,
        prefix=cleaned_data["release_prefix"],
        **common,
    )


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items",
            "change_log__actor",
            "accounting_events__outbox",
            "accounting_events__reversed_by_event",
            "releases__items__collateral_item",
            "approval_snapshots",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _pawn_auction_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanAuction.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "accounting_event__outbox",
        ).prefetch_related("items__collateral_item"),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _pawn_renewal_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanRenewal.objects.select_related(
            "source_loan",
            "source_loan__workspace",
            "source_loan__license",
            "source_loan__borrower",
            "successor_loan",
            "settlement_event__outbox",
            "opening_event__outbox",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _draft_readiness(workspace):
    from apps.tenant_apps.party.models import Party

    if not Party.objects.filter(status=Party.PartyStatus.ACTIVE).exists():
        return {
            "ready": False,
            "message": "Create an active Party before starting a pawn-loan draft.",
            "action_label": "Create Party",
            "action_url": reverse("party:party_create"),
        }
    candidates = LoanSeries.objects.filter(
        license__workspace=workspace,
        license__is_active=True,
        is_active=True,
    ).select_related("license")
    for series in candidates:
        try:
            preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN)
            if series.license.is_expired():
                continue
            today = timezone.localdate()
            resolve_pawn_loan_economic_policy(
                workspace_id=workspace.pk,
                license_id=series.license_id,
                as_of_date=today,
            )
            for metal in ("GOLD", "SILVER"):
                resolve_pawn_metal_interest_rate_policy(
                    workspace_id=workspace.pk,
                    license_id=series.license_id,
                    metal=metal,
                    as_of_date=today,
                )
            return {"ready": True}
        except (NumberAllocationError, ValueError):
            continue
    return {
        "ready": False,
        "message": "Configure numbering and current PawnLoan economics before drafting.",
        "action_label": "Open Economic Setup",
        "action_url": reverse("loans:pawn_economics_setup"),
    }


def _collateral_inputs(formset):
    return tuple(
        CollateralDraftInput(
            description=row["description"],
            metal=row["metal"],
            gross_weight=row["gross_weight"],
            net_weight=row["net_weight"],
            purity_percentage=row["purity_percentage"],
            latest_appraised_value=row.get("latest_appraised_value"),
            allocated_principal=row["allocated_principal"],
        )
        for row in formset.cleaned_data
        if row and not row.get("DELETE")
    )


def _create_command(workspace_id, form, formset):
    data = form.cleaned_data
    return CreatePawnDraftCommand(
        workspace_id=workspace_id,
        borrower_id=data["borrower"].pk,
        license_id=data["license"].pk,
        series_id=data["series"].pk,
        principal_amount=Decimal("0.01"),
        monthly_interest_rate=Decimal("0"),
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )


def _update_command(form, formset):
    data = form.cleaned_data
    return UpdatePawnDraftCommand(
        borrower_id=data["borrower"].pk,
        principal_amount=Decimal("0.01"),
        monthly_interest_rate=Decimal("0"),
        loan_date=data["loan_date"],
        tenure_months=data["tenure_months"],
        collateral=_collateral_inputs(formset),
    )


def _reason_transition(request, pk, action):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnTransitionReasonForm(request.POST or None)
    labels = {"reopen": "Return to draft", "cancel": "Cancel loan"}
    if request.method == "POST" and form.is_valid():
        try:
            if action == "reopen":
                reopen_pawn_loan(
                    loan.pk, reason=form.cleaned_data["reason"], actor=request.user
                )
            else:
                cancel_pawn_loan(
                    loan.pk, reason=form.cleaned_data["reason"], actor=request.user
                )
        except (PawnLifecycleError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{loan.loan_number}: {labels[action].lower()} completed.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return render(
        request,
        "loans/pawn/transition_form.html",
        {"loan": loan, "form": form, "action_label": labels[action]},
    )


def _render_action(request, loan, form, title, description, extra_context=None):
    context = {
        "loan": loan,
        "form": form,
        "action_label": title,
        "description": description,
    }
    context.update(extra_context or {})
    return render(request, "loans/pawn/action_form.html", context)


def _safe_balance(loan):
    try:
        return get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return None


def _safe_accrual_previews(loan, *, include_partial):
    try:
        return preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=timezone.localdate(),
            include_partial=include_partial,
        )
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return ()


def _release_quote(loan, selected_item_ids):
    return get_pawn_loan_release_readiness(
        loan.pk,
        selected_item_ids=selected_item_ids,
        as_of_date=timezone.localdate(),
    )


def _full_release_quote(loan):
    selected_ids = tuple(
        loan.collateral_items.exclude(custody_state="WITH_CUSTOMER").values_list(
            "pk", flat=True
        )
    )
    try:
        return _release_quote(loan, selected_ids)
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        return {"error": str(exc), "minimum_settlement": None}


def _primary_action(loan, context):
    if loan.state == PawnLoanState.DRAFT.value:
        return {
            "label": "Approve loan",
            "url": reverse("loans:pawn_loan_approve", args=[loan.pk]),
            "method": "post",
            "message": "Review the frozen terms, then approve this draft.",
        }
    if loan.state == PawnLoanState.APPROVED.value:
        return {
            "label": "Disburse loan",
            "url": reverse("loans:pawn_loan_disburse", args=[loan.pk]),
            "message": "Record disbursal to activate the loan and queue DEA posting.",
        }
    if loan.state == PawnLoanState.ACTIVE.value:
        balance = context.get("balance")
        if balance and not balance.posting_ready:
            return {
                "label": "Resolve accounting delivery",
                "url": "#accounting-delivery",
                "message": "A pending or failed accounting event blocks dependent operations.",
            }
        return {
            "label": "Record repayment",
            "url": reverse("loans:pawn_loan_repay", args=[loan.pk]),
            "message": "Continue with repayment, accrual, or collateral release.",
        }
    if loan.state == PawnLoanState.CLOSED.value:
        return {
            "label": "Review accounting history",
            "url": "#accounting-delivery",
            "message": "This loan is closed. Administrators can reverse eligible events in order.",
        }
    return None


def _can_administer(request):
    user = request.user
    workspace = request.loans_workspace
    return bool(
        is_platform_admin(user)
        or workspace.owner_id == user.pk
        or get_workspace_role_name(user, workspace) in {"Owner", "Admin"}
    )


def _accounting_rows(loan, *, can_administer):
    rows = []
    for event in loan.accounting_events.all():
        outbox = event.outbox
        try:
            reversed_event = event.reversed_by_event
        except PawnLoanAccountingEvent.DoesNotExist:
            reversed_event = None
        rows.append(
            {
                "event": event,
                "outbox": outbox,
                "can_retry": can_administer and outbox.status == LoanOutboxStatus.FAILED.value,
                "can_reverse": (
                    can_administer
                    and outbox.status == LoanOutboxStatus.POSTED.value
                    and event.event_kind
                    not in {
                        TransactionKind.REVERSAL.value,
                        TransactionKind.AUCTION_RECOVERY.value,
                        TransactionKind.RENEWAL_SETTLEMENT.value,
                        TransactionKind.RENEWAL_OPENING.value,
                    }
                    and reversed_event is None
                ),
            }
        )
    return rows
