"""Presentation of canonical origination amounts, without changing signed reviews."""

from decimal import Decimal
from datetime import date

from .recorded_history import validate_input
from .recorded_items import contract_items, monthly_interest
from apps.tenant_apps.loans.domain.origination_capabilities import capability_notes

CALCULATION_FIELDS = (
    "interest_method",
    "partial_month_method",
    "partial_month_cutoff_days",
    "partial_month_lower_fraction",
    "advance_interest_periods",
    "currency_quantum",
    "rounding_method",
    "minimum_first_month",
    "capitalization_interval_periods",
)


def policy_source(policy):
    """Explain the actual resolver result; never treat a default as a loan term."""
    scope = (
        f"Series {policy.series.pawn_display_name}"
        if getattr(policy, "series_id", None)
        else (
            f"Licence {policy.license.license_number}"
            if policy.license_id
            else "Workspace default"
        )
    )
    end = (
        f" through {policy.effective_until:%d/%m/%Y}" if policy.effective_until else ""
    )
    return f"{scope}; from {policy.effective_from:%d/%m/%Y}{end}; revision {getattr(policy, 'revision', 1)}"


def calculation_terms(values, *, recorded=False, original_date=None):
    """Presentation of known captured rules only; no financial calculation."""
    partial = values.get("partial_month_method")
    partial_label = {
        "FULL_MONTH": "A full month's interest for a started month",
        "STARTED_WEEKS": "Interest for started 7-day blocks within each loan month",
        "ACTUAL_DAYS": "Actual days within each loan month",
        "SLAB": f"Part-month slab: cutoff {values.get('partial_month_cutoff_days', 'unknown')} days; lower fraction {values.get('partial_month_lower_fraction', 'unknown')}",
    }.get(partial, partial or "Not established by this evidence")
    advance = values.get("advance_interest_periods")
    quantum = values.get("currency_quantum")
    quantum_label = (
        {Decimal("0.01"): "Paise (0.01 INR)", Decimal("1"): "Whole rupees (1 INR)"}.get(
            Decimal(quantum), str(quantum)
        )
        if quantum is not None
        else "Not established by this evidence"
    )
    result = [
        (
            "Interest calculation",
            {"SIMPLE": "Simple interest", "COMPOUND": "Compound interest"}.get(
                values.get("interest_method"), "Not established by this evidence"
            ),
        ),
        ("Part-month charging", partial_label),
        (
            "Interest deducted upfront",
            (
                f"{advance} month(s)"
                if advance is not None
                else "Not established by this evidence"
            ),
        ),
        (
            "Interest rounding unit",
            quantum_label,
        ),
        (
            "Rounding rule",
            (
                "Round each item's interest for each loan month"
                if recorded or values.get("policy_version") == 2
                else values.get("rounding_method", "Not established by this evidence")
                .replace("_", " ")
                .title()
            ),
        ),
        (
            "First-month charging",
            (
                "Full first month under the monthly charging rule"
                if partial == "FULL_MONTH" or recorded
                else (
                    "A full first month"
                    if values.get("minimum_first_month") is True
                    else (
                        "Follow the part-month rule"
                        if values.get("minimum_first_month") is False
                        else "Not established by this evidence"
                    )
                )
            ),
        ),
    ]
    if recorded or values.get("policy_version") == 2:
        result.append(
            (
                "Monthly boundary",
                "Original loan anniversary; the following month begins on the next day",
            )
        )
        if type(advance) is int and 0 < advance <= 1200 and original_date is not None:
            from apps.tenant_apps.loans.domain.monthly_contract import anniversary

            result.append(
                (
                    "Upfront interest covers through",
                    anniversary(original_date, advance).strftime("%d/%m/%Y"),
                )
            )
    if values.get("interest_method") == "COMPOUND":
        result.append(
            (
                "Capitalization interval",
                f"{values.get('capitalization_interval_periods', 'Unknown')} month(s)",
            )
        )
    notes = capability_notes(values)
    if notes:
        result.append(("Capability limits", " ".join(notes)))
    result.append(
        (
            "Monitoring",
            "Current monitoring uses its separate policy; these are agreement terms",
        )
    )
    return result


def _native_rules(loan, *, historical_context=None):
    from .economic_policies import (
        resolve_pawn_loan_economic_policy,
        resolve_pawn_metal_interest_rate_policy,
        resolve_pawn_loan_fee_policies,
    )
    from .economic_policies import PawnEconomicPolicyError

    sources = []
    if loan.state != "DRAFT":
        approval = loan.approval_snapshots.order_by("-version").first()
        values = (
            dict(approval.payload.get("collateral_economics", {})) if approval else {}
        )
        if values:
            sources.append(
                (
                    "Agreement",
                    f"Saved approval version {approval.version}; current setup is not substituted",
                )
            )
        return calculation_terms(values, original_date=loan.loan_date), sources
    try:
        items = tuple(loan.collateral_items.order_by("pk"))
        if historical_context is not None:
            from .historical_origination import historical_policies

            policy, rates, fees = historical_policies(
                historical_context,
                items,
                license_id=loan.license_id,
                series_id=loan.series_id,
            )
            sources.append(
                (
                    "Historical basis",
                    "Retained approval or existing evidence recorded by the actual payout date; current setup is not substituted",
                )
            )
        else:
            policy = resolve_pawn_loan_economic_policy(
                workspace_id=loan.workspace_id,
                license_id=loan.license_id,
                series_id=loan.series_id,
                as_of_date=loan.loan_date,
            )
            rates = tuple(
                resolve_pawn_metal_interest_rate_policy(
                    workspace_id=loan.workspace_id,
                    license_id=loan.license_id,
                    series_id=loan.series_id,
                    as_of_date=loan.loan_date,
                    metal=item.metal,
                )
                for item in items
            )
            fees = resolve_pawn_loan_fee_policies(
                workspace_id=loan.workspace_id,
                license_id=loan.license_id,
                as_of_date=loan.loan_date,
            )
        values = {name: getattr(policy, name) for name in CALCULATION_FIELDS}
        values["policy_version"] = 2
        sources.append(("Calculation policy", policy_source(policy)))
        for item, rate in zip(items, rates, strict=True):
            source = (
                f"Explicit item override: {item.interest_override_reason}"
                if item.interest_rate_override is not None
                else f"{rate.monthly_interest_rate}% monthly; {policy_source(rate)}"
            )
            sources.append((item.description, source))
        for fee in fees:
            sources.append((f"Fee: {fee.name}", policy_source(fee)))
    except PawnEconomicPolicyError as exc:
        return [], [("Setup needs attention", str(exc))]
    return calculation_terms(values, original_date=loan.loan_date), sources


def native_origination_summary(loan, economics, *, historical_context=None):
    rules, sources = _native_rules(loan, historical_context=historical_context)
    return dict(
        customer=loan.borrower,
        series=loan.series,
        number=loan.display_reference,
        product=loan.product_version,
        calculation_terms=rules,
        term_sources=sources,
        date=loan.loan_date,
        tenure=loan.tenure_months,
        economics=economics,
        items=[
            dict(
                description=item.description,
                metal=item.metal,
                quantity=item.quantity,
                net_weight=item.net_weight,
                principal=item.allocated_principal,
                rate=item.monthly_interest_rate,
            )
            for item in loan.collateral_items.order_by("pk")
        ],
    )


def replacement_origination_summary(preview, values):
    """Show already-resolved destination terms; no independent amount calculation."""
    resolved = preview["resolved"]
    policy = {
        name: getattr(resolved.economic_policy, name) for name in CALCULATION_FIELDS
    }
    sources = [("Calculation policy", policy_source(resolved.economic_policy))]
    for item, rate in zip(preview["items"], resolved.rate_policies, strict=True):
        sources.append(
            (
                item.description,
                (
                    f"Item override: {item.interest_override_reason}"
                    if item.interest_rate_override is not None
                    else f"{rate.monthly_interest_rate}% monthly; {policy_source(rate)}"
                ),
            )
        )
    sources.extend(
        (f"Fee: {fee.name}", policy_source(fee)) for fee in resolved.fee_policies
    )
    return dict(
        customer=preview["source"].borrower,
        series=preview["series"],
        number=preview["number"],
        product=preview["product"],
        date=values["loan_date"],
        tenure=values["tenure_months"],
        calculation_terms=calculation_terms(
            policy | {"policy_version": 2}, original_date=values["loan_date"]
        ),
        term_sources=sources,
        economics=resolved.economics,
        items=[
            dict(
                description=item.description,
                metal=item.metal,
                quantity=item.quantity,
                net_weight=item.net_weight,
                principal=tranche.allocated_principal,
                rate=tranche.monthly_interest_rate,
            )
            for item, tranche in zip(
                preview["items"], resolved.economics.tranches, strict=True
            )
        ],
    )


def recorded_origination_summary(data, *, customer, series, historical_source=False):
    # Use the writer's validation and item rounding, including old single-item
    # reviews. This context is deliberately outside the v1 signed review object.
    data = validate_input(data, historical_source=historical_source)
    items = contract_items(data)
    monthly = monthly_interest(items, Decimal(data["currency_quantum"]))
    return dict(
        customer=customer,
        series=series,
        number=data["number"],
        date=date.fromisoformat(data["date"]),
        calculation_terms=calculation_terms(
            dict(
                interest_method="SIMPLE",
                partial_month_method="FULL_MONTH",
                advance_interest_periods=data["advance_months"],
                currency_quantum=data["currency_quantum"],
                rounding_method="PER_ITEM_PER_PERIOD",
            ),
            recorded=True,
            original_date=date.fromisoformat(data["date"]),
        ),
        term_sources=[
            ("Agreement", f"Recorded original terms; {data['source_reference']}")
        ],
        source_reference=data["source_reference"],
        tenure=data["tenure"],
        recorded=True,
        payout_basis=data.get("payout_basis", "CASH"),
        items=items,
        economics=dict(
            gross_principal=data["principal"],
            monthly_interest=monthly,
            advance_interest=monthly * data["advance_months"],
            deducted_fees=data.get("document_charge", "0"),
            net_disbursed=data["cash_paid"],
        ),
    )


def review_summary(agreement):
    """Small signed presentation snapshot; not another financial authority."""
    economics = agreement.get("economics")
    if isinstance(economics, dict):
        net = economics.get("net_disbursed")
    else:
        net = getattr(economics, "net_disbursed", None)
    return {
        "Customer": f"{agreement['customer'].party_code}: {agreement['customer'].display_name}",
        "Series / number": f"{agreement['series']} / {agreement['number']}",
        "Loan date": str(agreement["date"]),
        "Tenure (months)": str(agreement["tenure"]),
        "Net proceeds": str(net) if net is not None else "Needs a fresh valid quote",
        "Collateral and agreed rates": "; ".join(
            f"{r['description']}: {r['net_weight']}g, principal {r['principal']}, {r['rate']}% monthly"
            for r in agreement["items"]
        ),
        **{
            label: str(value) for label, value in agreement.get("calculation_terms", ())
        },
        "Sources": "; ".join(
            f"{label}: {value}" for label, value in agreement.get("term_sources", ())
        ),
    }
