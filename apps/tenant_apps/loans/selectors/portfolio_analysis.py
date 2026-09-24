"""Read-only grouped reports. Money comes from the canonical balance fold."""

from decimal import Decimal

from django.db.models import OuterRef, Subquery

from apps.tenant_apps.loans.models import (
    CollateralAppraisal, PawnCollateralItem, current_tenant_workspace_id,
)
from .balances import calculate_pawn_loan_balance, PawnLoanBalanceSelectorError
from .reports import _optional_policy, _report_loans


ZERO = Decimal("0")
ANALYSIS_SECTIONS = (
    ("license_totals", "Active loans by licence"),
    ("series_totals", "Active loans by series"),
    ("collateral_totals", "Collateral by metal"),
    ("maturity", "Maturity profile"),
    ("year_totals", "Loans by year"),
)


def _chart(title, rows, column, unit):
    # Keep charts legible; every group remains in the adjacent table and export.
    ordered = sorted(rows, key=lambda row: row["cells"][column], reverse=True)
    labels = [row["cells"][0] for row in ordered[:12]]
    values = [str(row["cells"][column]) for row in ordered[:12]]
    if len(ordered) > 12:
        labels.append("Other groups")
        values.append(str(sum((row["cells"][column] for row in ordered[12:]), ZERO)))
    return {"title": title, "labels": labels, "values": values, "unit": unit}


def get_portfolio_analysis(*, section, as_of_date):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Reports require an active Workspace context.")
    if section not in dict(ANALYSIS_SECTIONS):
        raise ValueError("Unknown analytical report.")
    if section == "collateral_totals":
        return _collateral_analysis(workspace_id, as_of_date)
    if section == "year_totals":
        return build_year_analysis(_report_loans(workspace_id), as_of_date=as_of_date)
    loans = _report_loans(workspace_id).filter(state="ACTIVE")
    return build_active_loan_analysis(loans, section=section, as_of_date=as_of_date)


def build_active_loan_analysis(loans, *, section, as_of_date):
    groups = {}
    maturity_labels = ("Not past maturity", "1-30 days past maturity", "31-90 days past maturity",
                       "91-180 days past maturity", "Over 180 days past maturity", "Balance unavailable")
    for loan in loans:
        if loan.state != "ACTIVE":
            continue
        try:
            balance = calculate_pawn_loan_balance(
                loan, events=tuple(loan.loan_events.all()),
                collateral_items=tuple(loan.collateral_items.all()),
                policy_snapshot=_optional_policy(loan), as_of_date=as_of_date,
            )
        except (PawnLoanBalanceSelectorError, ValueError):
            balance = None
        if section == "maturity":
            days = max(0, (as_of_date - balance.due_date).days) if balance else None
            key = 5 if days is None else 0 if days == 0 else 1 if days <= 30 else 2 if days <= 90 else 3 if days <= 180 else 4
            label, filters = maturity_labels[key], {}
        elif section == "license_totals":
            key = loan.license_id
            label, filters = loan.license.license_number, {"license": key, "state": "ACTIVE"}
        else:
            key = loan.series_id
            label = f"{loan.license.license_number} / {loan.series.code}"
            filters = {"series": key, "state": "ACTIVE"}
        group = groups.setdefault(key, {"cells": [label, 0, ZERO, ZERO, ZERO, 0, 0], "filters": filters})
        cells = group["cells"]
        cells[1] += 1
        if balance is None:
            cells[6] += 1
        else:
            cells[2] += balance.principal_outstanding
            cells[3] += balance.interest_outstanding
            cells[4] += balance.total_due
            cells[5] += int(balance.is_overdue)
    rows = [groups[key] for key in sorted(groups)] if section == "maturity" else sorted(groups.values(), key=lambda row: row["cells"][0])
    totals = ["Total"] + [sum((row["cells"][i] for row in rows), ZERO) for i in range(1, 7)]
    charts = [_chart("Principal outstanding by " + ("maturity" if section == "maturity" else "licence" if section == "license_totals" else "series"), rows, 2, "INR")]
    if section == "maturity":
        charts[0]["labels"] = [row["cells"][0] for row in rows]
        charts[0]["values"] = [str(row["cells"][2]) for row in rows]
    return {
        "title": dict(ANALYSIS_SECTIONS)[section],
        "scope": f"Currently active loans. Recorded balances as of {as_of_date}; amounts exclude unavailable balances. Recorded interest is not a settlement quote. Maturity uses the loan's due date, not contractual instalment DPD.",
        "columns": ("Group", "Active loans", "Principal outstanding (INR)", "Recorded interest (INR)", "Recorded total due (INR)", "Overdue loans", "Unavailable balances"),
        "rows": rows, "totals": totals, "charts": charts,
        "incomplete_count": totals[6],
    }


def build_year_analysis(loans, *, as_of_date):
    groups = {}
    for loan in loans:
        year = loan.loan_date.year
        group = groups.setdefault(year, {"cells": [str(year), 0, 0, 0, 0, 0, ZERO, 0],
            "filters": {"loan_date_from": f"{year:04d}-01-01", "loan_date_to": f"{year:04d}-12-31"}})
        cells = group["cells"]
        cells[1] += 1
        if loan.state == "ACTIVE":
            cells[2] += 1
            try:
                balance = calculate_pawn_loan_balance(loan, events=tuple(loan.loan_events.all()),
                    collateral_items=tuple(loan.collateral_items.all()),
                    policy_snapshot=_optional_policy(loan), as_of_date=as_of_date)
                cells[6] += balance.principal_outstanding
            except (PawnLoanBalanceSelectorError, ValueError):
                cells[7] += 1
        elif loan.state == "CLOSED":
            cells[3] += 1
        elif loan.state == "CANCELLED":
            cells[4] += 1
        else:
            cells[5] += 1
    rows = [groups[year] for year in sorted(groups)]
    totals = ["Total"] + [sum((row["cells"][i] for row in rows), ZERO) for i in range(1, 8)]
    charts = []
    for title, column, unit in (("Loan count by original loan year", 1, "loans"),
                                ("Active principal by original loan year", 6, "INR")):
        labels = [row["cells"][0] for row in rows[-12:]]
        values = [str(row["cells"][column]) for row in rows[-12:]]
        if len(rows) > 12:
            labels.insert(0, "Earlier years")
            values.insert(0, str(sum((row["cells"][column] for row in rows[:-12]), ZERO)))
        charts.append({"title": title, "labels": labels, "values": values, "unit": unit})
    return {"title": "Loans by year",
        "scope": f"Grouped by original loan date (calendar year), not creation/import time. Counts include all current operational loan states; historical archive-only records are separate. Active principal uses recorded balances as of {as_of_date}. Unavailable active balances are excluded from money totals. This is not a historical year-end snapshot.",
        "columns": ("Loan year", "Loans", "Active", "Closed", "Cancelled", "Draft / approved", "Active principal (INR)", "Unavailable active balances"),
        "rows": rows, "totals": totals, "charts": charts, "incomplete_count": totals[7]}


def _collateral_analysis(workspace_id, as_of_date):
    appraisal = CollateralAppraisal.objects.filter(
        workspace_id=workspace_id, collateral_item_id=OuterRef("pk"),
        status="APPROVED", effective_at__date__lte=as_of_date,
    ).order_by("-effective_at", "-version", "-pk")
    items = PawnCollateralItem.objects.filter(
        workspace_id=workspace_id, loan__workspace_id=workspace_id, loan__state="ACTIVE",
        custody_state__in=("IN_VAULT", "WITH_FUNDING_LENDER"),
    ).annotate(report_appraisal=Subquery(appraisal.values("appraised_value")[:1])).order_by("metal", "custody_state", "pk")
    return build_collateral_analysis(items, as_of_date=as_of_date)


def build_collateral_analysis(items, *, as_of_date):
    groups = {}
    for item in items:
        key = (item.metal, item.custody_state)
        cells = groups.setdefault(key, {"cells": [f"{item.get_metal_display()} / {item.get_custody_state_display()}", 0, ZERO, ZERO, ZERO, 0, 0], "filters": {}})["cells"]
        cells[1] += 1
        if item.gross_weight is None:
            cells[5] += 1
        else:
            cells[2] += item.gross_weight
        cells[3] += item.net_weight
        if item.report_appraisal is None:
            cells[6] += 1
        else:
            cells[4] += item.report_appraisal
    rows = [groups[key] for key in sorted(groups)]
    totals = ["Total"] + [sum((row["cells"][i] for row in rows), ZERO) for i in range(1, 7)]
    return {
        "title": "Collateral by metal and custody",
        "scope": f"Current holdings on active loans: in vault or with funding lender. Weights are grams. Values use the latest approved appraisal dated on or before {as_of_date}; these are recorded appraisal references, not current market values or eligible lending coverage. Missing gross weights and appraisals are excluded from their sums, never treated as known zero. This is not a historical stock snapshot.",
        "columns": ("Metal / custody", "Items", "Known gross weight (g)", "Net weight (g)", "Known approved appraisal (INR)", "Missing gross weights", "Missing appraisals"),
        "rows": rows, "totals": totals,
        "charts": [_chart("Net weight by metal and custody", rows, 3, "g"), _chart("Recorded approved appraisal by metal and custody", rows, 4, "INR")],
        "incomplete_count": totals[5] + totals[6],
    }
