"""Offline adaptation of release claims into unaccepted historical evidence."""
from collections import Counter, defaultdict
from datetime import date
from html import escape
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED
from zoneinfo import ZoneInfo

from apps.tenant_apps.loans.services import archive_contract as contract
from apps.tenant_apps.loans.services.portability_validation import PortabilityValidationError

from .legacy_owner_rules import check_profile, weight_evidence
from .legacy_archive_review import date_findings, select_pilot_case, write_case_review
from .legacy_preview import encode, number, timestamp
from .parsers import PortabilityError

PROFILE = "legacy-closed-archive-preview/2"


def candidates(summary, records, *, business_timezone, review_date, owner_profile=None):
    """Yield every released loan, including held documents; never resolve local IDs."""
    check_profile(summary, owner_profile)
    zone = ZoneInfo(business_timezone)
    as_of = date.fromisoformat(review_date)
    by_table = defaultdict(dict)
    children = defaultdict(lambda: defaultdict(list))
    for record in records:
        table = record["source"]["table"]
        by_table[table][record["source"]["id"]] = record
        if table in {"girvi_loanitem", "girvi_loanpayment", "girvi_release"}:
            children[table][record["facts"]["loan_id"]].append(record)
    for pk, loan in by_table["girvi_loan"].items():
        releases = children["girvi_release"][pk]
        if not releases:
            continue
        notes = []
        transformations = []

        def day(raw, field):
            parsed = timestamp(raw)
            try:
                result = parsed.astimezone(zone).date() if parsed else None
            except (OverflowError, ValueError):
                result = None
            if result is None:
                notes.append(field + ": unknown or invalid timestamp")
            elif result > as_of:
                notes.append(field + ": after review date")
            return result.isoformat() if result else None

        def decimal(raw, field):
            value = number(raw)
            rendered = format(value, "f") if value is not None else ""
            if not re.fullmatch(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?", rendered):
                notes.append(field + ": unknown or outside archive decimal bounds")
                return None
            return rendered

        facts = loan["facts"]
        items = children["girvi_loanitem"][pk]
        payments = children["girvi_loanpayment"][pk]
        graph = [loan, *items, *payments, *releases]
        borrower = by_table["contact_customer"].get(facts["customer_id"])
        series = by_table["girvi_series"].get(facts["series_id"])
        licence = by_table["girvi_license"].get(series["facts"]["license_id"]) if series else None
        for related in [borrower, series, licence, *[
                by_table["contact_customer"].get(r["facts"]["released_by_id"]) for r in releases]]:
            if related is not None and related not in graph:
                graph.append(related)
        collateral = []
        for item in items:
            raw = item["facts"]
            quantity = number(raw["quantity"])
            valid_quantity = quantity is not None and quantity == int(quantity) and 1 <= quantity <= 10000
            if not valid_quantity:
                notes.append("collateral.quantity: unknown or outside bounds")
            description = raw["itemdesc"]
            if description is not None:
                normalized = re.sub(r"[\r\n\t]+", " ", description)
                if normalized != description:
                    transformations.append({"rule": "description-line-whitespace/1",
                        "source_id": item["source"]["external_id"], "field": "itemdesc",
                        "before": description, "after": normalized})
                description = normalized
            collateral.append({"description": description,
                "quantity": int(quantity) if valid_quantity else None, "gross_weight": None,
                "net_weight": decimal(raw["weight"], "collateral.net_weight") if owner_profile else None})
        if items and any(not item["description"] for item in collateral):
            notes.append("collateral: missing descriptions; structured facts unknown, raw rows retained")
            collateral = []
        if len(releases) != 1:
            notes.append("closed_on: multiple release claims; raw rows retained")
        document = {"profile": contract.PROFILE, "source": {
            "namespace": summary["source_namespace"], "system": summary["source_system"],
            "loan_id": loan["source"]["external_id"],
            "snapshot_reference": "sha256:" + summary["archive_sha256"],
            "evidence_reference": "Legacy COPY source rows; schema " + summary["source_schema"]},
            "facts": {"status": "CLOSED", "raw_status": "RELEASE_ROW_PRESENT",
                "loan_number": facts["loan_id"],
                "borrower_reference": {"system": summary["source_system"], "id": "contact_customer:" + facts["customer_id"]}
                    if facts["customer_id"] else None,
                "borrower_name": borrower["facts"]["name"] if borrower else None,
                "opened_on": day(facts["loan_date"], "opened_on"),
                "closed_on": day(releases[0]["facts"]["release_date"], "closed_on") if len(releases) == 1 else None,
                "original_principal": None, "reported_balance": None,
                "collateral": collateral or None,
                "payments": [{"id": p["source"]["external_id"],
                    "date": day(p["facts"]["payment_date"], "payment.date"),
                    "amount": decimal(p["facts"]["payment_amount"], "payment.amount")} for p in payments] or None},
            "source_records": graph + [{"adapter": PROFILE, "business_timezone": business_timezone,
                "review_date": review_date, "owner_profile": owner_profile,
                "net_weight_evidence": weight_evidence(summary, owner_profile),
                "interpretation": "Release row is a closure claim, not settlement or custody proof. Stored loan_amount is not original principal. Absent rows mean unknown evidence.",
                "mapping_notes": notes, "transformations": transformations}]}
        result = {"source_id": loan["source"]["external_id"], "loan_number": facts["loan_id"],
            "stored_source_amount": facts["loan_amount"], "mapping_notes": notes,
            "transformations": transformations,
            "source_issue_codes": sorted({i["code"] for r in graph for i in r["issues"]}),
            "document": document, "accepted": False}
        try:
            contract.parse(contract.encode(document))
            result["review"] = contract.review_document(document)
            result["held_reason"] = None
        except PortabilityValidationError as exc:
            result["held_reason"] = str(exc)
        yield result


def write_report(output_dir, summary, records, **options):
    # Validate configuration before creating a private output directory.
    check_profile(summary, options.get("owner_profile"))
    ZoneInfo(options["business_timezone"])
    date.fromisoformat(options["review_date"])
    output = Path(output_dir)
    try:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
    except OSError as exc:
        raise PortabilityError("Use a new output directory; existing reports are never overwritten.") from exc
    (output / ".gitignore").write_text("*\n", encoding="utf-8")
    counts = Counter()
    findings = Counter()
    rows = []
    review_cases = []
    pilot = {}
    total_bytes = 0
    with (output / "source-records.jsonl").open("x", encoding="utf-8") as target:
        for record in records:
            target.write(encode(record) + "\n")
    with ZipFile(output / "candidates.zip", "x", compression=ZIP_DEFLATED) as bundle, \
            (output / "index.jsonl").open("x", encoding="utf-8") as index, \
            (output / "held.jsonl").open("x", encoding="utf-8") as held:
        for position, result in enumerate(candidates(summary, records, **options), 1):
            document = result.pop("document")
            counts["released_loans"] += 1
            if result["held_reason"]:
                counts["held"] += 1
                held.write(encode({**result, "document": document}) + "\n")
            else:
                counts["schema_valid_candidates"] += 1
                payload = contract.encode(document)
                total_bytes += len(payload)
                if total_bytes > 256 * 1024 * 1024:
                    raise PortabilityError("Candidate output exceeds 256 MiB; report is incomplete.")
                filename = f"candidate-{position:06d}.json"
                bundle.writestr(filename, payload)
                result["candidate_file"] = filename
                findings.update(f["code"] for f in result["review"]["findings"])
            dates = date_findings(document, options["business_timezone"], options["review_date"])
            result["date_findings"] = dates
            if dates or result["transformations"]:
                review_cases.append({**result, "opened_on": document["facts"]["opened_on"],
                                     "closed_on": document["facts"]["closed_on"]})
            category = select_pilot_case(result, document, pilot)
            if category:
                pilot[category] = {**result, "category": category}
                (output / ("pilot-" + category + ".json")).write_bytes(contract.encode(document))
            index.write(encode(result) + "\n")
            # Full cohort is navigable in the report; JSONL retains detailed findings.
            rows.append([result["source_id"], result["loan_number"], result["stored_source_amount"],
                result["held_reason"] or "Schema valid; unaccepted",
                "; ".join(result["mapping_notes"] + result["source_issue_codes"] +
                          [d["code"] for d in dates] +
                          (["DESCRIPTION_WHITESPACE_NORMALIZED"] if result["transformations"] else []))])
    result_summary = {"profile": PROFILE, "source": summary, "options": options,
        "counts": {"released_loans": 0, "schema_valid_candidates": 0, "held": 0, **counts,
                   "unreleased_loans_excluded": summary["counts"]["girvi_loan"] - counts["released_loans"],
                   "accepted": 0}, "finding_counts": dict(findings), "candidate_bytes": total_bytes}
    def table(headers, values):
        return '<table><tr>' + ''.join('<th>' + escape(str(h)) + '</th>' for h in headers) + '</tr>' + ''.join(
            '<tr>' + ''.join('<td>' + escape(str(v)) + '</td>' for v in row) + '</tr>' for row in values) + '</table>'
    html = ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
        '<title>Closed-loan archive source review</title><style>body{font:16px system-ui;margin:32px;color:#183d32}'
        'table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccd8d2;padding:8px;text-align:left;overflow-wrap:anywhere}'
        'th{background:#eef4f0}</style><h1>Closed-loan archive source review</h1>'
        '<p><strong>Read-only preparation. Zero records accepted. No destination Workspace bound.</strong></p>'
        '<p>Release rows support a closure claim only. Settlement balances and original principal remain unknown. '
        'The stored source amount below is a mutable legacy value, not verified debt. Missing payments and collateral '
        'remain unknown. Dates use the stated business timezone; raw timestamps are retained. '
        'Schema validity allows historical retention review; it does not approve financial admission or certify source truth.</p>'
        + table(['Count', 'Loans'], result_summary['counts'].items())
        + table(['Archive finding (counts may overlap)', 'Candidates'], findings.items())
        + '<p>Timezone: ' + escape(options['business_timezone']) + '; review date: ' + escape(options['review_date']) + '</p>'
        + '<p><a href="case-review.html">Exceptions and proposed pilot</a> · '
        '<a href="candidates.zip">Individual candidate JSON files (ZIP)</a> · <a href="index.jsonl">Full review index</a> · '
        '<a href="held.jsonl">Held candidates</a> · <a href="source-records.jsonl">All extracted source records</a> · '
        '<a href="summary.json">Source identity and summary</a></p>'
        '<p>The ZIP is a review container. The archive upload accepts one extracted JSON document at a time. '
        'Review source exceptions before any acceptance. These files contain private customer data.</p>'
        + table(['Source ID', 'Loan number', 'Stored source amount (not original principal)', 'Disposition', 'Source exceptions'], rows)
        + '</html>')
    (output / "review.html").write_text(html, encoding="utf-8")
    (output / "summary.json").write_text(encode(result_summary) + "\n", encoding="utf-8")
    write_case_review(output, review_cases, pilot)
    (output / "COMPLETE").write_text(PROFILE + "\n", encoding="utf-8")
    return result_summary
