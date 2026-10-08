"""Shared Party child writes; callers provide an authorized Party."""
from django.db import transaction
from apps.orgs.audit import AuditLog
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod


@transaction.atomic
def ensure_party_display_defaults(*, workspace_id, party_id, actor):
    """Fill missing display choices without replacing facts or existing choices."""
    from .action_access import require_party_service_permission
    from apps.tenant_apps.party.access import PARTY_ACTION_PERMISSIONS

    require_party_service_permission(workspace_id, actor, *PARTY_ACTION_PERMISSIONS["edit"])
    party = Party.objects.select_for_update().get(pk=party_id, workspace_id=workspace_id)
    addresses = list(PartyAddress.objects.filter(party=party, workspace_id=workspace_id).order_by("pk"))
    phones = list(PartyContactMethod.objects.filter(party=party, workspace_id=workspace_id,
        contact_type__in=("PHONE", "MOBILE", "WHATSAPP")).order_by("pk"))
    phones = [phone for phone in phones if phone.value.strip()]
    changed = {"address_id": None, "contact_id": None, "phone_summary": False}

    if not any(address.is_default for address in addresses):
        eligible = [address for address in addresses if str(address).strip()]
        address = next((row for row in eligible if row.address_type == "HOME"),
                       eligible[0] if eligible else None)
        if address:
            address.is_default = True
            address.save(update_fields=["is_default", "updated_at"])
            _audit_flag(address, party, actor, "is_default", False, True)
            changed["address_id"] = address.pk

    primary = [phone for phone in phones if phone.is_primary]
    summary = party.primary_phone.strip()
    if not primary:
        # Respect a phone already chosen on the master, including legacy format.
        # An unrelated contact must not silently replace that existing choice.
        phone = next((row for row in phones if row.value.strip() == summary), None) if summary else (
            phones[0] if phones else None)
        if phone:
            phone.is_primary = True
            phone.save(update_fields=["is_primary", "updated_at"])
            _audit_flag(phone, party, actor, "is_primary", False, True)
            changed["contact_id"] = phone.pk
            primary = [phone]
    if not summary and primary:
        sync_party_primary_contact(party, primary[0])
        AuditLog.log("UPDATE", user=actor, company=party.workspace, content_object=party,
            description="Filled a missing customer primary phone from an existing contact.",
            data={"operation": "PARTY_PRIMARY_PHONE_SYNC", "party_id": party.pk,
                  "contact_id": primary[0].pk, "field": "primary_phone",
                  "before_present": False, "after_present": True})
        changed["phone_summary"] = True
    return changed

def sync_party_primary_contact(party, contact, *, old_contact=None, deleted=False):
    phone_types = {
        PartyContactMethod.ContactType.PHONE,
        PartyContactMethod.ContactType.MOBILE,
        PartyContactMethod.ContactType.WHATSAPP,
    }
    update_fields = []

    if deleted:
        if contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            if party.primary_email == contact.value:
                party.primary_email = ""
                update_fields.append("primary_email")
        elif contact.contact_type in phone_types and party.primary_phone == contact.value:
            party.primary_phone = ""
            update_fields.append("primary_phone")
    elif contact.is_primary:
        if contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            party.primary_email = contact.value
            update_fields.append("primary_email")
        elif contact.contact_type in phone_types:
            party.primary_phone = contact.value
            update_fields.append("primary_phone")
    elif old_contact and old_contact.is_primary:
        if old_contact.contact_type == PartyContactMethod.ContactType.EMAIL:
            if party.primary_email == old_contact.value:
                party.primary_email = ""
                update_fields.append("primary_email")
        elif old_contact.contact_type in phone_types and party.primary_phone == old_contact.value:
            party.primary_phone = ""
            update_fields.append("primary_phone")

    if update_fields:
        update_fields.append("updated_at")
        party.save(update_fields=update_fields)


def _audit_flag(obj, party, actor, field, before, after):
    if actor is not None and before != after:
        AuditLog.log('UPDATE', user=actor, company=party.workspace, content_object=obj,
            description='Changed a customer contact/address default.',
            data={'operation': 'PARTY_DEFAULT_CHANGE', 'party_id': party.pk,
                  'field': field, 'before': before, 'after': after})


def save_contact_form(form, party, *, actor=None):
    contact = form.save(commit=False)
    contact.party = party
    with transaction.atomic():
        party = Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        old_contact = PartyContactMethod.objects.get(pk=contact.pk, party=party) if contact.pk else None
        if contact.is_primary:
            demoted = list(PartyContactMethod.objects.filter(
                party=party,
                contact_type=contact.contact_type,
                is_primary=True,
            ).exclude(pk=contact.pk))
            PartyContactMethod.objects.filter(pk__in=[c.pk for c in demoted]).update(is_primary=False)
            for previous in demoted:
                _audit_flag(previous, party, actor, 'is_primary', True, False)
        contact.save()
        sync_party_primary_contact(party, contact, old_contact=old_contact)
        _audit_flag(contact, party, actor, 'is_primary', old_contact.is_primary if old_contact else None, contact.is_primary)
    return contact


def save_address_form(form, party, *, actor=None):
    address = form.save(commit=False)
    address.party = party
    with transaction.atomic():
        Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        previous = PartyAddress.objects.get(pk=address.pk, party=party) if address.pk else None
        if address.is_default:
            demoted = list(PartyAddress.objects.filter(
                party=party,
                address_type=address.address_type,
                is_default=True,
            ).exclude(pk=address.pk))
            PartyAddress.objects.filter(pk__in=[a.pk for a in demoted]).update(is_default=False)
            for old in demoted:
                _audit_flag(old, party, actor, 'is_default', True, False)
        address.save()
        _audit_flag(address, party, actor, 'is_default', previous.is_default if previous else None, address.is_default)
    return address


@transaction.atomic
def delete_contact(*, party, contact_id, actor):
    party = Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
    contact = PartyContactMethod.objects.get(pk=contact_id, party=party)
    _audit_flag(contact, party, actor, 'is_primary', contact.is_primary, None)
    sync_party_primary_contact(party, contact, deleted=True)
    contact.delete()


@transaction.atomic
def delete_address(*, party, address_id, actor):
    Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
    address = PartyAddress.objects.get(pk=address_id, party=party)
    _audit_flag(address, party, actor, 'is_default', address.is_default, None)
    address.delete()




def save_identifier_form(form, party):
    """Save an identifier through the native form; caller authorizes Party edit."""
    with transaction.atomic():
        Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        form.party = party
        if not form.is_valid():
            from django.core.exceptions import ValidationError
            raise ValidationError("A valid identifier form is required.")
        identifier = form.save(commit=False)
        identifier.party = party
        identifier.save()
        return identifier


def save_role_form(form, party):
    """Caller authorizes Party edit; keep native role validation and uniqueness."""
    with transaction.atomic():
        Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        if not form.is_valid():
            from django.core.exceptions import ValidationError
            raise ValidationError("A valid Party role form is required.")
        role = form.save(commit=False)
        role.party = party
        role.save()
        return role


def save_relationship_form(form, party):
    """Caller authorizes Party edit; lock both endpoints in stable order."""
    with transaction.atomic():
        if not form.is_valid():
            from django.core.exceptions import ValidationError
            raise ValidationError("A valid Party relationship form is required.")
        relationship = form.save(commit=False)
        list(Party.objects.select_for_update().filter(workspace_id=party.workspace_id,
            pk__in=[party.pk, relationship.to_party_id]).order_by("pk"))
        relationship.from_party = party
        relationship.save()
        return relationship
