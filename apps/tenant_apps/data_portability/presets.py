"""Immutable Workspace tabular mapping versions; applying always requires a new preview."""
from copy import deepcopy
import json

from django.db import transaction
from django.core.exceptions import ValidationError
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from .access import require_access
from .mapping import validate_mapping
from .models import MappingPresetVersion
from .parsers import PortabilityError

MAX_VERSIONS = 1000


def compatible(preset, batch):
    return (batch.source_type in {"csv", "xlsx"} and preset.profile == batch.contract_version
            and preset.source_system == batch.source_system and sorted(preset.headers) == sorted(batch.headers))


def available_presets(*, workspace_id, actor, batch):
    require_access(workspace_id, actor, "import")
    if batch.workspace_id != workspace_id:
        raise PortabilityError("The batch is unavailable in this Workspace.")
    return [p for p in MappingPresetVersion.objects.filter(workspace_id=workspace_id,
        profile=batch.contract_version, source_system=batch.source_system).order_by("name", "-version").defer("mapping")[:MAX_VERSIONS]
        if compatible(p, batch)]


def preset_for_batch(public_id, batch):
    try:
        preset = MappingPresetVersion.objects.get(workspace_id=batch.workspace_id, public_id=public_id)
    except (MappingPresetVersion.DoesNotExist, ValueError, TypeError, ValidationError) as exc:
        raise PortabilityError("The preset version is unavailable.") from exc
    if not compatible(preset, batch):
        raise PortabilityError("Preset profile, source system and CSV/XLSX header names must match this batch exactly.")
    return preset


@transaction.atomic
def save_preset(*, workspace_id, actor, batch_id, name, approval_digest):
    from .services import _batch, _approval
    workspace = require_access(workspace_id, actor, "import")
    Company.all_objects.select_for_update().get(pk=workspace_id)
    require_access(workspace_id, actor, "import")
    batch = _batch(workspace_id, batch_id, lock=True)
    if batch.source_type not in {"csv", "xlsx"} or batch.state not in {"READY", "COMPLETED"}:
        raise PortabilityError("Save a preset from a validated, error-free CSV/XLSX preview or completed CSV/XLSX batch.")
    if approval_digest != batch.approval_digest or _approval(batch, list(batch.rows.order_by("source_row"))) != approval_digest:
        raise PortabilityError("The preview changed. Review it before saving a preset.")
    if batch.mapping.get("name_reviews") or batch.mapping.get("address_reviews"):
        raise PortabilityError("Customer identity decisions belong to this batch and cannot be saved in a reusable mapping preset.")
    if not isinstance(name, str) or not name or len(name) > 80 or name != name.strip() or any(ord(c) < 32 for c in name):
        raise PortabilityError("Use a nonempty preset name of at most 80 characters without surrounding whitespace or control characters.")
    mapping = validate_mapping(deepcopy(batch.mapping), batch.headers, "csv", batch.contract_version)
    if len(json.dumps(mapping, ensure_ascii=False).encode("utf-8")) > 262144:
        raise PortabilityError("The preset mapping exceeds its bounded storage limit.")
    latest = MappingPresetVersion.objects.filter(workspace_id=workspace_id, name=name).order_by("-version").first()
    if latest:
        if latest.profile != batch.contract_version or latest.source_system != batch.source_system:
            raise PortabilityError("This preset name belongs to another profile or source system. Choose a new name.")
        if latest.mapping == mapping and sorted(latest.headers) == sorted(batch.headers):
            return latest
    if MappingPresetVersion.objects.filter(workspace_id=workspace_id).count() >= MAX_VERSIONS:
        raise PortabilityError("This Workspace has reached the limit of 1,000 retained preset versions.")
    preset = MappingPresetVersion.objects.create(workspace_id=workspace_id, name=name,
        version=latest.version + 1 if latest else 1, profile=batch.contract_version,
        source_system=batch.source_system, headers=sorted(batch.headers), mapping=mapping, created_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, description="Saved a tabular mapping preset version.",
        data={"batch": str(batch.public_id), "preset": str(preset.public_id), "version": preset.version, "profile": preset.profile,
              "approval": approval_digest, "revision": batch.revision})
    return preset
