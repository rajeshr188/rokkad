"""Operational notice actions; existing services own business rules."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import (
    get_object_or_404,
    redirect,
)
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.models import LoanOperationalNotice
from apps.tenant_apps.loans.services import (
    LoanOperationalNoticeError,
    retry_operational_notice,
)


@loans_setup_required
@require_POST
def operational_notice_retry(request, notice_pk):
    notice = get_object_or_404(
        LoanOperationalNotice,
        pk=notice_pk,
        workspace=request.loans_workspace,
    )
    try:
        result = retry_operational_notice(notice.pk, actor=request.user)
    except (LoanOperationalNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(
            request, f"Operational alert delivery is {result.delivery.status.lower()}."
        )
    if notice.source_license_id:
        return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=notice.source_license_id)
    return redirect(
        "workspace_loans:pawn_physical_verification_detail",
        workspace_slug=request.loans_workspace.slug,
        pk=notice.source_verification_observation.session_id,
    )
