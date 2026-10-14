"""Signed source-bound owner retry and operator reconciliation; no arbitrary send."""
from datetime import timedelta
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.orgs.services.platform_console import require_console_access
from apps.tenancy.context import current_workspace_id, workspace_context
from .configuration import transport_fingerprint
from .dispatch import _message, dispatch_one, reconcile_delivery, _standalone
from .intents import fingerprint
from .models import Delivery
from .services import require_account_actor, require_owner

SALT="platform-whatsapp.operation-review.v1"


def _snapshot(actor,workspace,delivery_id,action):
    if action not in {"retry","reconcile"}:raise ValidationError("Unsupported messaging action.")
    if action=="retry":require_account_actor(actor)
    else:require_console_access(actor)
    with workspace_context(workspace.pk):
        if action=="retry":require_owner(actor,workspace)
        row=Delivery.objects.get(pk=delivery_id,workspace=workspace)
        if action=="retry" and row.owner_id!=actor.pk:raise PermissionDenied("Only the recorded current owner may retry.")
        latest=row.attempts.order_by("-number").first()
        if not latest:raise ValidationError("This delivery has no attempt to review.")
        if action=="retry":
            if row.capture_only or latest.outcome!="rejected" or not latest.retryable or latest.number>=3:
                raise ValidationError("Only a definite retryable rejection can be retried.")
            if timezone.now()<latest.finished_at+timedelta(minutes=latest.number):
                raise ValidationError("The bounded retry backoff has not ended.")
            payload,_=_message(row)
            from .controls import gate
            gate(row)
            content=fingerprint(payload)
        else:content=row.source_fingerprint
        links=[[str(a.pk),a.outcome,a.provider_message_id,a.receipt_links.count()] for a in row.attempts.order_by("number")]
        return {"actor":actor.pk,"workspace":workspace.pk,"delivery":row.pk,"action":action,
            "source":row.source_fingerprint,"contact_revision":row.contact_revision,"consent":row.consent_id,
            "transport":transport_fingerprint(),"content":content,"attempts":links}


def review_operation(*,actor,workspace_slug,delivery_id,action):
    workspace=Company.all_objects.select_related("owner").get(slug=workspace_slug)
    saved=_snapshot(actor,workspace,delivery_id,action)
    return {"workspace":workspace,"delivery_id":delivery_id,"action":action,
        "token":signing.dumps(saved,salt=SALT),"expires_minutes":10}


def confirm_operation(*,actor,token,workspace_slug,delivery_id,action):
    # HTTP is marked non-atomic. A review transaction must end before Cloud IO.
    _standalone()
    try:saved=signing.loads(token,salt=SALT,max_age=600)
    except signing.BadSignature as exc:raise ValidationError("Messaging review expired or changed. Review again.") from exc
    if not isinstance(saved,dict) or saved.get("actor")!=actor.pk:raise PermissionDenied("This review belongs to another account.")
    workspace=Company.all_objects.select_related("owner").get(pk=saved.get("workspace"))
    if workspace.slug!=workspace_slug or saved.get("delivery")!=delivery_id or saved.get("action")!=action:
        raise PermissionDenied("The review must match this exact Workspace, delivery and action.")
    fresh=_snapshot(actor,workspace,saved.get("delivery"),saved.get("action"))
    if fresh!=saved:raise ValidationError("Source, consent, configuration or delivery evidence changed. Review again.")
    # Durable service repeats current eligibility/group checks before any request.
    if saved["action"]=="retry":
        status=dispatch_one(workspace_id=workspace.pk,delivery_id=saved["delivery"])
    else:
        status=reconcile_delivery(workspace_id=workspace.pk,delivery_id=saved["delivery"],recover_stale=True)["status"]
    AuditLog.log("SETTINGS_UPDATE",user=actor,company=workspace,
        description="Reviewed platform WhatsApp "+saved["action"],success=True,
        data={"delivery_id":saved["delivery"],"action":saved["action"],"status":status})
    return status
