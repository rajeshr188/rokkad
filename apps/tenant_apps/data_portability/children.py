"""Party child resolution and writes used by the shared staged lifecycle."""
import uuid

from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod, PartyIdentifier, PartyRole, PartyRoleType, PartyRelationship
from apps.tenant_apps.party.services.contact_details import save_address_form, save_contact_form, save_identifier_form, save_role_form, save_relationship_form
from . import child_contracts as contract
from .contracts import digest, issue, source_digest
from .models import ChildIdentity, ChildSourceIdentity, PartyIdentity, SourceIdentity, WorkspaceNamespace
from .parsers import PortabilityError


def parent_for(record, workspace_id):
    system, external = record["party_source_system"], record["party_external_id"]
    namespace = WorkspaceNamespace.objects.filter(workspace_id=workspace_id).first()
    if namespace and system == "rokkad:" + str(namespace.public_id):
        try:
            return PartyIdentity.objects.select_related("party").filter(workspace_id=workspace_id, public_id=uuid.UUID(external)).first()
        except ValueError:
            return None
    source = SourceIdentity.objects.select_related("identity__party").filter(workspace_id=workspace_id, source_system=system, external_id=external).first()
    return source.identity if source else None


def related_parent_for(record, workspace_id):
    return parent_for({"party_source_system": record["to_party_source_system"], "party_external_id": record["to_party_external_id"]}, workspace_id)


def child_party_id(obj):
    return obj.from_party_id if isinstance(obj, PartyRelationship) else obj.party_id


def child_object(identity):
    return getattr(identity, {contract.CONTACT: "contact", contract.ADDRESS: "address", contract.IDENTIFIER: "identifier", contract.ROLE: "role", contract.RELATIONSHIP: "relationship"}[identity.profile])


def source_for(batch, external):
    return ChildSourceIdentity.objects.select_related("identity__contact", "identity__address", "identity__identifier", "identity__role__role_type", "identity__relationship").filter(
        workspace_id=batch.workspace_id, profile=batch.contract_version, source_system=batch.source_system, external_id=external).first()


def existing_identity(batch, external):
    source = source_for(batch, external)
    if source:
        return source.identity
    namespace = WorkspaceNamespace.objects.filter(workspace_id=batch.workspace_id).first()
    if namespace and batch.source_system == "rokkad:" + str(namespace.public_id):
        try:
            return ChildIdentity.objects.select_related("contact", "address", "identifier", "role__role_type", "relationship").filter(
                workspace_id=batch.workspace_id, profile=batch.contract_version, public_id=uuid.UUID(external)).first()
        except ValueError:
            pass
    return None


def address_matches(record, workspace_id, party_id):
    match = {k + "__iexact": record[k] or "" for k in contract.ADDRESS_FIELDS if k != "is_default"}
    return PartyAddress.objects.filter(workspace_id=workspace_id, party_id=party_id, **match)


def resolve(record, external, batch, address_review=None):
    parent = parent_for(record, batch.workspace_id)
    if parent is None:
        return "CONFLICT", [issue("MISSING_PARENT", "party_external_id", "Import the Party master first, or use its exact source reference.")]
    source = source_for(batch, external)
    identity = existing_identity(batch, external)
    if identity:
        obj = child_object(identity)
        if obj is None or identity.parent_id != parent.pk or child_party_id(obj) != parent.party_id:
            return "CONFLICT", [issue("CHILD_CHANGED", "id", "The child was deleted, moved or belongs to a different Party.")]
        if batch.contract_version == contract.RELATIONSHIP:
            related = related_parent_for(record, batch.workspace_id)
            if related is None or identity.related_parent_id != related.pk or obj.to_party_id != related.party_id:
                return "CONFLICT", [issue("CHILD_CHANGED", "to_party_external_id", "The relationship destination changed.")]
        if source and source.accepted_digest != source_digest(record):
            return "CONFLICT", [issue("SOURCE_CHANGED", "", "Previously imported source values changed.")]
        if batch.contract_version == contract.ROLE and obj.role_type_id != record["_role_type"]["id"]:
            return "CONFLICT", [issue("ROLE_MAPPING_CHANGED", "role_type_key", "This source role is already bound to another destination type.")]
        expected = source.local_digest if source else None
        if (source and expected != digest(contract.local_state(batch.contract_version, obj))) or (not source and contract.semantic(batch.contract_version, obj) != {k: record[k] for k in contract.fields(batch.contract_version)}):
            return "CONFLICT", [issue("LOCAL_CHANGED", "", "The destination detail changed; automatic updates are unsupported.")]
        return "EXISTING", []
    namespace = WorkspaceNamespace.objects.filter(workspace_id=batch.workspace_id).first()
    if namespace and batch.source_system == "rokkad:" + str(namespace.public_id):
        return "CONFLICT", [issue("LOCAL_ID_CONFLICT", "id", "This local export identity is missing.")]
    profile = batch.contract_version
    if profile == contract.CONTACT:
        qs = PartyContactMethod.objects.filter(workspace_id=batch.workspace_id, party_id=parent.party_id)
        if qs.filter(contact_type=record["contact_type"], normalized_value=record["value"].strip().lower()).exists():
            return "CONFLICT", [issue("POSSIBLE_DUPLICATE", "value", "A matching contact already exists; it is not automatically bound.")]
        if record["is_primary"]:
            if qs.filter(contact_type=record["contact_type"], is_primary=True).exists():
                return "CONFLICT", [issue("PRIMARY_CONFLICT", "is_primary", "An existing primary contact would be replaced.")]
            summary = summary_field(record)
            if summary and getattr(parent.party, summary) and getattr(parent.party, summary) != record["value"]:
                return "NEW", [issue("SUMMARY_CHANGE", "value", "This primary contact updates the Party summary in source row order.", "WARNING", getattr(parent.party, summary), record["value"])]
    elif profile == contract.RELATIONSHIP:
        if PartyRelationship.objects.filter(workspace_id=batch.workspace_id, from_party_id=parent.party_id,
                to_party_id=record["_parties"]["to"], relationship_type=record["relationship_type"]).exists():
            return "CONFLICT", [issue("POSSIBLE_DUPLICATE", "relationship_type", "This directional relationship already exists; no automatic binding is performed.")]
    elif profile == contract.ROLE:
        qs = PartyRole.objects.filter(workspace_id=batch.workspace_id, party_id=parent.party_id, role_type_id=record["_role_type"]["id"])
        if record["status"] == "ACTIVE" and qs.filter(status="ACTIVE").exists():
            return "CONFLICT", [issue("ACTIVE_ROLE_CONFLICT", "role_type_key", "An active role of the mapped type already exists.")]
        if qs.filter(status=record["status"], segment=record["segment"] or "", effective_from=record["effective_from"], effective_to=record["effective_to"]).exists():
            return "CONFLICT", [issue("POSSIBLE_DUPLICATE", "role_type_key", "An identical role already exists; no automatic binding is performed.")]
    elif profile == contract.IDENTIFIER:
        if PartyIdentifier.objects.filter(workspace_id=batch.workspace_id, party_id=parent.party_id, identifier_type=record["identifier_type"]).exists():
            return "CONFLICT", [issue("IDENTIFIER_TYPE_CONFLICT", "identifier_type", "This Party already has an identifier of this type; automatic replacement is unsupported.")]
    else:
        qs = PartyAddress.objects.filter(workspace_id=batch.workspace_id, party_id=parent.party_id)
        matches = address_matches(record, batch.workspace_id, parent.party_id)
        if address_review is not None and (address_review["party_id"] != parent.party_id or
                set(matches.values_list("pk", flat=True)) != set(address_review["address_ids"])):
            return "CONFLICT", [issue("ADDRESS_REVIEW_CHANGED", "line1", "The parent or matching addresses changed since review.")]
        if address_review is None and matches.exists():
            return "CONFLICT", [issue("POSSIBLE_DUPLICATE", "line1", "A matching address already exists.")]
        if record["is_default"] and qs.filter(address_type=record["address_type"], is_default=True).exists():
            return "CONFLICT", [issue("DEFAULT_CONFLICT", "is_default", "An existing default address would be replaced.")]
    return "NEW", []


def summary_field(record):
    if record["contact_type"] == "EMAIL":
        return "primary_email"
    if record["contact_type"] in {"PHONE", "MOBILE", "WHATSAPP"}:
        return "primary_phone"
    return None


def duplicate_keys(record, batch):
    parent = parent_for(record, batch.workspace_id)
    if parent is None:
        return []
    if batch.contract_version == contract.RELATIONSHIP:
        return [(parent.pk, "relationship", record["_parties"]["to"], record["relationship_type"])]
    if batch.contract_version == contract.CONTACT:
        keys = [(parent.pk, "contact", record["contact_type"], record["value"].casefold())]
        if record["is_primary"]:
            keys.append((parent.pk, "primary", record["contact_type"]))
        return keys
    if batch.contract_version == contract.ROLE:
        keys = [(parent.pk, "role", record["_role_type"]["id"], record["status"], record["segment"], record["effective_from"], record["effective_to"])]
        if record["status"] == "ACTIVE":
            keys.append((parent.pk, "active_role", record["_role_type"]["id"]))
        return keys
    if batch.contract_version == contract.IDENTIFIER:
        return [(parent.pk, "identifier", record["identifier_type"])]
    keys = [(parent.pk, "address", tuple((record[k] or "").casefold() for k in contract.ADDRESS_FIELDS if k != "is_default"))]
    if record["is_default"]:
        keys.append((parent.pk, "default", record["address_type"]))
    return keys


def lock_destinations(batch, rows):
    parents = [parent_for(row.canonical, batch.workspace_id) for row in rows]
    if batch.contract_version == contract.RELATIONSHIP:
        parents += [related_parent_for(row.canonical, batch.workspace_id) for row in rows]
    ids = [p.party_id for p in parents if p]
    list(Party.objects.select_for_update().filter(workspace_id=batch.workspace_id, pk__in=ids).order_by("pk"))
    if batch.contract_version == contract.ROLE:
        role_type_ids = [row.canonical["_role_type"]["id"] for row in rows]
        list(PartyRoleType.objects.select_for_update().filter(workspace_id=batch.workspace_id, pk__in=role_type_ids).order_by("pk"))
    model = {contract.CONTACT: PartyContactMethod, contract.ADDRESS: PartyAddress, contract.IDENTIFIER: PartyIdentifier, contract.ROLE: PartyRole, contract.RELATIONSHIP: PartyRelationship}[batch.contract_version]
    parent_field = "from_party_id" if batch.contract_version == contract.RELATIONSHIP else "party_id"
    list(model.objects.select_for_update().filter(workspace_id=batch.workspace_id, **{parent_field + "__in": ids}).order_by("pk"))


def commit_row(batch, row, now):
    parent = parent_for(row.canonical, batch.workspace_id)
    identity = existing_identity(batch, row.external_id)
    if identity is None:
        form = contract.form_for(batch.contract_version, row.canonical)
        if not form.is_valid():
            raise PortabilityError("The child no longer validates.")
        if batch.contract_version == contract.CONTACT:
            obj = save_contact_form(form, parent.party)
            relation = {"contact": obj}
        elif batch.contract_version == contract.RELATIONSHIP:
            if form.instance.pk:
                raise PortabilityError("A relationship appeared after preview.")
            obj = save_relationship_form(form, parent.party)
            relation = {"relationship": obj, "related_parent": related_parent_for(row.canonical, batch.workspace_id)}
        elif batch.contract_version == contract.ROLE:
            obj = save_role_form(form, parent.party)
            relation = {"role": obj}
        elif batch.contract_version == contract.IDENTIFIER:
            obj = save_identifier_form(form, parent.party)
            relation = {"identifier": obj}
        else:
            obj = save_address_form(form, parent.party)
            relation = {"address": obj}
        identity = ChildIdentity.objects.create(workspace_id=batch.workspace_id, parent=parent, profile=batch.contract_version, **relation)
    obj = child_object(identity)
    if source_for(batch, row.external_id) is None:
        ChildSourceIdentity.objects.create(workspace_id=batch.workspace_id, profile=batch.contract_version,
            source_system=batch.source_system, external_id=row.external_id, identity=identity,
            accepted_digest=source_digest(row.canonical), local_digest=digest(contract.local_state(batch.contract_version, obj)))
    row.identity, row.child_identity, row.committed_at = parent, identity, now
    row.save(update_fields=["identity", "child_identity", "committed_at"])
