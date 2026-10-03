"""Reasoned series availability transitions; never cash, custody or renumbering."""
from contextlib import contextmanager

from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataSeries, KhataSeriesStatusChange
from .action_access import require_setup_administration
from .khata_accounts import KhataDraftError, _hash, _key


def available_transitions(series):
    if series.retired_at:
        return ()
    return (("PAUSED", "Pause"), ("RETIRED", "Retire")) if series.is_active else (("ACTIVE", "Resume"), ("RETIRED", "Retire"))


@contextmanager
def _locked(workspace, actor, series_id):
    with workspace_context(workspace.pk):
        require_setup_administration(workspace.pk, actor)
        Company.objects.select_for_update().get(pk=workspace.pk)
        yield KhataSeries.objects.select_for_update().get(workspace=workspace, pk=series_id)


def _snapshot(series):
    return dict(series_id=series.pk, status=series.lending_status,
        last_change=series.status_changes.values_list("number", flat=True).first() or 0,
        next_number=series.next_number, maximum_number=series.maximum_number,
        prefix=series.prefix, width=series.width, license_id=series.license_id,
        has_issued_number=series.has_issued_number, date=timezone.localdate().isoformat())


def preview(*, workspace, actor, series_id):
    with _locked(workspace, actor, series_id) as series:
        snapshot = _snapshot(series)
        return dict(snapshot=snapshot, review_hash=_hash(snapshot))


def change_status(*, workspace, actor, series_id, to_status, reason, request_key, review_hash):
    key = _key(request_key)
    reason = reason.strip()
    if not reason or len(reason) > 2000:
        raise KhataDraftError("A reason of at most 2,000 characters is required.")
    fingerprint = _hash(dict(series_id=series_id, actor=actor.pk, to_status=to_status,
                             reason=reason, review_hash=review_hash))
    with _locked(workspace, actor, series_id) as series:
        existing = KhataSeriesStatusChange.objects.filter(workspace=workspace, request_key=key).first()
        if existing:
            if existing.request_sha256 != fingerprint:
                raise KhataDraftError("Request UUID was already used with different instructions.")
            return existing
        snapshot = _snapshot(series)
        if _hash(snapshot) != review_hash:
            raise KhataDraftError("The series changed after review; refresh and review again.")
        if to_status not in dict(available_transitions(series)):
            raise KhataDraftError("Choose an available transition. Retirement is permanent.")
        change = KhataSeriesStatusChange(workspace=workspace, series=series,
            number=snapshot["last_change"] + 1, from_status=series.lending_status,
            to_status=to_status, reason=reason, request_key=key, request_sha256=fingerprint,
            created_by=actor)
        change.full_clean()
        change.save()  # The guarded database trigger updates series availability atomically.
        return change
