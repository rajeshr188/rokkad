"""Authorized append-only quote commands. No cache or loan posting side effects."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id

from .models import Rate, RateSource


QUOTE_FIELDS = ("metal", "currency", "purity", "buying_rate", "selling_rate", "effective_at")


def _authorize(workspace, actor, permission):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Quote changes require the active Workspace.")
    current = Company.all_objects.get(pk=workspace.pk)
    resolve_workspace_access(actor=actor, workspace=current).require(permission)
    if current.lifecycle_state != "ACTIVE":
        raise PermissionDenied("Quote changes require an active Workspace.")


@transaction.atomic
def record_quote(*, workspace, actor, values, supersedes_id=None):
    _authorize(workspace, actor, "data.edit" if supersedes_id else "data.create")
    previous = _correctable(workspace, supersedes_id) if supersedes_id else None
    try:
        source = RateSource.objects.get(workspace=workspace, pk=values["rate_source"].pk)
    except RateSource.DoesNotExist as exc:
        raise ValidationError("Select an existing source in this Workspace.") from exc
    quote = Rate(workspace=workspace, rate_source=source, recorded_by=actor,
                 supersedes=previous, reason=values.get("reason", "").strip(),
                 **{name: values[name] for name in QUOTE_FIELDS})
    quote.full_clean(exclude=("source_snapshot",))
    quote.save()
    return quote


def _correctable(workspace, pk):
    previous = Rate.objects.select_for_update().get(workspace=workspace, pk=pk)
    if previous.is_withdrawal or Rate.objects.filter(supersedes=previous).exists():
        raise ValidationError("This quote has already been corrected or withdrawn. Open its latest record.")
    return previous


@transaction.atomic
def withdraw_quote(*, workspace, actor, quote_id, reason):
    _authorize(workspace, actor, "data.delete")
    previous = _correctable(workspace, quote_id)
    quote = Rate(workspace=workspace, rate_source=previous.rate_source, recorded_by=actor,
                 supersedes=previous, is_withdrawal=True, reason=reason.strip(),
                 **{name: getattr(previous, name) for name in QUOTE_FIELDS})
    quote.full_clean(exclude=("buying_rate", "selling_rate", "purity", "source_snapshot"))
    quote.save()
    return quote
