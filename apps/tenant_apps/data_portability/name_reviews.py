"""Explicit per-source customer decisions, bound to the existing import preview."""
from copy import deepcopy
from django.db import transaction
from apps.orgs.models import Company
from apps.orgs.audit import AuditLog
from apps.tenant_apps.party.models import Party
from .access import require_access
from .contracts import PROFILE, source_digest
from .parsers import PortabilityError
from .services import _batch, _approval, validate_import


@transaction.atomic
def review_distinct_names(*, workspace_id, actor, batch_id, external_ids, reason, approval_digest):
    workspace = require_access(workspace_id, actor, "commit")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    batch = _batch(workspace_id, batch_id, lock=True)
    rows = list(batch.rows.order_by("source_row"))
    if batch.contract_version != PROFILE or batch.state not in {"NEEDS_MAPPING", "READY"} or not batch.mapping:
        raise PortabilityError("Validate an unfinished customer master batch before reviewing names.")
    if not approval_digest or approval_digest != batch.approval_digest or _approval(batch, rows) != approval_digest:
        raise PortabilityError("The preview changed. Review the current customer rows.")
    if (not isinstance(external_ids, list) or not 1 <= len(external_ids) <= 1000
            or any(not isinstance(pk, str) for pk in external_ids) or len(set(external_ids)) != len(external_ids)):
        raise PortabilityError("Select 1–1,000 distinct source customer IDs.")
    if (not isinstance(reason, str) or not reason.strip() or len(reason) > 255
            or any(ord(c) < 32 or ord(c) == 127 for c in reason)):
        raise PortabilityError("Record why these source customer IDs represent separate customers (up to 255 characters).")
    indexed = {}
    for row in rows:
        indexed.setdefault(row.external_id, []).append(row)
    mapping = deepcopy(batch.mapping)
    reviews = mapping.setdefault("name_reviews", {})
    for external in external_ids:
        selected = indexed.get(external, [])
        if len(selected) != 1 or not external:
            raise PortabilityError("Each reviewed source ID must identify exactly one row in this batch.")
        row = selected[0]
        if any(i["severity"] == "ERROR" and i["code"] not in {"DUPLICATE_ROW", "POSSIBLE_DUPLICATE", "NAME_REVIEW_CHANGED"} for i in row.issues):
            raise PortabilityError("Correct other customer validation errors before reviewing names.")
        matches = list(Party.objects.filter(workspace_id=workspace_id,
            display_name__iexact=row.canonical["name"]).order_by("pk").values_list("pk", flat=True)[:1001])
        if len(matches) > 1000:
            raise PortabilityError("Too many matching customers for this bounded name review.")
        reviews[external] = {"record_sha256": source_digest(row.canonical), "party_ids": matches, "reason": reason.strip()}
    updated = validate_import(workspace_id=workspace_id, actor=actor, batch_id=batch_id, mapping=mapping)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor,
        description="Reviewed distinct customer source identities with matching names.",
        data={"batch": str(batch.public_id), "source_sha256": batch.source_sha256,
              "external_ids": external_ids, "reason": reason.strip(), "approval": updated.approval_digest})
    return updated
