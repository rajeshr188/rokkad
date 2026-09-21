"""Source-code comparison worksheet, never a current Loans calculation policy."""
from collections import defaultdict
from datetime import date, datetime, time, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN, ROUND_HALF_UP
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dateutil.relativedelta import relativedelta

from .legacy_preview import encode, number, timestamp
from .parsers import PortabilityError

COMMIT = "c9fb81bc70adafa1d942721d642bfb2b38953f41"
PROFILE = "legacy-reconciliation-worksheet/1"


def compare_expressions(original, evaluated_at, monthly_money):
    """Independent Decimal transcription of inspected expressions, no legacy execution."""
    if original is None or evaluated_at is None or monthly_money is None or monthly_money < 0:
        return None
    try:
        if original.utcoffset() is None or evaluated_at.utcoffset() is None:
            return None
        original, evaluated_at = original.astimezone(timezone.utc), evaluated_at.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None
    if evaluated_at < original:
        return None
    delta = relativedelta(evaluated_at, original)
    months = delta.years * 12 + delta.months
    days = (evaluated_at - original).days
    report_months = int((Decimal(days) / Decimal("30.44")).to_integral_value(rounding=ROUND_CEILING))
    model = (monthly_money * months).quantize(Decimal("1"), rounding=ROUND_HALF_EVEN)
    report = (monthly_money * (report_months - 1)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return {"completed_calendar_months": months, "elapsed_whole_days": days,
            "report_months": report_months, "model_gross_interest": str(model),
            "report_gross_interest": str(report), "gross_interest_difference": str(model - report)}


def build_worksheet(summary, records, *, as_of, business_timezone, owner_profile=None):
    """Deterministic representative sample plus one explicitly separate released control."""
    from .legacy_owner_rules import check_profile, interest_diagnostic
    check_profile(summary, owner_profile)
    try:
        day = date.fromisoformat(as_of)
        zone = ZoneInfo(business_timezone)
        if day.isoformat() != as_of or day > datetime.now(zone).date():
            raise ValueError()
    except (ValueError, TypeError, ZoneInfoNotFoundError) as exc:
        raise PortabilityError("Supply a nonfuture ISO comparison date and an explicit IANA timezone.") from exc
    if summary.get("profile") != "legacy-dump-preview/1" or not summary.get("exclusion_proposal"):
        raise PortabilityError("Reconciliation requires the explicit source selection proposal.")
    if any(r["source"]["schema"] != summary["source_schema"] or
           r["source"]["source_system"] != summary["source_system"] for r in records):
        raise PortabilityError("Reconciliation must remain within the selected source tenant.")
    at = datetime.combine(day, time.max, zone).astimezone(timezone.utc)
    linked = defaultdict(list)
    for record in records:
        if record["source"]["table"] in {"girvi_loanitem", "girvi_loanpayment", "girvi_release"}:
            linked[record["source"]["table"], record["facts"]["loan_id"]].append(record)
    for children in linked.values():
        children.sort(key=lambda r: int(r["source"]["id"]))

    def candidate(record):
        pk, facts = record["source"]["id"], record["facts"]
        items, payments, releases = [linked[t, pk] for t in ("girvi_loanitem", "girvi_loanpayment", "girvi_release")]
        # Released examples are a control at their release time, never an opening candidate.
        end = at
        if releases:
            release_date = timestamp(releases[0]["facts"]["release_date"])
            end = min(at, release_date) if release_date else None
        original = timestamp(facts["loan_date"])
        comparison = compare_expressions(original, end, number(facts["interest"])) if end else None
        try:
            original_business_date = original.astimezone(zone).date().isoformat() if original else None
        except (ValueError, OverflowError):
            original_business_date = None

        def total(rows, field, *, require_rows=False):
            values = [number(r["facts"][field]) for r in rows]
            return str(sum(values, Decimal("0"))) if all(v is not None for v in values) and (rows or not require_rows) else None

        diagnostic = {"stored_loan_principal": facts["loan_amount"], "stored_monthly_interest": facts["interest"],
                      "item_principal_sum": total(items, "loanamount", require_rows=True),
                      "item_monthly_interest_sum": total(items, "interest", require_rows=True),
                      "payment_row_count": len(payments), "stored_payment_sum": total(payments, "payment_amount"),
                      "stored_principal_payment_sum": total(payments, "principal_payment"),
                      "stored_interest_payment_sum": total(payments, "interest_payment"),
                      "payments_after_comparison": sum(timestamp(p["facts"]["payment_date"]) is not None and end is not None and timestamp(p["facts"]["payment_date"]) > end for p in payments)}
        return {"source_loan_id": record["source"]["external_id"], "source_state": record["source_state"],
                "selection": record["exclusion_proposal"]["disposition"], "reasons": [],
                "evaluated_at": end.isoformat() if end else None,
                "source_original_business_date": original_business_date,
                "diagnostic": diagnostic, "comparison": comparison,
                "source_loan": record, "source_items": items, "source_payments": payments, "source_releases": releases,
                "import_ready": False, "reviewed_opening": {"principal": None, "interest": None, "fees": None,
                    "evidence_reference": None, "agreed_rule": None}}

    loans = [r for r in records if r["source"]["table"] == "girvi_loan"]
    retained = [candidate(r) for r in loans if r["source_state"] == "UNRELEASED" and
                r["exclusion_proposal"]["disposition"] == "RETAIN_FOR_REVIEW"]
    retained.sort(key=lambda r: int(r["source_loan"]["source"]["id"]))
    selected = {}

    def pick(reason, values, key=None, reverse=False, median=False):
        if not values:
            return
        ordered = sorted(values, key=key, reverse=reverse) if key else values
        chosen = ordered[len(ordered) // 2] if median else ordered[0]
        selected.setdefault(chosen["source_loan_id"], chosen)["reasons"].append(reason)

    amount_key = lambda r: number(r["diagnostic"]["stored_loan_principal"]) or Decimal("0")
    pick("Source total mismatch", [r for r in retained if any(i["severity"] == "ERROR" for i in r["source_loan"]["issues"])])
    pick("Largest interest-path difference", [r for r in retained if r["comparison"]],
         lambda r: abs(Decimal(r["comparison"]["gross_interest_difference"])), True)
    for metal in ("Gold", "Silver", "Bronze"):
        pick(f"{metal} example near median principal", [r for r in retained if {i["facts"]["itemtype"] for i in r["source_items"]} == {metal}], amount_key, median=True)
    pick("Multiple collateral items", [r for r in retained if len(r["source_items"]) > 1])
    pick("Different item interest rates", [r for r in retained if len({i["facts"]["interestrate"] for i in r["source_items"]}) > 1])
    pick("Billing date on day 29-31", [r for r in retained if r["source_original_business_date"] and int(r["source_original_business_date"][-2:]) >= 29])
    dated = [r for r in retained if r["source_original_business_date"]]
    pick("Oldest retained loan", dated, lambda r: r["source_original_business_date"])
    pick("Newest retained loan", dated, lambda r: r["source_original_business_date"], True)
    pick("Largest retained principal", retained, amount_key, True)
    pick("Retained loan with stored payments", [r for r in retained if r["source_payments"]])
    controls = [r for r in loans if r["source_state"] == "RELEASED" and
                r["exclusion_proposal"]["disposition"] == "RETAIN_FOR_REVIEW" and linked["girvi_loanpayment", r["source"]["id"]] and
                not any(i["severity"] == "ERROR" for i in r["issues"])]
    controls.sort(key=lambda r: int(r["source"]["id"]))
    pick("Released payment control; outside active migration", [candidate(controls[0])] if controls else [])
    rows = list(selected.values())
    return {"profile": PROFILE, "import_ready": False, "source_schema": summary["source_schema"],
            "source_namespace": summary["source_namespace"], "archive_sha256": summary["archive_sha256"],
            "selection_sha256": summary["exclusion_proposal"]["selection_sha256"], "source_commit": COMMIT,
            "comparison_date": day.isoformat(), "comparison_timezone": business_timezone, "cutover_approved": False,
            "retained_active_loans": len(retained), "retained_active_with_payment_rows": sum(bool(r["source_payments"]) for r in retained),
            "retained_active_with_differing_gross_interest": sum(r["comparison"] is not None and Decimal(r["comparison"]["gross_interest_difference"]) != 0 for r in retained),
            "sample_count": len(rows), "samples": rows,
            "owner_profile": owner_profile,
            "owner_rule_diagnostics": [interest_diagnostic(r, as_of=day, owner_profile=owner_profile) for r in retained] if owner_profile else [],
            "method": {"model": "loan.py:201-212: completed relativedelta months, monthly money, Python Decimal half-even round",
                       "report": "managers.py:100-135: ceil(whole elapsed days / 30.44) - 1, numeric half-away-from-zero round",
                       "model_due": "loan.py:154-164,233-238: item principal + model gross interest - all stored payment amounts",
                       "report_due": "managers.py:135: stored loan principal + report gross interest; payments not deducted",
                       "payment": "loan.py:919-923: split determined by interestdue at entry time, not payment_date"},
            "limitations": ["Comparison date/timezone are rehearsal assumptions, not an approved cutover.",
                            "Arithmetic transcribes inspected code without executing legacy Python or PostgreSQL expressions.",
                            "The report's 30.44 constant is evaluated with Decimal; deployed SQL coercion is unverified.",
                            "Source snapshot, deployed code and agreed borrower terms are not certified by the supplied commit.",
                            "No payment rows does not prove no payments. Stored totals are not reviewed opening balances.",
                            "Released control is evaluated at release (or comparison time if earlier) and is never an active candidate."]}


def write_worksheet(output, summary, records, *, as_of, business_timezone, owner_profile=None):
    worksheet = build_worksheet(summary, records, as_of=as_of, business_timezone=business_timezone, owner_profile=owner_profile)
    (output / "reconciliation.json").write_text(encode(worksheet) + "\n", encoding="utf-8")
    if owner_profile:
        from .legacy_owner_rules import COLLECTION_PROFILE, LINODE_PROFILE
        rounding_note = ("For this rehearsal, item interest is summed, multiplied by additional months and rounded once "
                         "to the nearest rupee, with half-even ties. Actual collections and accepted interest losses are separate; "
                         "their missing amounts remain unknown. No automatic shortfall allowance or loan waiver is applied."
                         if owner_profile in {COLLECTION_PROFILE, LINODE_PROFILE} else
                         "Fractional item charges require a confirmed aggregation rule.")
        diagnostics = worksheet["owner_rule_diagnostics"]
        calculated = sum(row["calculation"] is not None for row in diagnostics)
        rows = []
        for row in diagnostics:
            calculation = row["calculation"] or {}
            values = (row["source_number"], row["source_loan_id"], calculation.get("additional_months", ""),
                      calculation.get("additional_interest", ""), calculation.get("next_increase_on", ""),
                      ", ".join(row["blockers"]) or "Illustration only")
            rows.append("<tr>" + "".join(f"<td>{escape(str(value))}</td>" for value in values) + "</tr>")
        html = ("<!doctype html><html lang='en'><meta charset='utf-8'><title>JCL owner rule review</title>"
                "<style>body{font:16px system-ui;margin:2rem;color:#173c36}table{border-collapse:collapse}"
                "td,th{padding:.5rem;border:1px solid #bbb;text-align:left}th{background:#edf5f2}</style>"
                "<h1>JCL owner rule review</h1>"
                f"<p>Rehearsal date: {escape(as_of)} ({escape(business_timezone)}). No approved cutover.</p>"
                f"<p>{len(diagnostics)} retained active loans; {calculated} collection illustrations; "
                f"{len(diagnostics) - calculated} held. <strong>Zero loans approved or imported.</strong></p>"
                "<p>Interest below assumes unchanged original principal, the first month paid upfront and no later collections. "
                "It excludes document charges and is not an approved opening balance or accounting accrual.</p>"
                "<p>Net weight uses the source-scoped owner clarification. Gross weight remains unknown. "
                f"{rounding_note} Source errors remain held.</p>"
                "<p><a href='opening-review.html'>Opening evidence review</a> · "
                "<a href='reconciliation.json'>Source comparisons and full diagnostics</a></p>"
                "<table><thead><tr><th>Loan</th><th>Source ID</th><th>Additional months</th>"
                "<th>Illustrative additional interest (INR)</th><th>Next increase</th><th>Review state</th>"
                "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></html>")
        (output / "owner-rule-review.html").write_text(html, encoding="utf-8")
    return worksheet
