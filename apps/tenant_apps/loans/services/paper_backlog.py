"""Paper-book checkpoints, independent from debt and per-loan completeness."""
from datetime import date
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import PaperBacklogCheckpoint, current_tenant_workspace_id
from .action_access import require_workspace_action
from .recorded_history import _text


@transaction.atomic
def record_backlog_checkpoint(*, workspace, actor, book_reference, through_date, last_page_reference, state, note, request_key):
    if current_tenant_workspace_id() != workspace.pk:
        raise PermissionDenied("Backlog recording requires the matching Workspace.")
    require_workspace_action(workspace, actor, "data.edit")
    facts = dict(book_reference=_text(book_reference, "paper book reference"),
        last_page_reference=_text(last_page_reference, "last page checked"),
        request_key=_text(request_key, "submission reference", 120), state=state,
        through_date=through_date, note=_text(note, "progress note", 500) if note else "")
    if type(through_date) is not date or through_date > timezone.localdate() or state not in ("IN_PROGRESS", "ENTERED", "NEEDS_REVIEW"):
        raise ValueError("Select valid progress through a date no later than today.")
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    existing = PaperBacklogCheckpoint.objects.filter(workspace=workspace, request_key=facts["request_key"]).first()
    if existing:
        if existing.recorded_by_id != actor.pk or any(getattr(existing, key) != value for key, value in facts.items()):
            raise ValueError("This submission already recorded different progress.")
        return existing, False
    return PaperBacklogCheckpoint.objects.create(workspace=workspace, recorded_by=actor, **facts), True
