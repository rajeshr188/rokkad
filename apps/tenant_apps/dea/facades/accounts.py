def ensure_customer_account(customer):
    """Ensure a DEA Account exists for a Contact Customer."""
    from apps.tenant_apps.dea.models import Account, AccountType_Ext, EntityType

    entity_t = EntityType.objects.get(name="Person")
    if customer.customer_type in ("W", "R"):
        acct_type = AccountType_Ext.objects.get(description="Debtor")
    else:
        acct_type = AccountType_Ext.objects.get(description="Creditor")

    account, _created = Account.objects.update_or_create(
        contact=customer,
        entity=entity_t,
        defaults={"AccountType_Ext": acct_type},
    )
    customer.account = account
    return account
