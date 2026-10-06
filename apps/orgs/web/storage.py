from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company, StorageInventoryRun, WorkspaceStorageUsage
from apps.orgs.services.platform_console import require_console_access
from apps.tenancy.context import current_workspace_id, workspace_context


LABELS = {"owned": "Assigned to one workspace", "shared": "Shared references", "platform": "Platform files",
    "unreferenced_recent": "Unreferenced / recent or age unknown", "unreferenced_review": "Unreferenced / review needed",
    "missing": "Referenced but not found", "customer_photos": "Customer photos", "customer_documents": "Customer documents",
    "collateral_photos": "Collateral photos", "historical_evidence": "Historical evidence", "licence_documents": "Licence documents",
    "template_assets": "Template assets", "issued_documents": "Issued documents", "notification_artifacts": "Notification files",
    "workspace_logos": "Workspace logos", "multiple_uses": "Multiple uses (counted once)"}


def usage_context(usage):
    if usage is None:
        return {"usage": None}
    return {"usage": usage, "categories": [{**row, "label": LABELS.get(row["category"], row["category"])} for row in usage.categories],
            "stale": (timezone.now()-usage.run.completed_at).total_seconds() > 172800}


@never_cache
@login_required
@require_GET
def platform_storage(request):
    require_console_access(request.user)
    if getattr(request, "workspace", None) is not None:
        raise PermissionDenied
    run = StorageInventoryRun.objects.filter(state="complete").first()
    latest = StorageInventoryRun.objects.first()
    context = {"section": "storage", "run": run, "latest": latest}
    if run:
        state = request.GET.get("state", "unreferenced_review")
        if state not in LABELS or state not in {"owned", "shared", "platform", "unreferenced_review", "unreferenced_recent", "missing"}:
            state = "unreferenced_review"
        context.update(state=state, state_label=LABELS[state],
            totals=[{"label": LABELS[key], "state": key, **run.totals.get(key, {"objects": 0, "bytes": 0})}
                for key in ("owned", "shared", "platform", "unreferenced_recent", "unreferenced_review", "missing")],
            total_bytes=sum(value["bytes"] for value in run.totals.values()),
            total_objects=sum(value["objects"] for key, value in run.totals.items() if key != "missing"),
            page=Paginator(run.inventory_objects.filter(state=state).order_by("id"), 25).get_page(request.GET.get("page")),
            stale=(timezone.now()-run.completed_at).total_seconds() > 172800)
    return render(request, "platform_console/storage.html", context)


@never_cache
@login_required
@require_GET
def workspace_storage(request, workspace_slug):
    workspace = get_object_or_404(Company.all_objects, slug=workspace_slug)
    if (getattr(request, "workspace", None) is None or request.workspace.pk != workspace.pk
            or current_workspace_id() != workspace.pk):
        raise PermissionDenied("Storage usage requires the explicit workspace context.")
    access = resolve_workspace_access(actor=request.user, workspace=workspace)
    if not request.user.is_active or not access.can("workspace.settings.manage"):
        raise PermissionDenied
    usage = WorkspaceStorageUsage.objects.filter(workspace=workspace, run__state="complete").select_related("run").first()
    return render(request, "company/storage.html", {"workspace": workspace, **usage_context(usage)})


def platform_workspace_usage(*, actor, workspace):
    """Explicit scoped aggregate read for the platform detail; no object keys exposed."""
    require_console_access(actor)
    with workspace_context(workspace.pk):
        usage = WorkspaceStorageUsage.objects.filter(workspace=workspace, run__state="complete").select_related("run").first()
        return usage_context(usage)
