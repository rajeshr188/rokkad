"""Reviewed adoption of an existing register; reserves counters, never loans."""
from django.core import signing
from django.db import transaction

from apps.orgs.models import Company
from apps.tenant_apps.loans.models import LoanNumberSequence, LoanSeries, current_tenant_workspace_id
from .action_access import require_setup_administration
from .license_series import LicenseSeriesError, reserve_sequence_through

SALT = "loans.series-reservation.v1"


def _source(series_id, actor, kind, last_used, reference):
    workspace_id = current_tenant_workspace_id()
    require_setup_administration(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    try:
        series = LoanSeries.objects.get(pk=series_id, workspace_id=workspace_id)
        sequence = LoanNumberSequence.objects.select_for_update().get(series=series, document_kind=kind)
    except (LoanSeries.DoesNotExist, LoanNumberSequence.DoesNotExist) as exc:
        raise LicenseSeriesError("Select a configured register in this Workspace.") from exc
    if type(last_used) is not int or not sequence.next_number - 1 <= last_used <= sequence.maximum_number:
        raise LicenseSeriesError("The last used counter must be within the saved range and cannot move the next number backwards.")
    if not isinstance(reference, str) or not reference.strip() or len(reference.strip()) > 255 or any(ord(c) < 32 or ord(c) == 127 for c in reference):
        raise LicenseSeriesError("Supply the original register reference.")
    review = dict(workspace=workspace_id, series=series.pk, sequence=sequence.pk, actor=actor.pk,
        kind=kind, prefix=sequence.prefix, width=sequence.width, maximum=sequence.maximum_number,
        before=sequence.next_number, after=last_used+1, last_used=last_used, reference=reference.strip())
    review["next_number"] = f"{sequence.prefix}{last_used+1:0{sequence.width}d}" if last_used < sequence.maximum_number else "Exhausted"
    review["last_used_number"] = f"{sequence.prefix}{last_used:0{sequence.width}d}"
    return series, review


@transaction.atomic
def preview_register_reservation(series_id, *, actor, kind, last_used, reference):
    _, review = _source(series_id, actor, kind, last_used, reference)
    return review, signing.dumps(review, salt=SALT, compress=True)


@transaction.atomic
def confirm_register_reservation(series_id, *, actor, kind, last_used, reference, review_token, confirmed=False):
    if confirmed is not True:
        raise LicenseSeriesError("Confirm the reviewed register range.")
    series, current = _source(series_id, actor, kind, last_used, reference)
    try:
        saved = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise LicenseSeriesError("Review this register range again.") from exc
    if current != saved:
        repeated = dict(saved, before=saved.get("after")) if isinstance(saved, dict) else None
        if current != repeated:
            raise LicenseSeriesError("Numbering or review facts changed. Review this register range again.")
    changed = current["before"] != current["after"]
    reserve_sequence_through(series=series, document_kind=kind, last_used_number=last_used,
        evidence_reference=current["reference"], actor=actor)
    return changed
