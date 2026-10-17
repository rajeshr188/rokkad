"""Concrete admission limits; these checks never authorize or post a loan."""

from decimal import Decimal


def supports_paper_monthly_terms(
    *, interest_method, partial_month_method, advance_interest_periods, currency_quantum
):
    """The published recorded-anniversary/3 contract, without substituting rules."""
    return (
        interest_method == "SIMPLE"
        and partial_month_method == "FULL_MONTH"
        and advance_interest_periods in (0, 1)
        and Decimal(currency_quantum) in (Decimal("0.01"), Decimal("1"))
    )


def capability_notes(values):
    """Explain concrete known limits; history/dependency checks still run later."""
    if not values.get("interest_method") or not values.get("partial_month_method"):
        return [
            "Calculation capability is not established by this evidence. Review the saved agreement before servicing or correction."
        ]
    notes = []
    if not supports_paper_monthly_terms(
        **{
            key: values.get(key, "0")
            for key in (
                "interest_method",
                "partial_month_method",
                "advance_interest_periods",
                "currency_quantum",
            )
        }
    ):
        notes.append(
            "Paper admission supports simple full monthly interest with zero or one upfront month and paise or rupee rounding. These rules cannot be substituted for a different actual agreement."
        )
    if (
        values["interest_method"] != "SIMPLE"
        or values["partial_month_method"] != "FULL_MONTH"
        or Decimal(values.get("currency_quantum", "0"))
        not in (Decimal(".01"), Decimal("1"))
    ):
        notes.append(
            "Financial agreement correction currently requires a supported simple full-month contract. This saved rule remains valid for ordinary direct origination; later financial correction needs a supported reconciliation. Borrower and collateral fact corrections have their own dependency checks."
        )
    return notes
