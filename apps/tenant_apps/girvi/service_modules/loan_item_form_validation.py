"""Validation helpers for loan item forms."""

from decimal import Decimal

from django import forms


class LoanItemFormValidationService:
    """Keep loan item forms focused on binding while centralizing business checks."""

    @staticmethod
    def validate_collateral_value(*, itemtype, loanamount, weight, purity, rate):
        if None in (loanamount, itemtype, weight, purity):
            return

        if rate is None:
            raise forms.ValidationError(
                f"{itemtype} rate is not configured. Add the current metal rate "
                "from Rates before creating this loan item."
            )

        value = round(weight * purity * Decimal("0.01") * rate)
        if value < loanamount:
            raise forms.ValidationError(
                f"Loan amount {loanamount} cannot exceed items value {value}."
            )

    @staticmethod
    def validate_initial_row(form, cleaned_data, *, row_has_user_input):
        if not row_has_user_input:
            return cleaned_data

        required_messages = {
            "itemdesc": "Description is required when adding an item.",
            "weight": "Weight is required when adding an item.",
            "loanamount": "Loan amount is required when adding an item.",
            "interestrate": "Interest rate is required when adding an item.",
        }
        for field_name, message in required_messages.items():
            if cleaned_data.get(field_name) in (None, ""):
                form.add_error(field_name, message)

        if cleaned_data.get("quantity") in (None, ""):
            cleaned_data["quantity"] = 1
        if cleaned_data.get("purity") in (None, ""):
            cleaned_data["purity"] = 75
        if not cleaned_data.get("itemtype"):
            cleaned_data["itemtype"] = "Gold"

        return cleaned_data
