"""Explicit customer-status repair from recorded loan relationships, not debt."""
import hashlib
import json
import re
from collections import Counter
from uuid import uuid5

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.orgs.audit import AuditLog
from apps.tenant_apps.data_portability.models import SourceIdentity
from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.action_access import require_party_service_permission
from apps.tenant_apps.loans.models import HistoricalLoanEvidence, PawnLoan


def _archive_party(row, aliases):
    reference = row["document"].get("facts", {}).get("borrower_reference") or {}
    system, external = reference.get("system"), reference.get("id")
    if system != row["source_system"] or not isinstance(external, str):
        return None
    if system.startswith("legacy:"):
        prefix = f"legacy:{row['source_namespace'].hex}:"
        schema = system.removeprefix(prefix)
        if (not system.startswith(prefix) or schema == "public"
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema)
                or not re.fullmatch(r"contact_customer:[1-9][0-9]*", external)):
            return None
        # Same stable UUID transformation as the accepted legacy Party import.
        external = str(uuid5(uuid5(row["source_namespace"], schema), external))
    return aliases.get((system, external))


@transaction.atomic
def repair_customer_statuses(*, workspace_id, actor, apply=False, expected_digest=None):
    workspace = require_party_service_permission(workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
    parties = Party.objects.filter(workspace_id=workspace_id).order_by("pk")
    if apply:
        # Also serialize ordinary borrower-FK admissions with this short repair.
        parties = parties.select_for_update()
    parties = list(parties)
    loans = list(PawnLoan.objects.filter(workspace_id=workspace_id).order_by("pk").values("id", "borrower_id"))
    sources = list(SourceIdentity.objects.filter(workspace_id=workspace_id,
        identity__workspace_id=workspace_id, identity__party__workspace_id=workspace_id).order_by("pk").values(
            "id", "source_system", "external_id", "identity__party_id"))
    aliases = {(r["source_system"], r["external_id"]): r["identity__party_id"] for r in sources}
    ordinary = {r["borrower_id"] for r in loans}
    historical, archive_inputs, unresolved = set(), [], 0
    for row in HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id).order_by("pk").values(
            "id", "source_namespace", "source_system", "source_id", "source_sha256", "document").iterator():
        party_id = _archive_party(row, aliases)
        unresolved += party_id is None
        if party_id is not None:
            historical.add(party_id)
        archive_inputs.append({k: v for k, v in row.items() if k != "document"} | {
            "borrower_reference": row["document"].get("facts", {}).get("borrower_reference"), "party_id": party_id})
    linked = ordinary | historical
    historical_only = historical - ordinary
    counts = Counter(active=0, inactive=0, historical_only=0, activate=0, deactivate=0, protected=0)
    changes = []
    for party in parties:
        target = Party.PartyStatus.ACTIVE if party.pk in linked else Party.PartyStatus.INACTIVE
        counts["active" if party.pk in linked else "inactive"] += 1
        counts["historical_only"] += party.pk in historical_only
        counts["protected"] += party.status in ("BLOCKED", "ARCHIVED") or bool(party.metadata.get("merged_into_party_id"))
        if party.status != target:
            changes.append((party, target))
            counts["activate" if target == "ACTIVE" else "deactivate"] += 1
    inputs = [workspace_id, [{"id": p.pk, "status": p.status, "metadata": p.metadata} for p in parties],
              loans, sources, archive_inputs]
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()
    report = dict(workspace_id=workspace_id, parties=len(parties), counts=dict(counts),
                  unresolved_archives=unresolved, candidate_count=len(changes), digest=digest, applied=False)
    if not apply:
        return report
    if not expected_digest or expected_digest != digest:
        raise ValidationError("Loan relationships or customer statuses changed. Preview again before applying.")
    if unresolved or counts["protected"]:
        raise ValidationError("Resolve unmatched historical borrowers or blocked/archived/merged customers before applying.")
    for party, target in changes:
        before = party.status
        party.status = target
        party.updated_by = actor
        party.save(update_fields=["status", "updated_by", "updated_at"])
        AuditLog.log("UPDATE", user=actor, company=workspace, content_object=party,
            description="Reconciled customer status with recorded loan history.",
            data={"operation": "PARTY_STATUS_CHANGE", "field": "status", "before": before, "after": target,
                  "reason": "RECORDED_LOAN_HISTORY", "ordinary_loan": party.pk in ordinary,
                  "retained_historical_loan": party.pk in historical})
    return report | {"applied": True, "changed": len(changes)}
