"""Offline adaptation and bounded files for Loans-owned opening reconciliation."""
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

from apps.tenant_apps.loans.services.portability_validation import CATEGORY_LABELS
from apps.tenant_apps.loans.services.opening_validation import COLLECTION_PROFILE, PROFILE, PENDING, validate_opening

from .legacy_preview import encode, number
from .parsers import PortabilityError, decode_json

MAX_BYTES = 64 * 1024 * 1024
MAX_LINE_BYTES = 64 * 1024
MAX_LOANS = 5000


def prepare_openings(summary, records, *, owner_profile=None):
    """Propose review documents, leaving unknown financial facts explicitly null."""
    from .legacy_owner_rules import EVIDENCE, check_profile
    check_profile(summary, owner_profile)
    proposal = summary.get("exclusion_proposal")
    if summary.get("profile") != "legacy-dump-preview/1" or not proposal:
        raise PortabilityError("Opening preparation requires the explicit collateral exclusion proposal.")
    if any(r["source"]["schema"] != summary["source_schema"] or
           r["source"]["source_system"] != summary["source_system"] for r in records):
        raise PortabilityError("Opening preparation must stay within the selected source tenant.")
    children = defaultdict(list)
    for record in records:
        if record["source"]["table"] == "girvi_loanitem":
            children[record["facts"]["loan_id"]].append(record)
    documents = []
    for record in records:
        if (record["source"]["table"] != "girvi_loan" or record["source_state"] != "UNRELEASED" or
                record.get("exclusion_proposal", {}).get("disposition") != "RETAIN_FOR_REVIEW"):
            continue
        facts = record["facts"]
        items = children[record["source"]["id"]]
        collateral = []
        for item in items:
            raw = item["facts"]
            quantity = number(raw["quantity"])
            collateral.append({
                "id": item["source"]["external_id"], "description": raw["itemdesc"],
                "quantity": int(quantity) if quantity is not None and quantity == quantity.to_integral_value() else None,
                "metal": {"Gold": "GOLD", "Silver": "SILVER", "Bronze": "BRONZE"}.get(raw["itemtype"]),
                "gross_weight": None, "net_weight": raw["weight"] if owner_profile else None, "purity": raw["purity"],
                "original_principal": raw["loanamount"], "remaining_principal": None,
                "monthly_rate": raw["interestrate"], "weight_reference": EVIDENCE if owner_profile else None,
                "custody_reference": None, "valuation": None,
            })
        borrower = f"contact_customer:{facts['customer_id']}"
        documents.append({
            "profile": COLLECTION_PROFILE if owner_profile == "jcl-owner/2" else PROFILE,
            "source": {"namespace": summary["source_namespace"], "schema": summary["source_schema"],
                       "loan_id": record["source"]["external_id"], "number": facts["loan_id"],
                       "loan_timestamp": facts["loan_date"], "borrower_id": borrower,
                       "item_ids": [i["source"]["external_id"] for i in items],
                       "archive_sha256": summary["archive_sha256"],
                       "selection_sha256": proposal["selection_sha256"],
                       "loan_sha256": record["source_sha256"], "state": "UNRELEASED", "excluded": False,
                       "errors": [i for i in record["issues"] if i["severity"] == "ERROR"]},
            "cutover": None,
            "mapping": {"workspace_id": None, "borrower_id": None,
                        "borrower_source_system": summary["source_system"], "borrower_external_id": borrower,
                        "licence_revision_id": None, "series_id": None, "product_version_id": None,
                        "evidence_reference": None},
            "balances": None, "terms": None, "collateral": collateral,
            "obligations": None, "continuation": None, "review_reference": None,
        })
        if len(documents) > MAX_LOANS:
            raise PortabilityError("Opening review supports at most 5,000 loans per selected source tenant.")
    return documents


def read_documents(path):
    documents, consumed = [], 0
    try:
        with Path(path).open("rb") as source:
            while True:
                line = source.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break
                consumed += len(line)
                if len(line) > MAX_LINE_BYTES or consumed > MAX_BYTES:
                    raise PortabilityError("Opening review exceeds the 64 MiB file or 64 KiB line limit.")
                try:
                    text = line.decode("utf-8-sig" if not documents else "utf-8")
                except UnicodeDecodeError as exc:
                    raise PortabilityError("Opening review must be UTF-8 JSONL.") from exc
                if not text.strip() or "\x00" in text:
                    raise PortabilityError("Opening review cannot contain empty lines or NUL characters.")
                document = decode_json(text)
                try:
                    encode(document).encode("utf-8")
                except (UnicodeError, RecursionError) as exc:
                    raise PortabilityError("Opening review contains unsupported Unicode or nesting.") from exc
                documents.append(document)
                if len(documents) > MAX_LOANS:
                    raise PortabilityError("Opening review supports at most 5,000 loans.")
    except OSError as exc:
        raise PortabilityError("Could not read the opening review file.") from exc
    if not documents:
        raise PortabilityError("The opening review file contains no loans.")
    return documents


def reconcile_documents(documents):
    results, seen, scopes, destinations, cutovers = [], set(), set(), set(), set()
    counts, groups, categories = Counter(), Counter(), Counter()
    for doc in documents:
        if type(doc) is not dict or type(doc.get("source")) is not dict:
            raise PortabilityError("Each opening review row must identify its source loan.")
        source = doc["source"]
        key = source.get("loan_id")
        if not isinstance(key, str) or not key.strip() or len(key) > 255 or key in seen:
            raise PortabilityError("Opening review requires unique bounded source loan IDs.")
        seen.add(key)
        scopes.add(encode([source.get(k) for k in ("namespace", "schema", "archive_sha256", "selection_sha256")]))
        mapping = doc.get("mapping")
        if type(mapping) is dict and mapping.get("workspace_id") is not None:
            destinations.add(encode(mapping["workspace_id"]))
        cutover = doc.get("cutover")
        if type(cutover) is dict:
            cutovers.add(encode([cutover.get("date"), cutover.get("timezone")]))
        if len(scopes) > 1 or len(destinations) > 1 or len(cutovers) > 1:
            raise PortabilityError("A review must use one source tenant, snapshot, selection, destination Workspace and cutover.")
        if len(seen) > MAX_LOANS:
            raise PortabilityError("Opening review supports at most 5,000 loans.")
        result = {"source_loan_id": key, **validate_opening(doc)}
        results.append(result)
        counts.update(issue["code"] for issue in result["issues"])
        categories.update(issue["category"] for issue in result["issues"])
        groups.update(set(issue["field"].split(".")[0].split("[")[0] for issue in result["issues"]))
    summary = {"profile": PROFILE, "coverage": "DOCUMENT_REVIEW_ONLY", "import_ready": False,
               "loans": len(results), "document_reconciled": sum(r["document_reconciled"] for r in results),
               "loans_with_issues": sum(bool(r["issues"]) for r in results),
               "category_counts": dict(sorted(categories.items())),
               "issue_counts": dict(sorted(counts.items())), "loans_requiring_review": dict(sorted(groups.items())),
               "pending": list(PENDING), "limits": {"file_mib": 64, "line_kib": 64, "loans": MAX_LOANS}}
    return summary, results


def render_review(summary, results):
    def table(headers, rows):
        return '<table><tr>' + ''.join(f'<th>{escape(str(h))}</th>' for h in headers) + '</tr>' + ''.join(
            '<tr>' + ''.join(f'<td>{escape(str(v))}</td>' for v in row) + '</tr>' for row in rows) + '</table>'
    errors = [(r["source_loan_id"], i["field"], CATEGORY_LABELS[i["category"]], i["code"], i["message"]) for r in results for i in r["issues"]]
    return ('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">'
            '<title>Opening-position review</title><style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 20px}'
            'table{border-collapse:collapse;width:100%;margin:20px 0}td,th{border:1px solid #ccc;padding:8px;text-align:left;overflow-wrap:anywhere}'
            '.notice{background:#fff2ce;padding:16px}</style><h1>Opening-position review</h1>'
            '<p class="notice">Offline document reconciliation only. Nothing imported or posted. '
            'A reconciled document still requires source verification, destination authorization, supported servicing and financial commit.</p>'
            f'<p>Loans reviewed: {summary["loans"]}. Documents reconciled: {summary["document_reconciled"]}. '
            f'Loans with issues: {summary["loans_with_issues"]}.</p>'
            '<h2>Information still needed</h2>' + table(['Review group', 'Loans'], summary['loans_requiring_review'].items()) +
            '<p>Unknown balances and fees remain unknown. Stored original principal is not an outstanding balance. '
            'Weight interpretation must have an evidence reference; unrecorded gross weight stays unknown. '
            'Original dates, agreed rules and recognized or prepaid interest must be carried forward explicitly.</p>'
            '<h2>Issues</h2><p>Categories explain why review is blocked; every listed issue still blocks document reconciliation. They do not certify historical acceptance or permission to service a loan.</p><p>First 200 occurrences shown. opening-results.jsonl contains every loan and issue.</p>' +
            table(['Source loan', 'Field', 'Category', 'Issue', 'Explanation'], errors[:200]) +
            '<h2>Operational readiness: not evaluated</h2><ul>' + ''.join(f'<li>{escape(p)}</li>' for p in PENDING) +
            '</ul><p>opening-candidates.jsonl contains private technical review records, not an import package. '
            'Edited fingerprints and evidence references are claims, not verified approvals. '
            'Keep this report with the original source preview.</p></html>')


def write_review_files(output, documents):
    """Write into a fresh parent report; its caller writes COMPLETE last."""
    summary, results = reconcile_documents(documents)
    for name, rows in (("opening-candidates.jsonl", documents), ("opening-results.jsonl", results)):
        with (output / name).open("x", encoding="utf-8", newline="\n") as target:
            total = 0
            for row in rows:
                line = encode(row) + "\n"
                if name == "opening-candidates.jsonl":
                    total += len(line.encode("utf-8"))
                    if len(line.encode("utf-8")) > MAX_LINE_BYTES or total > MAX_BYTES:
                        raise PortabilityError("Generated opening documents exceed the supported file limits.")
                target.write(line)
    (output / "opening-summary.json").write_text(encode(summary) + "\n", encoding="utf-8")
    (output / "opening-review.html").write_text(render_review(summary, results), encoding="utf-8")
    return summary


def write_review(output_dir, documents):
    output = Path(output_dir)
    try:
        output.mkdir(mode=0o700, parents=True, exist_ok=False)
    except OSError as exc:
        raise PortabilityError("Use a new output directory; existing reports are never overwritten.") from exc
    try:
        (output / ".gitignore").write_text("*\n", encoding="utf-8")
        summary = write_review_files(output, documents)
        (output / "COMPLETE").write_text(PROFILE + "\n", encoding="utf-8")
    except OSError as exc:
        raise PortabilityError("Could not finish the opening report; check for COMPLETE before using it.") from exc
    return summary
