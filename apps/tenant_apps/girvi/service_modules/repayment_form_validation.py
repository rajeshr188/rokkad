"""Validation helpers for repayment forms."""

from apps.tenant_apps.girvi.selectors import build_loan_settlement_balance


class RepaymentFormValidationService:
    """Keep repayment forms focused on input binding while centralizing rule checks."""

    @staticmethod
    def validate_form(form, *, loan_kind="given"):
        cleaned_data = form.cleaned_data
        total = cleaned_data.get("total_amount")
        interest = cleaned_data.get("interest_amount")

        if total is not None and interest is not None and interest > total:
            form.add_error(
                "interest_amount", "Interest portion cannot exceed total amount."
            )

        loan = getattr(form, "loan", None)
        if not loan or total is None:
            return

        settlement = build_loan_settlement_balance(loan, loan_kind=loan_kind)

        if total > settlement.total_outstanding:
            form.add_error(
                "total_amount",
                f"Payment amount cannot exceed outstanding amount {settlement.total_outstanding}.",
            )

        if interest is not None and interest > settlement.interest_due:
            form.add_error(
                "interest_amount",
                f"Interest portion cannot exceed outstanding interest {settlement.interest_due}.",
            )
