"""Shared Party child writes; callers provide an authorized Party."""
from django.db import transaction
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod

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


def save_contact_form(form, party):
    contact = form.save(commit=False)
    contact.party = party
    old_contact = None
    if contact.pk:
        old_contact = PartyContactMethod.objects.get(pk=contact.pk)
    with transaction.atomic():
        party = Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        if contact.is_primary:
            PartyContactMethod.objects.filter(
                party=party,
                contact_type=contact.contact_type,
                is_primary=True,
            ).exclude(pk=contact.pk).update(is_primary=False)
        contact.save()
        sync_party_primary_contact(party, contact, old_contact=old_contact)
    return contact


def save_address_form(form, party):
    address = form.save(commit=False)
    address.party = party
    with transaction.atomic():
        Party.objects.select_for_update().get(pk=party.pk, workspace_id=party.workspace_id)
        if address.is_default:
            PartyAddress.objects.filter(
                party=party,
                address_type=address.address_type,
                is_default=True,
            ).exclude(pk=address.pk).update(is_default=False)
        address.save()
    return address




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
