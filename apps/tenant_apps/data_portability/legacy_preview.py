"""Source-only mapping proposals; no ORM, destination binding, or financial writes."""
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
from html import escape
import json
from pathlib import Path
import re
from uuid import UUID, uuid5

from .legacy_dump import COLUMNS, source_schema
from .legacy_profiles import apply_corrections, get_profile
from .parsers import PortabilityError

PROFILE = "legacy-dump-preview/1"
TARGETS = {
    "contact_customer": "party-master/1", "contact_contact": "party-contact/1",
    "contact_address": "party-address/1", "girvi_license": "Loans licence setup",
    "girvi_series": "Loans series setup", "girvi_loan": "Loans migration review",
    "girvi_loanitem": "Loan collateral evidence", "girvi_loanpayment": "Loan payment evidence",
    "girvi_release": "Loan release evidence",
}
REFERENCES = {
    "contact_contact": {"customer_id": "contact_customer"},
    "contact_address": {"customer_id": "contact_customer"},
    "girvi_series": {"license_id": "girvi_license"},
    "girvi_loan": {"customer_id": "contact_customer", "series_id": "girvi_series"},
    "girvi_loanitem": {"loan_id": "girvi_loan"},
    "girvi_loanpayment": {"loan_id": "girvi_loan"},
    "girvi_release": {"loan_id": "girvi_loan", "released_by_id": "contact_customer"},
}
NUMBERS = {
    "girvi_loan": "loan_amount interest tenure value",
    "girvi_loanitem": "quantity weight purity loanamount interestrate interest",
    "girvi_loanpayment": "payment_amount principal_payment interest_payment",
}
DATE_FIELDS = {"girvi_loan": "loan_date", "girvi_loanpayment": "payment_date", "girvi_release": "release_date"}
BOOLEAN_FIELDS = {"contact_customer": "active", "contact_contact": "is_verified is_default",
                  "contact_address": "is_verified is_default", "girvi_series": "is_active",
                  "girvi_loanpayment": "with_release"}
RELATIONS = {"s": "SON_OF", "d": "DAUGHTER_OF", "f": "FATHER_OF", "p": "PARENT_OF",
             "h": "HUSBAND_OF", "w": "WIFE_OF", "o": "OTHER"}
DECIMAL_TEXT = re.compile(r"-?[0-9]{1,20}(?:\.[0-9]{1,10})?\Z")


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def namespace_uuid(value):
    try:
        namespace = UUID(str(value))
    except (ValueError, AttributeError) as exc:
        raise PortabilityError("Provide a stable source namespace UUID and reuse it for later snapshots.") from exc
    if namespace.int == 0:
        raise PortabilityError("The source namespace cannot be the nil UUID.")
    return namespace


def number(value):
    if not isinstance(value, str) or not DECIMAL_TEXT.fullmatch(value):
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def timestamp(value):
    try:
        result = datetime.fromisoformat(value)
        return result if result.utcoffset() is not None else None
    except (ValueError, TypeError):
        return None


def add_issue(record, code, field, message, severity="ERROR"):
    record["issues"].append({"code": code, "field": field, "message": message,
                             "severity": severity, "rule_version": 1,
                             "before": None, "after": None})


def build_preview(extracted, *, schema, source_namespace, source_profile=None):
    source_schema(schema)
    if extracted.get("source_schema") != schema:
        raise PortabilityError("Extracted records must belong to the selected source schema.")
    profile = get_profile(source_profile) if source_profile else None
    if profile and profile.schema != schema:
        raise PortabilityError("The source profile does not match the selected source schema.")
    namespace = namespace_uuid(source_namespace)
    tenant_namespace = uuid5(namespace, schema)
    system = f"legacy:{namespace.hex}:{schema}"
    raw_tables = extracted["tables"]
    tables, corrections = (apply_corrections(raw_tables, profile_key=profile.key) if profile else (raw_tables, {}))
    if set(tables) != set(COLUMNS):
        raise PortabilityError("The selected source table set is incomplete.")

    def reference(table, pk):
        return {"source_system": system, "external_id": f"{table}:{pk}"}

    records, lookup = [], {}
    for table in COLUMNS:
        for pk, row in sorted(tables[table].items(), key=lambda item: int(item[0])):
            record = {
                "source": {**reference(table, pk), "schema": schema, "table": table, "id": pk,
                           "correction": corrections.get((table, pk))},
                "proposed_id": str(uuid5(tenant_namespace, f"{table}:{pk}")),
                "source_sha256": hashlib.sha256(encode(raw_tables[table][pk]).encode("utf-8")).hexdigest(),
                "target": TARGETS[table], "facts": row, "references": {},
                "review_route": "SOURCE_MAPPING_REVIEW", "import_ready": False, "issues": [],
            }
            records.append(record)
            lookup[table, pk] = record
            for field, target in REFERENCES.get(table, {}).items():
                value = row[field]
                if value is None and field == "released_by_id":
                    add_issue(record, "COLLECTOR_UNKNOWN", field, "The source does not identify the collector.", "WARNING")
                    continue
                record["references"][field] = reference(target, value) if value is not None else None
                if value not in tables[target]:
                    add_issue(record, "MISSING_REFERENCE", field, "The referenced record is absent from the selected tenant.")
            for field in NUMBERS.get(table, "").split():
                value = number(row[field])
                if value is None:
                    add_issue(record, "INVALID_NUMBER", field, "A required source number is missing or invalid.")
                elif value < 0:
                    add_issue(record, "NEGATIVE_NUMBER", field, "A source amount or measurement is negative.")
            for field in BOOLEAN_FIELDS.get(table, "").split():
                if row[field] not in {"t", "f"}:
                    add_issue(record, "INVALID_BOOLEAN", field, "The source flag must be true or false.")
            if table in DATE_FIELDS and timestamp(row[DATE_FIELDS[table]]) is None:
                add_issue(record, "INVALID_DATE", DATE_FIELDS[table], "A timezone-aware source timestamp is required.")
            if table == "contact_customer":
                record["proposed_fields"] = {
                    "name": row["name"], "relation_name": row["relatedto"],
                    "relation_kind": RELATIONS.get(row["relatedas"]),
                    "status": {"t": "ACTIVE", "f": "INACTIVE"}.get(row["active"]),
                }
                if not (row["name"] or "").strip():
                    add_issue(record, "CUSTOMER_NAME_MISSING", "name", "Supply the customer's name.")
                if row["relatedas"] not in RELATIONS:
                    add_issue(record, "RELATION_MAPPING_REQUIRED", "relatedas", "Review the source relationship label.", "WARNING")
                record["review_route"] = "PARTY_MAPPING_REVIEW"
            elif table == "girvi_license":
                add_issue(record, "LICENCE_MAPPING_REQUIRED", "name", "Select a destination licence revision; source name and renewal date do not establish number/validity.", "WARNING")
            elif table == "girvi_series":
                add_issue(record, "SERIES_MAPPING_REQUIRED", "license_id", "Select a destination series under the mapped licence.", "WARNING")
            elif table == "girvi_loanitem":
                if "is_repledged" in row and row["is_repledged"] != "f":
                    add_issue(record, "REPLEDGE_CUSTODY_REVIEW", "is_repledged",
                              "Repledged or unknown source custody requires separate review before opening migration.")
                if row["itemtype"] not in {"Gold", "Silver"}:
                    add_issue(record, "METAL_MAPPING_REQUIRED", "itemtype", "Review the destination metal mapping and preserve its source label.", "WARNING")
                if row["item_id"] is not None:
                    add_issue(record, "LEGACY_PRODUCT_REFERENCE", "item_id", "The referenced legacy product is outside this preview; preserve supplied collateral facts.", "WARNING")
                for field in ("weight", "loanamount", "quantity"):
                    if number(row[field]) == 0:
                        add_issue(record, "NONPOSITIVE_COLLATERAL", field, "Collateral weight, quantity and principal must be reviewed when zero.")
                purity = number(row["purity"])
                if purity is not None and not 0 < purity <= 100:
                    add_issue(record, "INVALID_PURITY", "purity", "Source purity must be reviewed; expected percentage is above zero and at most 100.")

    linked = {table: defaultdict(list) for table in ("girvi_loanitem", "girvi_loanpayment", "girvi_release")}
    for table, groups in linked.items():
        for row in tables[table].values():
            groups[row["loan_id"]].append(row)
    cohorts = Counter()
    seen_numbers = {}
    for pk, row in tables["girvi_loan"].items():
        record = lookup["girvi_loan", pk]
        items, payments, releases = (linked[table][pk] for table in linked)
        state = "RELEASED" if releases else "UNRELEASED"
        record.update(source_state=state, item_count=len(items), payment_count=len(payments),
                      review_route="RELEASED_RECORD_REVIEW" if releases else "OPENING_POSITION_REVIEW")
        cohorts[state] += 1
        if not items:
            add_issue(record, "NO_SEPARATE_ITEMS", "item_desc", "Review inline collateral facts; no item rows are present.", "WARNING")
        if not payments:
            add_issue(record, "NO_PAYMENT_ROWS", "", "No payment rows are present; this does not prove no payments occurred.", "WARNING")
        if len(releases) > 1:
            add_issue(record, "MULTIPLE_RELEASES", "", "Multiple release rows refer to this loan.")
        if row["loan_type"] != "Given" or row["interest_type"] != "Simple":
            add_issue(record, "UNSUPPORTED_LOAN_TERMS", "", "This source loan type or interest method requires a separate review.")
        series = tables["girvi_series"].get(row["series_id"], {})
        if "loan_type" in series and series["loan_type"] != "Given":
            add_issue(record, "UNSUPPORTED_SERIES_LOAN_TYPE", "series_id",
                      "The source series is not explicitly lending Given loans; review its type before migration.")
        principal = number(row["loan_amount"])
        if principal is not None and principal <= 0:
            add_issue(record, "NONPOSITIVE_PRINCIPAL", "loan_amount", "Source principal must be greater than zero for operational migration.")
        original = row["loan_id"]
        if not original:
            add_issue(record, "LOAN_NUMBER_MISSING", "loan_id", "The original loan number is missing.")
        elif original in seen_numbers:
            for other in (record, seen_numbers[original]):
                add_issue(other, "DUPLICATE_LOAN_NUMBER", "loan_id", "The original number is used by more than one source loan.")
        else:
            seen_numbers[original] = record
        for source_field, item_field, code in (("loan_amount", "loanamount", "PRINCIPAL_ITEM_MISMATCH"),
                                               ("interest", "interest", "INTEREST_ITEM_MISMATCH")):
            values = [number(item[item_field]) for item in items]
            value = number(row[source_field])
            if items and value is not None and all(v is not None for v in values) and sum(values) != value:
                add_issue(record, code, source_field, "Stored loan total differs from its item total.")
        loan_date = timestamp(row["loan_date"])
        for table, children, field in (("girvi_loanpayment", payments, "payment_date"), ("girvi_release", releases, "release_date")):
            for child in children:
                child_record = lookup[table, child["id"]]
                date = timestamp(child[field])
                if date is not None and loan_date is not None and date < loan_date:
                    add_issue(child_record, "DATE_BEFORE_LOAN", field, "This event is dated before the source loan.")
                if table == "girvi_loanpayment":
                    p, i, total = (number(child[k]) for k in ("principal_payment", "interest_payment", "payment_amount"))
                    if all(v is not None for v in (p, i, total)) and p + i != total:
                        add_issue(child_record, "PAYMENT_SPLIT_MISMATCH", "payment_amount", "Principal plus interest does not equal payment amount.")
                if any(issue["severity"] == "ERROR" for issue in child_record["issues"]):
                    add_issue(record, "LINKED_EVENT_ISSUE", "", "A linked payment or release has an error; inspect its source record.")
        if any(any(issue["severity"] == "ERROR" for issue in lookup["girvi_loanitem", item["id"]]["issues"]) for item in items):
            add_issue(record, "LINKED_ITEM_ISSUE", "", "A linked collateral item has an error; inspect its source record.")

    issue_counts = Counter(issue["code"] for record in records for issue in record["issues"])
    summary = {
        "profile": PROFILE, "coverage": "SOURCE_REVIEW_ONLY", "import_ready": False,
        "source_namespace": str(namespace), "tenant_namespace": str(tenant_namespace),
        "source_system": system, "source_schema": schema, "source_profile": profile.key if profile else None,
        "archive_sha256": extracted["archive_sha256"],
        "destination_workspace": None, "counts": {table: len(rows) for table, rows in tables.items()},
        "loan_cohorts": dict(cohorts), "issue_counts": dict(sorted(issue_counts.items())),
        "records_with_errors": sum(any(i["severity"] == "ERROR" for i in r["issues"]) for r in records),
        "excluded_tables": sorted(set(extracted["schemas"][schema]) - set(COLUMNS)),
        "limits": {"archive_mib": 64, "extracted_mib": 128, "source_records": 100000},
        "pending": ["Explicit destination Workspace and Party/setup mappings",
                    "Approved opening balances, accrual basis and continued servicing terms",
                    "Limited-evidence released-record contract",
                    "Source/dump version and calculation reconciliation",
                    "Media bytes, unsupported relationships and final production cutover"],
    }
    return summary, records


def propose_collateral_exclusions(summary, records):
    """Annotate a reversible source selection; retain every source row and issue."""
    if summary.get("profile") != PROFILE or summary.get("coverage") != "SOURCE_REVIEW_ONLY":
        raise PortabilityError("Exclusion proposals require a source-only legacy preview.")
    if any(r["source"]["schema"] != summary["source_schema"] or
           r["source"]["source_system"] != summary["source_system"] for r in records):
        raise PortabilityError("Exclusion proposals must stay within the selected source tenant.")
    children = defaultdict(list)
    for record in records:
        if record["source"]["table"] == "girvi_loanitem":
            children[record["facts"]["loan_id"]].append(record)
    exclusions = {}
    for record in records:
        if record["source"]["table"] != "girvi_loan":
            continue
        pk = record["source"]["id"]
        reasons = set()
        if not children[pk]:
            reasons.add("NO_STRUCTURED_ITEMS")
        for item in children[pk]:
            facts = item["facts"]
            if not (facts["itemdesc"] or "").strip():
                reasons.add("MISSING_ITEM_DESCRIPTION")
            for field in ("weight", "quantity", "loanamount", "purity"):
                value = number(facts[field])
                if (value is None or value <= 0 or
                        (field == "purity" and value > 100) or
                        (field == "quantity" and value != value.to_integral_value())):
                    reasons.add(f"INVALID_ITEM_{field.upper()}")
        disposition = "SKIP_INITIAL_MIGRATION" if reasons else "RETAIN_FOR_REVIEW"
        record["exclusion_proposal"] = {"disposition": disposition, "reasons": sorted(reasons)}
        if reasons:
            exclusions[pk] = sorted(reasons)
    # A loan and its source child graph stay together; customer/setup rows are retained.
    for record in records:
        if record["source"]["table"] in {"girvi_loanitem", "girvi_loanpayment", "girvi_release"}:
            reasons = exclusions.get(record["facts"]["loan_id"])
            if reasons:
                record["exclusion_proposal"] = {"disposition": "SKIP_WITH_LOAN", "reasons": reasons}
    groups = []
    for state in ("UNRELEASED", "RELEASED"):
        for disposition in ("SKIP_INITIAL_MIGRATION", "RETAIN_FOR_REVIEW"):
            group = [r for r in records if r["source"]["table"] == "girvi_loan" and
                     r["source_state"] == state and r["exclusion_proposal"]["disposition"] == disposition]
            amounts = [number(r["facts"]["loan_amount"]) for r in group]
            dates = [timestamp(r["facts"]["loan_date"]) for r in group]
            valid_dates = [d for d in dates if d is not None]
            groups.append({"source_state": state, "disposition": disposition, "loans": len(group),
                           "source_principal_known_sum": str(sum((a for a in amounts if a is not None), Decimal("0"))),
                           "source_principal_unknown_count": sum(a is None for a in amounts),
                           "oldest_source_timestamp": min(valid_dates).isoformat() if valid_dates else None,
                           "newest_source_timestamp": max(valid_dates).isoformat() if valid_dates else None,
                           "source_date_unknown_count": sum(d is None for d in dates),
                           "loans_with_errors": sum(any(i["severity"] == "ERROR" for i in r["issues"]) for r in group)})
    evidence = sorted((r["source"]["external_id"], r["source_sha256"]) for r in records)
    summary["exclusion_proposal"] = {
        "policy": "incomplete-collateral/1", "approved": False, "age_cutoff": None,
        "excluded_loans": len(exclusions), "groups": groups,
        "reasons": dict(sorted(Counter(reason for reasons in exclusions.values() for reason in reasons).items())),
        "selection_sha256": hashlib.sha256(encode({"source_system": summary["source_system"],
            "archive_sha256": summary["archive_sha256"], "policy": "incomplete-collateral/1",
            "records": evidence, "excluded": exclusions}).encode("utf-8")).hexdigest(),
    }


def render_html(summary, records):
    def table(headers, rows):
        return '<table><thead><tr>' + ''.join(f'<th>{escape(str(h))}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join(
            '<tr>' + ''.join(f'<td>{escape(str(value))}</td>' for value in row) + '</tr>' for row in rows) + '</tbody></table>'
    errors = [(r["source"]["table"], r["source"]["id"], r["facts"].get("loan_id", ""), i["code"], i["message"])
              for r in records for i in r["issues"] if i["severity"] == "ERROR"]
    proposal = summary.get("exclusion_proposal")
    selection = ""
    if proposal:
        selection = ('<h2>Proposed exclusions for the initial migration</h2>'
                     '<p class="notice">This is an unapproved selection proposal. All source records and issues remain in the review. '
                     'Exclusion does not close, forgive or delete a loan. Customers and setup records are retained.</p>' +
                     table(['Source state', 'Proposed treatment', 'Loans', 'Stored source principal sum', 'Unknown amounts'],
                           [(g['source_state'], g['disposition'], g['loans'], g['source_principal_known_sum'],
                             g['source_principal_unknown_count']) for g in proposal['groups']]) +
                     '<p>These sums use stored loan amounts; they are not verified cutover balances. '
                     'The rule checks structured collateral completeness, not age. Retained loans still require financial and setup review.</p>' +
                     table(['Exclusion reason', 'Loans (reasons may overlap)'], proposal['reasons'].items()) +
                     '<p>proposed-exclusions.jsonl lists every proposed skipped loan and its reasons. '
                     'Its items, payments and releases are marked to stay with that loan in records.jsonl.</p>')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Legacy migration preview</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px;color:#183d32}'
            'table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ccd8d2;padding:8px;text-align:left;overflow-wrap:anywhere}'
            'th{background:#eef4f0}.notice{padding:18px;background:#fff2ce}code{overflow-wrap:anywhere}</style><body>'
            f'<h1>Legacy migration preview: {escape(summary["source_schema"])}</h1>'
            '<p class="notice"><strong>Read-only source review. Nothing has been imported.</strong> '
            'Balances are not approved, and no destination Workspace is bound. '
            'Records without errors still require mapping and domain review.</p>'
            '<h2>Source records</h2>' + table(['Source table', 'Records'], summary['counts'].items()) +
            '<h2>Loan review routes</h2>' + table(['Source state', 'Loans'], summary['loan_cohorts'].items()) +
            '<p>Unreleased loans require an opening-position review. Released loans require a historical-record review. '
            'No loan is certified as complete history by this preview.</p>' + selection + '<h2>Proposed mappings</h2>' +
            table(['Source', 'Destination to review'], TARGETS.items()) +
            '<p>Customer, licence, series and loan references resolve only within this selected source schema. '
            'Original IDs and numbers remain unchanged in the detailed records.</p><h2>Issue counts</h2>' +
            table(['Issue', 'Occurrences'], summary['issue_counts'].items()) +
            '<h2>Errors to review</h2><p>First 200 error occurrences; all issues and source facts are in records.jsonl. '
            'A count of occurrences is not a count of unique loans.</p>' +
            table(['Table', 'Source ID', 'Loan reference', 'Issue', 'Explanation'], errors[:200]) +
            '<h2>Still required</h2><ul>' + ''.join(f'<li>{escape(p)}</li>' for p in summary['pending']) +
            '</ul><h2>Tables outside this preview</h2><p>' + escape(', '.join(summary['excluded_tables'])) +
            '</p><h2>Source identity</h2><p>Reuse this namespace for later snapshots of this legacy system: <code>' +
            escape(summary['source_namespace']) + '</code></p><p>Archive SHA-256: <code>' +
            escape(summary['archive_sha256']) + '</code></p><p>summary.json and records.jsonl are local review artifacts, '
            'not canonical import packages. They contain private source data.</p></body></html>')


def write_preview(output_dir, summary, records, *, opening_documents=None, reconciliation=None):
    output = Path(output_dir)
    try:
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError as exc:
        raise PortabilityError("Use a new output directory; existing reports are never overwritten.") from exc
    try:
        # Ignore the whole local report directory if it is created inside a checkout.
        (output / ".gitignore").write_text("*\n", encoding="utf-8")
        with (output / "records.jsonl").open("x", encoding="utf-8", newline="\n") as target:
            for record in records:
                target.write(encode(record) + "\n")
        if summary.get("exclusion_proposal"):
            with (output / "proposed-exclusions.jsonl").open("x", encoding="utf-8", newline="\n") as target:
                for record in records:
                    if record.get("exclusion_proposal", {}).get("disposition") == "SKIP_INITIAL_MIGRATION":
                        target.write(encode(record) + "\n")
        (output / "review.html").write_text(render_html(summary, records), encoding="utf-8")
        (output / "summary.json").write_text(encode(summary) + "\n", encoding="utf-8")
        if opening_documents is not None:
            from .opening_review import write_review_files
            write_review_files(output, opening_documents)
        if reconciliation is not None:
            from .legacy_reconciliation import write_worksheet
            write_worksheet(output, summary, records, **reconciliation)
        # Written last: a failed output is never presented as a complete report.
        (output / "COMPLETE").write_text(PROFILE + "\n", encoding="utf-8")
    except OSError as exc:
        raise PortabilityError("Could not finish writing the preview; a report is complete only when COMPLETE exists.") from exc
    return output
