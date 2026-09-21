"""Source timeline diagnostics and a small, unaccepted retention pilot proposal."""
from collections import Counter
from datetime import date
from html import escape
from zoneinfo import ZoneInfo

from .legacy_preview import encode, timestamp


def date_findings(document, business_timezone, review_date):
    zone = ZoneInfo(business_timezone)
    as_of = date.fromisoformat(review_date)
    rows = [r for r in document["source_records"] if "source" in r]
    loan = next(r for r in rows if r["source"]["table"] == "girvi_loan")
    opening = timestamp(loan["facts"]["loan_date"])
    findings = []
    for row in rows:
        field = {"girvi_loan": "loan_date", "girvi_release": "release_date",
                 "girvi_loanpayment": "payment_date"}.get(row["source"]["table"])
        if not field:
            continue
        raw = row["facts"][field]
        value = timestamp(raw)
        codes = []
        if value is None:
            codes.append("UNKNOWN_TIMESTAMP")
        else:
            try:
                if value.astimezone(zone).date() > as_of:
                    codes.append("AFTER_REVIEW_DATE")
            except (OverflowError, ValueError):
                codes.append("UNREPRESENTABLE_LOCAL_DATE")
            if opening is not None and value < opening:
                codes.append("RELEASE_BEFORE_ORIGINATION" if field == "release_date" else "PAYMENT_BEFORE_ORIGINATION")
        for code in codes:
            findings.append({"code": code, "source_id": row["source"]["external_id"],
                "field": field, "raw_timestamp": raw, "raw_opened_at": loan["facts"]["loan_date"],
                "disposition": "Retain unchanged; source correction unverified."})
    return findings


def select_pilot_case(result, document, selected):
    """At most three distinct candidates; eligibility is not acceptance approval."""
    if result["held_reason"] or result["date_findings"]:
        return None
    if any(i["severity"] == "ERROR" for r in document["source_records"] if "issues" in r for i in r["issues"]):
        return None
    category = ("normalized-description" if result["transformations"] else
                "recorded-payments" if document["facts"]["payments"] else "unknown-payments")
    return category if category not in selected else None


def write_case_review(output, cases, pilot):
    counts = Counter(f["code"] for case in cases for f in case["date_findings"])
    summary = {"date_finding_counts": dict(counts),
        "loans_with_date_findings": sum(bool(c["date_findings"]) for c in cases),
        "loans_with_description_mapping": sum(bool(c["transformations"]) for c in cases),
        "pilot_count": len(pilot), "accepted": False, "destination_workspace": None,
        "pilot_policy": "First candidate per category in source order, excluding schema holds, source ERRORs and timeline findings. Not a representative statistical sample."}
    (output / "case-review.json").write_text(encode({"summary": summary, "cases": cases, "pilot": pilot}) + "\n", encoding="utf-8")
    def cell(value):
        return '<td><pre style="white-space:pre-wrap">' + escape(str(value)) + '</pre></td>'
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Archive exceptions and pilot</title><style>body{font:16px system-ui;margin:32px}td,th{border:1px solid #ccc;padding:10px}table{border-collapse:collapse;width:100%}</style>'
        '<h1>Archive exceptions and proposed pilot</h1><p>Nothing accepted. Destination unselected. '
        'Dates are retained claims, not corrected history. Description whitespace is normalized only in mapped facts; raw evidence is unchanged.</p>'
        '<p><a href="review.html">Full cohort</a> | <a href="case-review.json">Exact findings and transformation evidence</a></p>'
        '<h2>Review counts</h2><pre>' + escape(encode(summary)) + '</pre><h2>Proposed pilot</h2><ul>')
    for category, result in pilot.items():
        html += '<li><a href="pilot-' + category + '.json">' + escape(category) + '</a>: ' + escape(str(result['loan_number'])) + ' — ' + escape(result['source_id']) + '</li>'
    html += '</ul><h2>Date exceptions and description mappings</h2><table><tr><th>Loan</th><th>Source ID</th><th>Dates (raw timestamps)</th><th>Description transformations</th></tr>'
    for case in cases:
        html += '<tr>' + ''.join(cell(v) for v in (case['loan_number'], case['source_id'],
            encode(case['date_findings']), encode(case['transformations']))) + '</tr>'
    (output / "case-review.html").write_text(html + '</table></html>', encoding="utf-8")
