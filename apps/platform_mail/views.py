from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.orgs.tenant_context import resolve_request_workspace
from apps.orgs.web.access_helpers import _assert_workspace_access
from apps.subscriptions.checkout import require_billing_owner
from .models import Delivery
from .services import retry_delivery


@login_required
@require_POST
def retry_platform_mail(request, workspace_id, delivery_id):
    workspace = resolve_request_workspace(request)
    from django.http import Http404
    if not workspace or workspace.pk != workspace_id:
        raise Http404
    from django.db.models import Q
    row = get_object_or_404(Delivery.objects.filter(
        Q(invitation__company=workspace) | Q(invoice__subscription__company=workspace)), pk=delivery_id)
    if row.invitation_id:
        _assert_workspace_access(request, workspace, required_permissions={"team_invite"})
    else:
        require_billing_owner(workspace=workspace, actor=request.user)
    try:
        retry_delivery(row.pk, actor=request.user)
    except ValidationError as exc:
        messages.error(request, exc.messages[0])
    else:
        messages.success(request, "Email queued. Check its delivery status here.")
    if row.invitation_id:
        return redirect("workspace_slug_settings_invitations", workspace_slug=workspace.slug)
    return redirect("workspace_subscriptions:invoice-detail", workspace_slug=workspace.slug, pk=row.invoice_id)
