"""Loan documents; existing services own business rules."""

import hashlib
from types import SimpleNamespace
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.domain import TransactionKind
from apps.tenant_apps.loans.documents import PawnLoanDocumentProjectionBuilder
from apps.tenant_apps.loans.models import (
    PawnLoanEvent,
    PawnLoanAuction,
    PawnLoanRelease,
    PawnLoanRenewal,
)
from apps.tenant_apps.loans.services import (
    DocumentLayoutServiceError,
    LoanDocumentLayoutService,
    PawnLoanDocumentError,
    PawnLoanDocumentService,
    issue_configurable_document,
)
from apps.tenant_apps.loans.services.print_profiles import PrintProfileServiceError
from apps.tenant_apps.loans.web.pawn_read_helpers import (
    _can_administer,
    _pawn_loan_for_workspace,
)


def _configurable_document_response(request, *, payload, loan, source_type, source_id, source_fingerprint):
    use_fixed = request.GET.get("renderer") == "fixed"
    if use_fixed and not _can_administer(request):
        return HttpResponse("Fixed-renderer recovery requires workspace administration access.", status=403, content_type="text/plain")
    use_legacy_profile = request.GET.get("print_profile") == "legacy"
    if use_legacy_profile and not _can_administer(request):
        return HttpResponse(
            "Legacy print-profile recovery requires workspace administration access.",
            status=403,
            content_type="text/plain",
        )
    try:
        result = issue_configurable_document(
            workspace=request.loans_workspace,
            payload=payload,
            loan=loan,
            source_type=source_type,
            source_id=source_id,
            source_fingerprint=source_fingerprint,
            actor=request.user,
            request=request,
            fixed_recovery=use_fixed,
            legacy_profile_recovery=use_legacy_profile,
        )
    except (
        ValueError, ValidationError, DocumentLayoutServiceError,
        PrintProfileServiceError,
    ) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    if result.use_fixed_renderer:
        return None
    return _issued_document_response(result.issue, payload)


def _issued_document_response(issue, payload):
    issue.artifact.open("rb")
    pdf = issue.artifact.read()
    issue.artifact.close()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{payload.file_name}"'
    response["Cache-Control"] = "private, no-store"
    response["X-Rokkad-Verification-ID"] = payload.verification_id
    response["X-Rokkad-Document-Issue"] = str(issue.pk)
    if issue.print_profile_hash:
        response["X-Rokkad-Print-Profile"] = issue.print_profile_name
        response["X-Rokkad-Print-Profile-Hash"] = issue.print_profile_hash
    return response


@loans_workspace_required
def pawn_loan_ticket_pdf(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
        approval = loan.approval_snapshots.order_by("-version").first()
        response = _configurable_document_response(
            request, payload=payload, loan=loan, source_type="PawnLoan",
            source_id=loan.pk, source_fingerprint=approval.fingerprint,
        )
        if response is not None: return response
        result = PawnLoanDocumentService.render_loan_ticket(loan)
    except (PawnLoanDocumentError, ValueError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_kfs_schedule_pdf(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.loan_kfs_schedule(loan)
        schedule = loan.repayment_schedules.order_by("-version").first()
        existing = LoanDocumentLayoutService.find_official_issue(
            workspace=request.loans_workspace, document_type=payload.document_type,
            source_type="RepaymentScheduleVersion", source_id=schedule.pk,
            source_fingerprint=schedule.fingerprint,
        )
        if existing:
            return _issued_document_response(existing, payload)
        result = PawnLoanDocumentService.render_loan_kfs_schedule(loan)
        render_result = SimpleNamespace(
            pdf=result.pdf, renderer_version="fixed-kfs-v1",
            payload_hash=hashlib.sha256(repr(payload).encode()).hexdigest(),
            layout_hash="", asset_hashes={},
        )
        issue = LoanDocumentLayoutService.issue(
            workspace=request.loans_workspace, document_type=payload.document_type,
            source_type="RepaymentScheduleVersion", source_id=schedule.pk,
            source_fingerprint=schedule.fingerprint,
            payload_schema_version=payload.schema_version, render_result=render_result,
            filename=payload.file_name, actor=request.user,
        )
        return _issued_document_response(issue, payload)
    except (PawnLoanDocumentError, ValueError, ValidationError) as exc:
        return HttpResponse(str(exc), status=409, content_type="text/plain")


@loans_workspace_required
def pawn_repayment_receipt_pdf(request, pk, event_pk):
    event = get_object_or_404(
        PawnLoanEvent.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "reversed_by_event",
        ),
        pk=event_pk,
        loan_id=pk,
        loan__workspace=request.loans_workspace,
        event_kind=TransactionKind.REPAYMENT.value,
    )
    payload = PawnLoanDocumentProjectionBuilder.repayment_receipt(event)
    response = _configurable_document_response(
        request, payload=payload, loan=event.loan,
        source_type="PawnLoanEvent", source_id=event.pk,
        source_fingerprint=event.payload_fingerprint,
    )
    if response is not None:
        return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_repayment_receipt(event))


@loans_workspace_required
def pawn_release_memo_pdf(request, release_pk):
    release = get_object_or_404(
        PawnLoanRelease.objects.select_related(
            "workspace",
            "loan",
            "loan__license",
            "loan__borrower",
            "loan_event",
            "loan_event",
            "reversal",
        ).prefetch_related("items__collateral_item"),
        pk=release_pk,
        workspace=request.loans_workspace,
    )
    payload = PawnLoanDocumentProjectionBuilder.release_memo(release)
    response = _configurable_document_response(
        request, payload=payload, loan=release.loan,
        source_type="PawnLoanRelease", source_id=release.pk,
        source_fingerprint=release.loan_event.payload_fingerprint,
    )
    if response is not None:
        return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_release_memo(release))


@loans_workspace_required
def pawn_loan_auction_notice_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    payload = PawnLoanDocumentProjectionBuilder.auction_notice(auction)
    response = _configurable_document_response(
        request, payload=payload, loan=auction.loan,
        source_type="PawnLoanAuctionNotice", source_id=auction.pk,
        source_fingerprint=hashlib.sha256(payload.verification_id.encode()).hexdigest(),
    )
    if response is not None: return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_auction_notice(auction))


@loans_workspace_required
def pawn_loan_auction_recovery_pdf(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        payload = PawnLoanDocumentProjectionBuilder.auction_recovery_memo(auction)
        response = _configurable_document_response(
            request, payload=payload, loan=auction.loan,
            source_type="PawnLoanAuction", source_id=auction.pk,
            source_fingerprint=auction.loan_event.payload_fingerprint,
        )
        if response is not None: return response
        result = PawnLoanDocumentService.render_auction_recovery_memo(auction)
    except (PawnLoanDocumentError, ValueError) as exc:
        return HttpResponse(str(exc), status=409)
    return PawnLoanDocumentService.build_pdf_response(result)


@loans_workspace_required
def pawn_loan_renewal_pdf(request, renewal_pk):
    renewal = _pawn_renewal_for_workspace(request, renewal_pk)
    payload = PawnLoanDocumentProjectionBuilder.renewal_memo(renewal)
    response = _configurable_document_response(
        request, payload=payload, loan=renewal.source_loan,
        source_type="PawnLoanRenewal", source_id=renewal.pk,
        source_fingerprint=renewal.settlement_event.payload_fingerprint,
    )
    if response is not None: return response
    return PawnLoanDocumentService.build_pdf_response(PawnLoanDocumentService.render_renewal_memo(renewal))


def _pawn_auction_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanAuction.objects.select_related(
            "loan",
            "loan__workspace",
            "loan__license",
            "loan__borrower",
            "loan_event",
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
            "settlement_event",
            "opening_event",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )
