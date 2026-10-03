from django.http import HttpResponse
from django.urls import reverse
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.services.collateral_media import PawnCollateralMediaError
from apps.tenant_apps.loans.services.loan_collateral_label import render_loan_collateral_label
from .pawn_read_helpers import _pawn_loan_for_workspace


@loans_workspace_required
@never_cache
@require_GET
def loan_collateral_label(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    qr_target = request.build_absolute_uri(reverse("workspace_loans:pawn_loan_detail",
        kwargs={"workspace_slug":request.loans_workspace.slug, "pk":loan.pk})) + "#collateral-gallery"
    try:
        content = render_loan_collateral_label(loan.pk, qr_target=qr_target,
            action=request.GET.get("action", "PREVIEW").upper(), actor=request.user)
    except PawnCollateralMediaError as exc:
        return HttpResponse(str(exc), status=409)
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = content_disposition_header(False, f"{loan.loan_number}-all-collateral-label.pdf")
    response["X-Content-Type-Options"] = "nosniff"
    return response
