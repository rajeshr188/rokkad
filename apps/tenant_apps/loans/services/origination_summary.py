"""Presentation of canonical origination amounts, without changing signed reviews."""
from decimal import Decimal
from datetime import date

from .recorded_history import validate_input
from .recorded_items import contract_items, monthly_interest


def native_origination_summary(loan, economics):
    return dict(customer=loan.borrower, series=loan.series, number=loan.loan_number,
        date=loan.loan_date, tenure=loan.tenure_months, economics=economics,
        items=[dict(description=item.description, metal=item.metal, quantity=item.quantity,
            net_weight=item.net_weight, principal=item.allocated_principal,
            rate=item.monthly_interest_rate) for item in loan.collateral_items.order_by("pk")])


def recorded_origination_summary(data, *, customer, series, historical_source=False):
    # Use the writer's validation and item rounding, including old single-item
    # reviews. This context is deliberately outside the v1 signed review object.
    data = validate_input(data, historical_source=historical_source)
    items = contract_items(data)
    monthly = monthly_interest(items, Decimal(data["currency_quantum"]))
    return dict(customer=customer, series=series, number=data["number"], date=date.fromisoformat(data["date"]),
        source_reference=data["source_reference"],
        tenure=data["tenure"], recorded=True, payout_basis=data.get("payout_basis", "CASH"),
        items=items, economics=dict(gross_principal=data["principal"], monthly_interest=monthly,
            advance_interest=monthly * data["advance_months"], deducted_fees=data.get("document_charge", "0"),
            net_disbursed=data["cash_paid"]))
