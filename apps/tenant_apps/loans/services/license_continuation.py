"""Audited continuation with document evidence or explicit owner attestation."""
import re
import hashlib
import json
from datetime import date

from django.db import transaction
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenant_apps.loans.models import LoanLicense, LoanLicenseRevision, LoanNumberSequence, LoanSeries, PawnLoan, PawnLoanRelease
from .action_access import require_setup_administration
from .license_series import LicenseSeriesError, _record_license_revision, _audit_license_revision, reserve_sequence_through


def _overlapping_prefixes(left, right):
    short, long = sorted((left, right), key=len)
    return long.startswith(short) and (long == short or re.fullmatch(r"[0-9]+", long[len(short):]) is not None)


def numbering_review_digest(sequences):
    """Detect a stale review, including formatting edits and receipt allocation."""
    rows = [(s.pk, s.series_id, s.document_kind, s.prefix, s.width,
             s.maximum_number, s.next_number, s.is_active) for s in sequences]
    return hashlib.sha256(json.dumps(sorted(rows)).encode()).hexdigest()


@transaction.atomic
def verify_legacy_license(*, workspace_id, license_id, actor, issued_on, expires_on,
                          issuing_authority, supporting_document, source_sha256,
                          source_as_of, source_reference, confirmed_complete, counters,
                          expected_revision_id, expected_numbering_digest, request=None,
                          document_deferral_reason=None):
    """Counters cover every existing series/kind; no new number is issued here."""
    require_setup_administration(workspace_id, actor)
    # Serializes this transition with import preparation in the same Workspace.
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    deferred = document_deferral_reason is not None
    if deferred:
        if actor.pk != workspace.owner_id:
            raise PermissionDenied("Only the Workspace owner may attest validity while deferring the document.")
        if (not isinstance(document_deferral_reason, str)
                or not document_deferral_reason.strip() or len(document_deferral_reason) > 1000
                or supporting_document is not None):
            raise LicenseSeriesError("Document deferral requires a reason and no substitute document.")
    license = LoanLicense.objects.select_for_update().get(workspace_id=workspace_id, pk=license_id)
    if not license.is_legacy_reference:
        raise LicenseSeriesError("This license is already verified. Reload its current setup.")
    previous = license.revisions.order_by("-revision_number").first()
    if not previous or previous.pk != expected_revision_id or previous.kind != "LEGACY_REFERENCE":
        raise LicenseSeriesError("License evidence changed. Reload and review it again.")
    today = timezone.localdate()
    if not all(type(day) is date for day in (issued_on, expires_on, source_as_of)) or not issued_on <= today <= expires_on or source_as_of > today:
        raise LicenseSeriesError("Provide currently valid license dates and a source review date no later than today.")
    if (supporting_document is None and not deferred) or not isinstance(issuing_authority, str) or not issuing_authority.strip():
        raise LicenseSeriesError("The issuing authority and supporting license document are required.")
    if (confirmed_complete is not True or not isinstance(source_sha256, str)
            or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
            or not isinstance(source_reference, str) or not source_reference.strip() or len(source_reference) > 255):
        raise LicenseSeriesError("Confirm the complete frozen source review, its SHA-256 and evidence reference.")
    series = list(LoanSeries.objects.select_for_update().filter(workspace_id=workspace_id, license=license).order_by("pk"))
    sequences = list(LoanNumberSequence.objects.select_for_update().filter(workspace_id=workspace_id, series__in=series).order_by("pk"))
    if numbering_review_digest(sequences) != expected_numbering_digest:
        raise LicenseSeriesError("Numbering changed since this review began. Reload and review it again.")
    expected_kinds = {"PAWN_LOAN", "PAWN_LOAN_RELEASE"}
    if not series or any({s.document_kind for s in sequences if s.series_id == row.pk} != expected_kinds for row in series):
        raise LicenseSeriesError("Configure both loan and release sequences for every series before verification.")
    if not isinstance(counters, dict) or set(counters) != {s.pk for s in sequences}:
        raise LicenseSeriesError("Review every current loan and release counter; reload if series were changed.")
    others = list(LoanNumberSequence.objects.filter(workspace_id=workspace_id).exclude(pk__in=[s.pk for s in sequences]))
    evidence_rows = []
    for sequence in sequences:
        last = counters[sequence.pk]
        if type(last) is not int or last < sequence.next_number - 1 or last > sequence.maximum_number:
            raise LicenseSeriesError(f"{sequence.series.code} {sequence.document_kind}: last used must be at least {sequence.next_number - 1} and no more than {sequence.maximum_number}.")
        for other in sequences + others:
            if other.pk != sequence.pk and other.document_kind == sequence.document_kind and _overlapping_prefixes(sequence.prefix, other.prefix):
                raise LicenseSeriesError(f"Number prefix {sequence.prefix!r} overlaps another {sequence.document_kind} sequence. Resolve the numbering conflict before verification.")
        model, field = (PawnLoan, "loan_number") if sequence.document_kind == "PAWN_LOAN" else (PawnLoanRelease, "release_number")
        for number in model.objects.filter(workspace_id=workspace_id, **{field + "__startswith": sequence.prefix}).values_list(field, flat=True).iterator():
            suffix = number[len(sequence.prefix):]
            if re.fullmatch(r"[0-9]+", suffix) and int(suffix) > last:
                raise LicenseSeriesError(f"{sequence.series.code}: the reviewed range omits existing number {number}.")
        evidence_rows.append({"sequence_id": sequence.pk, "series_id": sequence.series_id,
                              "kind": sequence.document_kind, "prefix": sequence.prefix,
                              "width": sequence.width, "maximum": sequence.maximum_number,
                              "previous_next": sequence.next_number, "last_used": last, "next_number": last + 1})
    for sequence in sequences:
        reserve_sequence_through(series=sequence.series, document_kind=sequence.document_kind,
                                 last_used_number=counters[sequence.pk], evidence_reference=source_reference, actor=actor)
    # Preserve the identity, old revision, all source loans and their frozen FKs.
    license.issued_on, license.expires_on = issued_on, expires_on
    license.issuing_authority = issuing_authority.strip()
    evidence = {"profile": "legacy-license-continuation/1", "previous_revision_id": previous.pk,
                "source_sha256": source_sha256, "source_as_of": source_as_of.isoformat(),
                "source_reference": source_reference.strip(), "confirmed_complete": True,
                "sequences": evidence_rows}
    if deferred:
        evidence.update(document_deferred=True, document_deferral_reason=document_deferral_reason.strip(),
                        validity_basis="owner_attested")
    revision = _record_license_revision(license,
                                        kind=LoanLicenseRevision.Kind.ATTESTATION if deferred else LoanLicenseRevision.Kind.VERIFICATION,
                                        actor=actor, supporting_document=supporting_document,
                                        verification_evidence=evidence)
    license.is_legacy_reference, license.is_active = False, True
    license.updated_by = actor
    license.full_clean()
    license.save(update_fields=["issued_on", "expires_on", "issuing_authority", "is_legacy_reference", "is_active", "updated_by", "updated_at"])
    _audit_license_revision(revision, actor=actor, request=request)
    return license
