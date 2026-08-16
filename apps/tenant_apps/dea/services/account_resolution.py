from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.dea.models import (
    Account,
    AccountType_Ext,
    EntityType,
    Ledger,
    PartyAccountMapping,
    PartyAccountMappingStatus,
    PartyAccountPurpose,
)


CUSTOMER_PURPOSES = {
    PartyAccountPurpose.CUSTOMER_RECEIVABLE,
    PartyAccountPurpose.BORROWER_LOAN_RECEIVABLE,
    PartyAccountPurpose.SUPPLIER_ADVANCE,
}

CREDITOR_PURPOSES = {
    PartyAccountPurpose.SUPPLIER_PAYABLE,
    PartyAccountPurpose.LENDER_LOAN_PAYABLE,
    PartyAccountPurpose.CUSTOMER_ADVANCE,
}

PURPOSE_DEFAULTS = {
    PartyAccountPurpose.CUSTOMER_RECEIVABLE: {
        "role_key": "CUSTOMER",
        "account_type": "Debtor",
        "control_ledger": "Accounts Receivable",
    },
    PartyAccountPurpose.SUPPLIER_PAYABLE: {
        "role_key": "SUPPLIER",
        "account_type": "Creditor",
        "control_ledger": "ACCOUNTS_PAYABLE",
    },
    PartyAccountPurpose.BORROWER_LOAN_RECEIVABLE: {
        "role_key": "BORROWER",
        "account_type": "Debtor",
        "control_ledger": "BORROWER_LOAN_CTRL",
    },
    PartyAccountPurpose.LENDER_LOAN_PAYABLE: {
        "role_key": "LENDER",
        "account_type": "Creditor",
        "control_ledger": "LENDER_ACCOUNT_CTRL",
    },
    PartyAccountPurpose.CUSTOMER_ADVANCE: {
        "role_key": "CUSTOMER",
        "account_type": "Creditor",
        "control_ledger": "Unearned Revenue",
    },
    PartyAccountPurpose.SUPPLIER_ADVANCE: {
        "role_key": "SUPPLIER",
        "account_type": "Debtor",
        "control_ledger": "Current Assets",
    },
}


@dataclass(frozen=True)
class ResolvedPartyAccount:
    account: Account
    mapping: PartyAccountMapping | None
    created: bool = False


def default_customer_purpose(customer):
    if getattr(customer, "customer_type", None) == "S":
        return PartyAccountPurpose.SUPPLIER_PAYABLE
    return PartyAccountPurpose.CUSTOMER_RECEIVABLE


def default_role_for_customer(customer):
    if getattr(customer, "customer_type", None) == "S":
        return "SUPPLIER"
    return "CUSTOMER"


def resolve_customer_account(
    customer,
    role_key=None,
    purpose=None,
    event_type=None,
    create=True,
):
    """Resolve a customer account through Party when available.

    This keeps legacy callers compatible while routing bridged customers through
    the new party role/purpose mapping table.
    """
    purpose = _normalize_purpose(purpose or default_customer_purpose(customer))
    role_key = _normalize_key(role_key or default_role_for_customer(customer))

    if getattr(customer, "party_id", None):
        resolved = resolve_party_account(
            customer.party,
            role_key=role_key,
            purpose=purpose,
            event_type=event_type,
            create=create,
        )
        return resolved.account if isinstance(resolved, ResolvedPartyAccount) else resolved

    return ensure_customer_account(customer)


def resolve_party_account(
    party,
    role_key,
    purpose,
    event_type=None,
    create=True,
):
    """Resolve or create a party-role-purpose subledger account mapping."""
    purpose = _normalize_purpose(purpose)
    role_key = _normalize_key(role_key or PURPOSE_DEFAULTS[purpose]["role_key"])
    event_type = _normalize_key(event_type or "")

    mapping = _find_mapping(party, role_key, purpose, event_type)
    if mapping:
        return ResolvedPartyAccount(account=mapping.account, mapping=mapping, created=False)

    if not create:
        return None

    with transaction.atomic():
        mapping = _find_mapping(party, role_key, purpose, event_type)
        if mapping:
            return ResolvedPartyAccount(
                account=mapping.account,
                mapping=mapping,
                created=False,
            )

        account = _create_account_for_party(party, purpose)
        mapping = PartyAccountMapping.objects.create(
            party=party,
            role_key=role_key,
            purpose=purpose,
            event_type=event_type,
            account=account,
            control_ledger=_control_ledger_for_purpose(purpose),
        )
        return ResolvedPartyAccount(account=account, mapping=mapping, created=True)


def ensure_customer_account(customer):
    """Ensure the legacy default customer account exists."""
    purpose = default_customer_purpose(customer)

    if getattr(customer, "party_id", None):
        return resolve_customer_account(
            customer,
            role_key=default_role_for_customer(customer),
            purpose=purpose,
            create=True,
        )

    raise ValidationError("Customer must be mapped to Party before account resolution.")


def _find_mapping(party, role_key, purpose, event_type):
    query = PartyAccountMapping.objects.select_related(
        "account",
        "account__party",
        "control_ledger",
    ).filter(
        party=party,
        role_key=role_key,
        purpose=purpose,
        status=PartyAccountMappingStatus.ACTIVE,
    )
    if event_type:
        return query.filter(event_type=event_type).first() or query.filter(
            event_type=""
        ).first()
    return query.filter(event_type="").first()


def _create_account_for_party(party, purpose):
    return Account.objects.create(
        party=party,
        entity=_entity_type_for_party(party),
        AccountType_Ext=_account_type_for_purpose(purpose),
    )


def _entity_type_for_party(party):
    if party.party_type in {"ORGANIZATION", "BANK", "GOVERNMENT"}:
        return EntityType.objects.get(name="Organisation")
    return EntityType.objects.get(name="Person")


def _account_type_for_purpose(purpose):
    defaults = PURPOSE_DEFAULTS[_normalize_purpose(purpose)]
    return AccountType_Ext.objects.get(description=defaults["account_type"])


def _control_ledger_for_purpose(purpose):
    ledger_name = PURPOSE_DEFAULTS[_normalize_purpose(purpose)]["control_ledger"]
    return Ledger.objects.filter(name=ledger_name).first()


def _normalize_purpose(purpose):
    purpose = str(purpose or "").strip().upper()
    if purpose not in PartyAccountPurpose.values:
        raise ValidationError(f"Unsupported party account purpose: {purpose}")
    return purpose


def _normalize_key(value):
    return str(value or "").strip().upper()
