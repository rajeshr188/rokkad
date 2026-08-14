"""Contact app signal hooks.

Customer persistence intentionally has no DEA/accounting side effects.
Accounting workflows that need a party account should call
apps.tenant_apps.dea.facade.ensure_customer_account(customer) explicitly at the
accounting boundary.
"""
