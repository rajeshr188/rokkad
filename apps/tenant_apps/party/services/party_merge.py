from dataclasses import dataclass, field

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.dea.models import PartyAccountMapping, PartyAccountMappingStatus
from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
)


class PartyMergeConflict(ValidationError):
    """Raised when a merge would hide conflicting business data."""


@dataclass(frozen=True)
class PartyMergeResult:
    target: Party
    source: Party
    roles_moved: int = 0
    contacts_moved: int = 0
    addresses_moved: int = 0
    identifiers_moved: int = 0
    documents_moved: int = 0
    relationships_moved: int = 0
    account_mappings_moved: int = 0
    skipped: list[str] = field(default_factory=list)


@transaction.atomic
def merge_parties(*, target, source, actor=None):
    """Merge a duplicate source Party into target without mutating ledger facts.

    The source Party is archived instead of deleted so audit history, skipped
    relationships, and any intentionally unresolved source data remain visible.
    """
    if target.pk == source.pk:
        raise PartyMergeConflict("A party cannot be merged into itself.")

    target = Party.objects.select_for_update().get(pk=target.pk)
    source = Party.objects.select_for_update().get(pk=source.pk)
    conflicts = _merge_conflicts(target, source)
    if conflicts:
        raise PartyMergeConflict(conflicts)

    _merge_summary_fields(target, source)
    roles_moved, role_skips = _merge_roles(target, source)
    contacts_moved = _move_contacts(target, source)
    addresses_moved = _move_addresses(target, source)
    identifiers_moved = _move_identifiers(target, source)
    documents_moved = source.documents.update(party=target)
    relationships_moved, relationship_skips = _move_relationships(target, source)
    account_mappings_moved = _move_account_mappings(target, source)
    _move_legacy_customer(target, source)
    _archive_source_party(target, source, actor=actor)

    return PartyMergeResult(
        target=target,
        source=source,
        roles_moved=roles_moved,
        contacts_moved=contacts_moved,
        addresses_moved=addresses_moved,
        identifiers_moved=identifiers_moved,
        documents_moved=documents_moved,
        relationships_moved=relationships_moved,
        account_mappings_moved=account_mappings_moved,
        skipped=role_skips + relationship_skips,
    )


def _merge_conflicts(target, source):
    conflicts = []
    if getattr(target, "legacy_customer", None) and getattr(source, "legacy_customer", None):
        conflicts.append(
            "Both parties are linked to legacy customers. Merge the legacy customer "
            "records first or wait for operational foreign-key migration."
        )

    target_identifiers = {
        identifier.identifier_type: identifier
        for identifier in target.identifiers.all()
    }
    for identifier in source.identifiers.all():
        target_identifier = target_identifiers.get(identifier.identifier_type)
        if target_identifier and target_identifier.value != identifier.value:
            conflicts.append(
                f"Identifier conflict for {identifier.get_identifier_type_display()}."
            )

    target_mapping_keys = set(
        PartyAccountMapping.objects.filter(
            party=target,
            status=PartyAccountMappingStatus.ACTIVE,
        ).values_list("role_key", "purpose", "event_type")
    )
    for role_key, purpose, event_type in PartyAccountMapping.objects.filter(
        party=source,
        status=PartyAccountMappingStatus.ACTIVE,
    ).values_list("role_key", "purpose", "event_type"):
        if (role_key, purpose, event_type) in target_mapping_keys:
            conflicts.append(
                f"DEA account mapping conflict for {role_key}/{purpose}"
                f"{'/' + event_type if event_type else ''}."
            )

    return conflicts


def _merge_summary_fields(target, source):
    update_fields = []
    for field_name in [
        "legal_name",
        "relation_label",
        "relation_name",
        "primary_phone",
        "primary_email",
        "profile_photo",
        "tax_pan",
        "gstin",
        "risk_level",
    ]:
        if not getattr(target, field_name) and getattr(source, field_name):
            setattr(target, field_name, getattr(source, field_name))
            update_fields.append(field_name)

    metadata = dict(target.metadata or {})
    merged_from = list(metadata.get("merged_from_party_ids", []))
    if source.pk not in merged_from:
        merged_from.append(source.pk)
    metadata["merged_from_party_ids"] = merged_from
    target.metadata = metadata
    update_fields.append("metadata")

    if update_fields:
        update_fields.append("updated_at")
        target.save(update_fields=update_fields)


def _merge_roles(target, source):
    moved = 0
    skipped = []
    target_active_role_type_ids = set(
        target.roles.filter(status=PartyRole.RoleStatus.ACTIVE).values_list(
            "role_type_id",
            flat=True,
        )
    )
    for role in source.roles.all():
        if (
            role.status == PartyRole.RoleStatus.ACTIVE
            and role.role_type_id in target_active_role_type_ids
        ):
            skipped.append(f"Skipped duplicate active role {role.role_type}.")
            continue
        role.party = target
        role.save(update_fields=["party", "updated_at"])
        moved += 1
    return moved, skipped


def _move_contacts(target, source):
    moved = 0
    for contact in source.contact_methods.all():
        if (
            contact.is_primary
            and PartyContactMethod.objects.filter(
                party=target,
                contact_type=contact.contact_type,
                is_primary=True,
            ).exists()
        ):
            contact.is_primary = False
        contact.party = target
        contact.save(update_fields=["party", "is_primary", "updated_at"])
        moved += 1
    return moved


def _move_addresses(target, source):
    moved = 0
    for address in source.addresses.all():
        if (
            address.is_default
            and PartyAddress.objects.filter(
                party=target,
                address_type=address.address_type,
                is_default=True,
            ).exists()
        ):
            address.is_default = False
        address.party = target
        address.save(update_fields=["party", "is_default", "updated_at"])
        moved += 1
    return moved


def _move_identifiers(target, source):
    moved = 0
    target_identifiers = {
        identifier.identifier_type: identifier
        for identifier in target.identifiers.all()
    }
    for identifier in source.identifiers.all():
        target_identifier = target_identifiers.get(identifier.identifier_type)
        if target_identifier:
            source.documents.filter(identifier=identifier).update(
                identifier=target_identifier
            )
            continue
        identifier.party = target
        identifier.save(update_fields=["party", "updated_at"])
        target_identifiers[identifier.identifier_type] = identifier
        moved += 1
    return moved


def _move_relationships(target, source):
    moved = 0
    skipped = []
    for relationship in source.relationships_from.all():
        if relationship.to_party_id == target.pk:
            skipped.append("Skipped outgoing relationship that would become self-linked.")
            continue
        if PartyRelationship.objects.filter(
            from_party=target,
            to_party=relationship.to_party,
            relationship_type=relationship.relationship_type,
        ).exists():
            skipped.append(f"Skipped duplicate outgoing relationship {relationship}.")
            continue
        relationship.from_party = target
        relationship.save(update_fields=["from_party", "updated_at"])
        moved += 1

    for relationship in source.relationships_to.all():
        if relationship.from_party_id == target.pk:
            skipped.append("Skipped incoming relationship that would become self-linked.")
            continue
        if PartyRelationship.objects.filter(
            from_party=relationship.from_party,
            to_party=target,
            relationship_type=relationship.relationship_type,
        ).exists():
            skipped.append(f"Skipped duplicate incoming relationship {relationship}.")
            continue
        relationship.to_party = target
        relationship.save(update_fields=["to_party", "updated_at"])
        moved += 1
    return moved, skipped


def _move_account_mappings(target, source):
    return PartyAccountMapping.objects.filter(party=source).update(party=target)


def _move_legacy_customer(target, source):
    source_customer = getattr(source, "legacy_customer", None)
    if source_customer and not getattr(target, "legacy_customer", None):
        source_customer.party = target
        source_customer.save(update_fields=["party"])


def _archive_source_party(target, source, actor=None):
    metadata = dict(source.metadata or {})
    metadata.update(
        {
            "merged_into_party_id": target.pk,
            "merged_at": timezone.now().isoformat(),
        }
    )
    if actor is not None and getattr(actor, "pk", None):
        metadata["merged_by_user_id"] = actor.pk
    source.metadata = metadata
    source.status = Party.PartyStatus.ARCHIVED
    source.save(update_fields=["status", "metadata", "updated_at"])
