from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.services.account_resolution import (
    resolve_customer_account,
    resolve_party_account,
)


def resolve_given_loan_borrower_account(source_loan):
    borrower_party = getattr(source_loan, "borrower_party", None)
    if borrower_party:
        return resolve_party_account(
            borrower_party,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
        ).account

    borrower = getattr(source_loan, "borrower", None) or getattr(
        source_loan, "customer", None
    )
    if not borrower:
        raise ValidationError("Loan has no borrower/customer")

    return resolve_customer_account(
        borrower,
        role_key="BORROWER",
        purpose="BORROWER_LOAN_RECEIVABLE",
    )


def resolve_taken_loan_lender_account(source_loan):
    lender_party = getattr(source_loan, "lender_party", None)
    if lender_party:
        return resolve_party_account(
            lender_party,
            role_key="LENDER",
            purpose="LENDER_LOAN_PAYABLE",
        ).account

    lender = getattr(source_loan, "lender", None)
    if not lender:
        raise ValidationError("Loan has no lender")

    return resolve_customer_account(
        lender,
        role_key="LENDER",
        purpose="LENDER_LOAN_PAYABLE",
    )


def resolve_sales_customer_account(source_doc):
    party = getattr(source_doc, "party", None)
    if party:
        return resolve_party_account(
            party,
            role_key="CUSTOMER",
            purpose="CUSTOMER_RECEIVABLE",
        ).account

    customer = getattr(source_doc, "customer", None)
    if not customer:
        raise ValidationError("Sales document has no customer")

    return resolve_customer_account(
        customer,
        role_key="CUSTOMER",
        purpose="CUSTOMER_RECEIVABLE",
    )


def resolve_purchase_supplier_account(source_doc):
    party = getattr(source_doc, "party", None)
    if party:
        return resolve_party_account(
            party,
            role_key="SUPPLIER",
            purpose="SUPPLIER_PAYABLE",
        ).account

    supplier = getattr(source_doc, "vendor", None) or getattr(source_doc, "supplier", None)
    if not supplier:
        raise ValidationError("Purchase document has no supplier/vendor")

    return resolve_customer_account(
        supplier,
        role_key="SUPPLIER",
        purpose="SUPPLIER_PAYABLE",
    )


def resolve_customer_advance_account(source_doc):
    party = getattr(source_doc, "party", None)
    if party:
        return resolve_party_account(
            party,
            role_key="CUSTOMER",
            purpose="CUSTOMER_ADVANCE",
        ).account

    customer = getattr(source_doc, "customer", None)
    if not customer:
        raise ValidationError("Sales/customer advance document has no customer")

    return resolve_customer_account(
        customer,
        role_key="CUSTOMER",
        purpose="CUSTOMER_ADVANCE",
    )


def resolve_supplier_advance_account(source_doc):
    party = getattr(source_doc, "party", None)
    if party:
        return resolve_party_account(
            party,
            role_key="SUPPLIER",
            purpose="SUPPLIER_ADVANCE",
        ).account

    supplier = getattr(source_doc, "vendor", None) or getattr(source_doc, "supplier", None)
    if not supplier:
        raise ValidationError("Purchase/supplier advance document has no supplier/vendor")

    return resolve_customer_account(
        supplier,
        role_key="SUPPLIER",
        purpose="SUPPLIER_ADVANCE",
    )
