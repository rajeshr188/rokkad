from dataclasses import dataclass
from hashlib import sha256

from django.db import transaction

from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyIdentifier,
    PartyRole,
    PartyRoleType,
)
from apps.tenant_apps.party.services.role_seed import seed_party_roles


CUSTOMER_TYPE_ROLE_MAP = {
    "R": ("CUSTOMER", "RETAIL"),
    "W": ("CUSTOMER", "WHOLESALE"),
    "S": ("SUPPLIER", ""),
}

CONTACT_TYPE_MAP = {
    "H": PartyContactMethod.ContactType.PHONE,
    "O": PartyContactMethod.ContactType.PHONE,
    "M": PartyContactMethod.ContactType.MOBILE,
}

PROOF_TYPE_MAP = {
    "AA": PartyIdentifier.IdentifierType.AADHAAR,
    "DL": PartyIdentifier.IdentifierType.DRIVING_LICENSE,
    "PN": PartyIdentifier.IdentifierType.PAN,
    "PP": PartyIdentifier.IdentifierType.PASSPORT,
    "VI": PartyIdentifier.IdentifierType.OTHER,
}

RELATION_LABEL_MAP = {
    "s": Party.RelationLabel.SON_OF,
    "d": Party.RelationLabel.DAUGHTER_OF,
    "c": Party.RelationLabel.CARE_OF,
    "p": Party.RelationLabel.PARENT_OF,
    "f": Party.RelationLabel.FATHER_OF,
    "w": Party.RelationLabel.WIFE_OF,
    "h": Party.RelationLabel.HUSBAND_OF,
    "o": Party.RelationLabel.OTHER,
}


@dataclass(frozen=True)
class CustomerPartyBackfillResult:
    processed: int = 0
    linked: int = 0
    created: int = 0
    roles_created: int = 0


def backfill_customer_parties(queryset=None):
    from apps.tenant_apps.contact.models import Customer

    seed_party_roles()
    customers = queryset or Customer.objects.all()
    result = CustomerPartyBackfillResult()

    processed = linked = created = roles_created = 0
    for customer in customers.select_related("party").prefetch_related(
        "contactno",
        "address",
        "proofs",
    ):
        outcome = ensure_customer_party(customer, seed_roles=False)
        processed += 1
        linked += int(outcome["linked"])
        created += int(outcome["created"])
        roles_created += outcome["roles_created"]

    return CustomerPartyBackfillResult(
        processed=processed,
        linked=linked,
        created=created,
        roles_created=roles_created,
    )


@transaction.atomic
def ensure_customer_party(customer, seed_roles=True):
    if seed_roles:
        seed_party_roles()

    created = False
    if customer.party_id:
        party = customer.party
    else:
        party = Party.objects.create(
            party_code=_customer_party_code(customer),
            party_type=Party.PartyType.INDIVIDUAL,
            display_name=customer.name,
            legal_name=customer.name,
            relation_label=_customer_relation_label(customer),
            relation_name=(customer.relatedto or "").strip(),
            primary_email=customer.email or "",
            primary_phone=_default_customer_phone(customer),
            status=(
                Party.PartyStatus.ACTIVE
                if customer.active
                else Party.PartyStatus.INACTIVE
            ),
            created_by=customer.created_by,
            metadata={
                "legacy_customer_id": customer.id,
                "legacy_customer_type": customer.customer_type,
            },
        )
        customer.party = party
        customer.save(update_fields=["party"])
        created = True

    roles_created = _ensure_customer_role(customer, party)
    _sync_party_relation(customer, party)
    _sync_contact_methods(customer, party)
    _sync_addresses(customer, party)
    _sync_identifiers(customer, party)

    return {"linked": True, "created": created, "roles_created": roles_created}


@transaction.atomic
def ensure_party_customer(party, *, created_by=None, seed_roles=True):
    """Ensure a Party has a compatibility Customer for legacy workflows."""
    from apps.tenant_apps.contact.models import Customer

    if seed_roles:
        seed_party_roles()

    try:
        customer = party.legacy_customer
        created = False
    except Customer.DoesNotExist:
        first_name, last_name = _split_party_name(party.display_name)
        customer = Customer.objects.create(
            party=party,
            firstname=first_name,
            lastname=last_name,
            email=party.primary_email or None,
            customer_type=Customer.CustomerType.Retail,
            relatedas=_party_customer_relation_label(party),
            relatedto=party.relation_name or None,
            active=party.status == Party.PartyStatus.ACTIVE,
            created_by=created_by,
        )
        created = True

    borrower_role, _role_created = PartyRole.objects.get_or_create(
        party=party,
        role_type=PartyRoleType.objects.get(key="BORROWER"),
        status=PartyRole.RoleStatus.ACTIVE,
    )
    customer_role_created = _ensure_customer_role(customer, party)

    return {
        "customer": customer,
        "created": created,
        "borrower_role_created": int(_role_created),
        "customer_role_created": customer_role_created,
        "borrower_role": borrower_role,
    }


def _customer_party_code(customer):
    base = f"CUST-{customer.id:06d}"
    if not Party.objects.filter(party_code=base).exists():
        return base

    suffix = 1
    while True:
        candidate = f"{base}-{suffix}"
        if not Party.objects.filter(party_code=candidate).exists():
            return candidate
        suffix += 1


def _split_party_name(display_name):
    name = (display_name or "").strip()
    if not name:
        return "Unnamed Party", ""
    parts = name.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def _party_customer_relation_label(party):
    reverse_map = {value: key for key, value in RELATION_LABEL_MAP.items()}
    return reverse_map.get(party.relation_label or "", "o")


def _ensure_customer_role(customer, party):
    role_key, segment = CUSTOMER_TYPE_ROLE_MAP.get(customer.customer_type, ("CUSTOMER", ""))
    role_type = PartyRoleType.objects.get(key=role_key)
    _role, created = PartyRole.objects.get_or_create(
        party=party,
        role_type=role_type,
        status=PartyRole.RoleStatus.ACTIVE,
        defaults={"segment": segment},
    )
    return int(created)


def _customer_relation_label(customer):
    relatedto = (customer.relatedto or "").strip()
    if not relatedto:
        return ""
    return RELATION_LABEL_MAP.get(customer.relatedas, Party.RelationLabel.OTHER)


def _sync_party_relation(customer, party):
    relation_label = _customer_relation_label(customer)
    relation_name = (customer.relatedto or "").strip()
    if party.relation_label == relation_label and party.relation_name == relation_name:
        return
    party.relation_label = relation_label
    party.relation_name = relation_name
    party.save(update_fields=["relation_label", "relation_name", "updated_at"])


def _default_customer_phone(customer):
    contact = _default_contact(customer)
    return str(contact.phone_number) if contact else ""


def _default_contact(customer):
    contacts = list(customer.contactno.all())
    return next((item for item in contacts if item.is_default), None) or (
        contacts[0] if contacts else None
    )


def _sync_contact_methods(customer, party):
    for contact in customer.contactno.all():
        value = str(contact.phone_number)
        contact_type = CONTACT_TYPE_MAP.get(
            contact.contact_type,
            PartyContactMethod.ContactType.PHONE,
        )
        PartyContactMethod.objects.get_or_create(
            party=party,
            contact_type=contact_type,
            normalized_value=contact.phone_number_normalized or _digits_only(value),
            defaults={
                "label": contact.get_contact_type_display(),
                "value": value,
                "is_primary": contact.is_default,
                "is_verified": contact.is_verified,
            },
        )


def _sync_addresses(customer, party):
    for address in customer.address.all():
        PartyAddress.objects.get_or_create(
            party=party,
            address_type=PartyAddress.AddressType.BILLING,
            line1=address.door_number or address.street or address.area or address.city,
            defaults={
                "line2": address.street if address.door_number else "",
                "area": address.area,
                "city": address.city,
                "state": address.state,
                "postal_code": address.zip_code,
                "country": address.country,
                "is_default": address.is_default,
                "is_verified": address.is_verified,
            },
        )


def _sync_identifiers(customer, party):
    for proof in customer.proofs.all():
        identifier_type = PROOF_TYPE_MAP.get(
            proof.proof_type,
            PartyIdentifier.IdentifierType.OTHER,
        )
        PartyIdentifier.objects.get_or_create(
            party=party,
            identifier_type=identifier_type,
            defaults={
                "value": proof.proof_number,
                "masked_value": _mask_identifier(proof.proof_number),
                "value_hash": _hash_identifier(proof.proof_number),
                "is_verified": proof.is_verified,
                "metadata": {"legacy_proof_id": proof.id, "legacy_proof_type": proof.proof_type},
            },
        )


def _digits_only(value):
    return "".join(ch for ch in str(value or "") if ch.isdigit())


def _mask_identifier(value):
    value = str(value or "").strip()
    if len(value) <= 4:
        return value
    return f"{'*' * (len(value) - 4)}{value[-4:]}"


def _hash_identifier(value):
    normalized = str(value or "").strip().upper()
    if not normalized:
        return ""
    return sha256(normalized.encode("utf-8")).hexdigest()
