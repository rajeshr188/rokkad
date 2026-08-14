from dataclasses import dataclass

from apps.tenant_apps.party.models import PartyRoleType


@dataclass(frozen=True)
class CanonicalPartyRole:
    key: str
    label: str
    description: str
    sort_order: int


CANONICAL_PARTY_ROLES = (
    CanonicalPartyRole("CUSTOMER", "Customer", "Party that buys goods or services.", 10),
    CanonicalPartyRole("SUPPLIER", "Supplier", "Party that supplies goods or services.", 20),
    CanonicalPartyRole("BORROWER", "Borrower", "Party that receives a loan.", 30),
    CanonicalPartyRole("LENDER", "Lender", "Party that gives a loan.", 40),
    CanonicalPartyRole("RETAILER", "Retailer", "Party operating as a retail counterparty.", 50),
    CanonicalPartyRole("WHOLESALER", "Wholesaler", "Party operating as a wholesale counterparty.", 60),
    CanonicalPartyRole("MANUFACTURER", "Manufacturer", "Party that manufactures goods.", 70),
    CanonicalPartyRole("EMPLOYEE", "Employee", "Party connected to payroll, advances, or reimbursements.", 80),
    CanonicalPartyRole("AGENT", "Agent", "Party acting on behalf of another party or workspace.", 90),
    CanonicalPartyRole("BROKER", "Broker", "Party facilitating deals or transactions.", 100),
    CanonicalPartyRole("BANK", "Bank", "Bank as a counterparty, separate from DEA bank accounts.", 110),
    CanonicalPartyRole("TRANSPORTER", "Transporter", "Party responsible for transport or logistics.", 120),
    CanonicalPartyRole(
        "INSURANCE_PROVIDER",
        "Insurance Provider",
        "Party providing insurance services.",
        130,
    ),
    CanonicalPartyRole(
        "PORTAL_CUSTOMER",
        "Portal Customer",
        "Party linked to future customer portal access.",
        140,
    ),
)


def seed_party_roles():
    created = 0
    updated = 0

    for role in CANONICAL_PARTY_ROLES:
        _obj, was_created = PartyRoleType.objects.update_or_create(
            key=role.key,
            defaults={
                "label": role.label,
                "description": role.description,
                "is_system": True,
                "is_active": True,
                "sort_order": role.sort_order,
            },
        )
        if was_created:
            created += 1
        else:
            updated += 1

    return {"created": created, "updated": updated, "total": len(CANONICAL_PARTY_ROLES)}
