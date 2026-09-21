"""Browser approval of operator-prepared, source-verified opening candidates."""
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.services.history_contract import HistoryError
from apps.tenant_apps.loans.services.history_setup import require_history_setup_access
from . import legacy_opening
from .models import LoanHistoryBatch


@login_required
@never_cache
@require_http_methods(["GET"])
def listing(request):
    require_history_setup_access(request.workspace.pk, request.user)
    batches = LoanHistoryBatch.objects.filter(workspace_id=request.workspace.pk, profile=legacy_opening.PROFILE).order_by("-created_at", "-pk")[:20]
    return render(request, "data_portability/legacy_openings.html", {"batches": batches})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def review(request, batch_id):
    args = {"workspace_id": request.workspace.pk, "actor": request.user, "batch_id": batch_id}
    batch = legacy_opening.get_batch(**args)
    approval, error = None, None
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "preview":
                approval = legacy_opening.preview(**args)
            elif action == "commit":
                legacy_opening.commit(**args, approval=request.POST.get("approval", ""), confirmed=request.POST.get("confirmed") == "yes")
                return redirect("workspace_portability:opening_batch", workspace_slug=request.workspace.slug, batch_id=batch_id)
            elif action == "cancel":
                legacy_opening.cancel(**args, confirmed=request.POST.get("confirmed") == "yes")
                return redirect("workspace_portability:opening_batch", workspace_slug=request.workspace.slug, batch_id=batch_id)
            else:
                raise HistoryError("Choose a supported opening review action.")
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            error = str(exc)
    batch.refresh_from_db()
    source_review = batch.document.get("opening", {}).get("review")
    destination = {}
    if source_review:
        from apps.tenant_apps.loans.models import LoanLicenseRevision, LoanSeries, LoanProductVersion
        mapping = source_review["mapping"]
        destination = {
            "licence": LoanLicenseRevision.objects.filter(workspace_id=request.workspace.pk, pk=mapping["licence_revision_id"]).first(),
            "series": LoanSeries.objects.filter(workspace_id=request.workspace.pk, pk=mapping["series_id"]).first(),
            "product": LoanProductVersion.objects.select_related("product").filter(workspace_id=request.workspace.pk, pk=mapping["product_version_id"]).first(),
        }
    return render(request, "data_portability/legacy_opening_review.html", {
        "batch": batch, "review": source_review, "destination": destination,
        "approval": approval, "error": error, "unfinished": batch.state in {"STAGED", "READY"}})
