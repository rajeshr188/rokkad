"""Opening review document checks only; no ORM queries or financial events."""
import calendar
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
import re
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .portability_validation import (
    MALFORMED_DATA, MISSING_EVIDENCE, HISTORICAL_INCONSISTENCY, OPERATIONAL_READINESS,
)

PROFILE = "loan-opening-review/1"
COLLECTION_PROFILE = "loan-opening-review/2"
MAX_ITEMS = 20
MAX_OBLIGATIONS = 240
DECIMAL = re.compile(r"(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?\Z")
HASH = re.compile(r"[0-9a-f]{64}\Z")
PENDING = ["Destination authorization and database reference checks",
           "Source evidence and selected-loan approval",
           "Reviewed calculation rule implementation and servicing acceptance",
           "Explicit owner-authorized opening commit (v2 only)"]


# Explicit rule families: an unsupported contract is not evidence of false history.
ISSUE_CATEGORIES = {}
for category, codes in (
    (MALFORMED_DATA, "SHAPE REQUIRED_TEXT AMOUNT_REQUIRED AMOUNT_RANGE INTEGER_REQUIRED DATE_REQUIRED ROWS_REQUIRED SOURCE_SCOPE SOURCE_NAMESPACE SOURCE_HASH SOURCE_DATE TIMEZONE PARTIAL_FRACTION PARTIAL_PARAMETERS WEIGHT_RANGE PURITY_RANGE RATE_RANGE SOURCE_ITEMS PERIOD_RANGE COLLECTION_RANGE"),
    (MISSING_EVIDENCE, "REQUIRED UPFRONT_COVERAGE"),
    (OPERATIONAL_READINESS, "PROFILE RULE_REQUIRED SOURCE_NOT_SELECTED PRINCIPAL_INCREASE COLLECTION_RULE COLLECTION_PRINCIPAL_CHANGED BILLING_ANCHOR_CHANGED"),
    (HISTORICAL_INCONSISTENCY, "SOURCE_ERRORS FUTURE_CUTOVER BORROWER_REFERENCE ORIGINAL_DATE_CHANGED MATURITY_ORDER CUTOVER_ORDER WEIGHT_ORDER VALUATION_AFTER_CUTOVER DUPLICATE_ITEM ITEM_SET_MISMATCH ITEM_PRINCIPAL_MISMATCH DUPLICATE_OBLIGATION OBLIGATION_DATE PRINCIPAL_REAGED OBLIGATION_INTEREST OBLIGATION_BALANCE_MISMATCH PERIOD_RESET PERIOD_CUTOVER UNPAID_CARRY CARRY_BALANCE UNSTARTED_RECOGNITION BASIS_ITEM ORIGINAL_BASIS PERIOD_BASIS BASIS_ITEM_SET PERIOD_INTEREST_MISMATCH CARRY_OVER_COVERED COLLECTION_CUTOVER COLLECTION_BALANCE COLLECTION_MONTHS COLLECTION_RECOGNITION"),
):
    ISSUE_CATEGORIES.update(dict.fromkeys(codes.split(), category))


def _missing_category(path):
    return OPERATIONAL_READINESS if path == "mapping" or path.startswith("mapping.") else MISSING_EVIDENCE


def readiness_checks():
    # The offline validator cannot evaluate these. Do not add them to document errors.
    codes = ("DESTINATION_ACCESS", "SOURCE_APPROVAL", "SERVICING_ACCEPTANCE", "OPENING_COMMIT")
    return [{"code": code, "category": OPERATIONAL_READINESS, "status": "NOT_EVALUATED",
             "message": message, "rule_version": 1} for code, message in zip(codes, PENDING)]


class Review:
    def __init__(self):
        self.issues = []

    def issue(self, code, field, message, *, category=None):
        self.issues.append({"code": code, "field": field, "message": message,
                            "category": category or ISSUE_CATEGORIES[code],
                            "severity": "ERROR", "rule_version": 1,
                            "before": None, "after": None})

    def object(self, value, fields, path):
        if value is None:
            self.issue("REQUIRED", path, "Supply this review group from reviewed evidence.", category=_missing_category(path))
            return None
        if type(value) is not dict or set(value) != set(fields.split()):
            self.issue("SHAPE", path, "Missing or unsupported document fields.")
            return None
        return value

    def text(self, value, path, maximum=255):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum or any(ord(c) < 32 or ord(c) == 127 for c in value):
            self.issue("REQUIRED_TEXT", path, "Supply bounded nonempty text without control characters.", category=_missing_category(path) if value is None or value == "" else None)
            return None
        return value

    def amount(self, value, path, positive=False, places=2):
        if not isinstance(value, str) or not DECIMAL.fullmatch(value):
            self.issue("AMOUNT_REQUIRED", path, "Supply a finite nonnegative decimal string; unknown is not zero.", category=_missing_category(path) if value is None or value == "" else None)
            return None
        result = Decimal(value)
        if (positive and result <= 0) or result != result.quantize(Decimal(1).scaleb(-places)):
            self.issue("AMOUNT_RANGE", path, "The amount is outside the required positivity or precision bounds.")
            return None
        return result

    def integer(self, value, path, minimum=1, maximum=2147483647):
        if type(value) is not int or not minimum <= value <= maximum:
            self.issue("INTEGER_REQUIRED", path, "Supply an integer within the supported bounds.", category=_missing_category(path) if value is None or value == "" else None)
            return None
        return value

    def day(self, value, path):
        try:
            result = date.fromisoformat(value)
            if result.isoformat() != value:
                raise ValueError()
            return result
        except (ValueError, TypeError):
            self.issue("DATE_REQUIRED", path, "Supply an ISO calendar date.", category=_missing_category(path) if value is None or value == "" else None)

    def choice(self, value, allowed, path):
        if not isinstance(value, str) or value not in allowed:
            self.issue("RULE_REQUIRED", path, "Select an explicit supported review value.", category=_missing_category(path) if value is None or value == "" else None)
            return None
        return value

    def rows(self, value, path, maximum):
        if type(value) is not list or not 1 <= len(value) <= maximum:
            self.issue("ROWS_REQUIRED", path, f"Supply 1-{maximum} reviewed rows.", category=_missing_category(path) if value is None or value == [] else None)
            return []
        return value


def _anniversary(anchor, months, rule):
    if rule == "CLAMPED_CONTIGUOUS":
        result = anchor
        for _ in range(months):
            result = _anniversary(result, 1, "ORIGINAL_ANNIVERSARY")
        return result
    index = anchor.year * 12 + anchor.month - 1 + months
    year, month = divmod(index, 12)
    return date(year, month + 1, min(anchor.day, calendar.monthrange(year, month + 1)[1]))


def validate_opening(document, *, today=None):
    """Reconcile supplied review facts, never certify source truth or import readiness."""
    check = Review()
    result = {"profile": PROFILE, "document_reconciled": False, "import_ready": False,
              "issues": check.issues, "reconciliation": {}, "pending": list(PENDING),
              "readiness_checks": readiness_checks()}
    doc = check.object(document, "profile source cutover mapping balances terms collateral obligations continuation review_reference", "document")
    if doc is None:
        return result
    collection_profile = doc["profile"] == COLLECTION_PROFILE
    if collection_profile:
        result["profile"] = COLLECTION_PROFILE
    if doc["profile"] not in (PROFILE, COLLECTION_PROFILE):
        check.issue("PROFILE", "profile", "Only an opening review document is supported.")
    check.text(doc["review_reference"], "review_reference")
    source = check.object(doc["source"], "namespace schema loan_id number loan_timestamp borrower_id item_ids archive_sha256 selection_sha256 loan_sha256 state excluded errors", "source")
    original_timestamp, namespace = None, None
    if source:
        for name in ("schema", "loan_id", "number", "borrower_id"):
            check.text(source[name], f"source.{name}")
        if not isinstance(source["schema"], str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", source["schema"]) or source["schema"] == "public":
            check.issue("SOURCE_SCOPE", "source.schema", "Select a supported business source schema.")
        try:
            namespace = UUID(str(source["namespace"]))
            if namespace.int == 0:
                raise ValueError()
        except (ValueError, TypeError):
            check.issue("SOURCE_NAMESPACE", "source.namespace", "Supply a non-nil source namespace UUID.")
        for field in ("archive_sha256", "selection_sha256", "loan_sha256"):
            if not isinstance(source[field], str) or not HASH.fullmatch(source[field]):
                check.issue("SOURCE_HASH", f"source.{field}", "Supply the source evidence fingerprint.", category=MISSING_EVIDENCE if source[field] is None or source[field] == "" else None)
        if source["state"] != "UNRELEASED" or source["excluded"] is not False:
            check.issue("SOURCE_NOT_SELECTED", "source", "Only a retained unreleased loan can be reviewed as an opening.")
        if type(source["errors"]) is not list or source["errors"]:
            check.issue("SOURCE_ERRORS", "source.errors", "Resolve source errors before opening reconciliation.")
        try:
            original_timestamp = datetime.fromisoformat(source["loan_timestamp"])
            if original_timestamp.utcoffset() is None:
                raise ValueError()
        except (ValueError, TypeError):
            check.issue("SOURCE_DATE", "source.loan_timestamp", "Supply the original timezone-aware loan timestamp.")
            original_timestamp = None
    cutover = check.object(doc["cutover"], "date timezone evidence_reference", "cutover")
    cutoff, zone = None, None
    if cutover:
        cutoff = check.day(cutover["date"], "cutover.date")
        check.text(cutover["evidence_reference"], "cutover.evidence_reference")
        try:
            zone = ZoneInfo(cutover["timezone"])
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            check.issue("TIMEZONE", "cutover.timezone", "Supply the agreed business timezone.")
        if cutoff and zone and cutoff > (today or datetime.now(zone).date()):
            check.issue("FUTURE_CUTOVER", "cutover.date", "Cutover cannot be in the future.")
    mapping = check.object(doc["mapping"], "workspace_id borrower_id borrower_source_system borrower_external_id licence_revision_id series_id product_version_id evidence_reference", "mapping")
    if mapping:
        for field in ("workspace_id", "borrower_id", "licence_revision_id", "series_id", "product_version_id"):
            check.integer(mapping[field], f"mapping.{field}")
        for field in ("borrower_source_system", "borrower_external_id", "evidence_reference"):
            check.text(mapping[field], f"mapping.{field}")
        if source and namespace:
            expected = f"legacy:{namespace.hex}:{source['schema']}"
            if mapping["borrower_source_system"] != expected or mapping["borrower_external_id"] != source["borrower_id"]:
                check.issue("BORROWER_REFERENCE", "mapping", "Borrower mapping must preserve the exact source tenant and customer reference.")
    balances = check.object(doc["balances"], "principal interest fees evidence_reference", "balances")
    amounts = {}
    if balances:
        for field in ("principal", "interest", "fees"):
            amounts[field] = check.amount(balances[field], f"balances.{field}", positive=field == "principal")
        check.text(balances["evidence_reference"], "balances.evidence_reference")
    terms = check.object(doc["terms"], "original_date maturity_date grace_days billing_anchor rule_id period_rule interest_basis partial_rule partial_cutoff_days partial_lower_fraction rounding_scope rounding_mode interest_quantum evidence_reference", "terms")
    original, maturity, anchor, period_rule, basis_rule, rounding_scope, rounding_mode, quantum = (None,) * 8
    if terms:
        original = check.day(terms["original_date"], "terms.original_date")
        maturity = check.day(terms["maturity_date"], "terms.maturity_date")
        anchor = check.day(terms["billing_anchor"], "terms.billing_anchor")
        check.integer(terms["grace_days"], "terms.grace_days", 0, 366)
        check.text(terms["rule_id"], "terms.rule_id", 120)
        check.text(terms["evidence_reference"], "terms.evidence_reference")
        period_rule = check.choice(terms["period_rule"], {"ORIGINAL_ANNIVERSARY", "CLAMPED_CONTIGUOUS"}, "terms.period_rule")
        basis_rule = check.choice(terms["interest_basis"], {"ORIGINAL_PRINCIPAL", "OUTSTANDING_AT_PERIOD_START"}, "terms.interest_basis")
        partial = check.choice(terms["partial_rule"], {"INCLUSIVE_UPFRONT"} if collection_profile else {"COMPLETED_ONLY", "FULL_MONTH", "SLAB"}, "terms.partial_rule")
        if partial == "SLAB":
            check.integer(terms["partial_cutoff_days"], "terms.partial_cutoff_days", 1, 28)
            fraction = check.amount(terms["partial_lower_fraction"], "terms.partial_lower_fraction", True, 6)
            if fraction is not None and fraction >= 1:
                check.issue("PARTIAL_FRACTION", "terms.partial_lower_fraction", "The lower slab fraction must be below one.")
        elif terms["partial_cutoff_days"] is not None or terms["partial_lower_fraction"] is not None:
            check.issue("PARTIAL_PARAMETERS", "terms", "Slab parameters must be null for a non-slab rule.")
        rounding_scope = check.choice(terms["rounding_scope"], {"PER_ITEM", "AGGREGATE"}, "terms.rounding_scope")
        rounding_mode = check.choice(terms["rounding_mode"], {"HALF_UP", "HALF_EVEN"}, "terms.rounding_mode")
        q = check.choice(terms["interest_quantum"], {"1", "0.01"}, "terms.interest_quantum")
        quantum = Decimal(q) if q else None
        if original and original_timestamp and zone:
            try:
                if original != original_timestamp.astimezone(zone).date():
                    check.issue("ORIGINAL_DATE_CHANGED", "terms.original_date", "Preserve the original loan date in the selected business timezone.")
            except (ValueError, OverflowError):
                check.issue("SOURCE_DATE", "source.loan_timestamp", "The business date is outside supported calendar bounds.")
        if original and anchor and original != anchor:
            check.issue("BILLING_ANCHOR_CHANGED", "terms.billing_anchor", "This review slice preserves the original loan billing anchor.")
        if original and maturity and maturity < original:
            check.issue("MATURITY_ORDER", "terms.maturity_date", "Maturity cannot precede the original loan date.")
        if original and cutoff and original > cutoff:
            check.issue("CUTOVER_ORDER", "cutover.date", "Cutover cannot precede the original loan date.")
    items = {}
    for n, raw in enumerate(check.rows(doc["collateral"], "collateral", MAX_ITEMS)):
        path = f"collateral[{n}]"
        item = check.object(raw, "id description quantity metal gross_weight net_weight purity original_principal remaining_principal monthly_rate weight_reference custody_reference valuation", path)
        if item is None:
            continue
        key = check.text(item["id"], path + ".id")
        for field in ("description", "weight_reference", "custody_reference"):
            check.text(item[field], path + "." + field)
        check.integer(item["quantity"], path + ".quantity", 1, 10000)
        metals = {"GOLD", "SILVER", "OTHER"}
        if collection_profile:
            metals.add("BRONZE")
        check.choice(item["metal"], metals, path + ".metal")
        # v2 can preserve net-only evidence; null never means zero or net weight.
        # The weight reference, positive net weight and separate purity remain required.
        gross = (None if collection_profile and item["gross_weight"] is None else
                 check.amount(item["gross_weight"], path + ".gross_weight", True, 4))
        net = check.amount(item["net_weight"], path + ".net_weight", True, 4)
        purity = check.amount(item["purity"], path + ".purity", True, 4)
        if gross is not None and net is not None and gross < net:
            check.issue("WEIGHT_ORDER", path, "Gross weight cannot be below net weight.")
        if any(weight is not None and weight >= Decimal("10000000000") for weight in (gross, net)):
            check.issue("WEIGHT_RANGE", path, "Weight exceeds the supported collateral model precision.")
        if purity is not None and purity > 100:
            check.issue("PURITY_RANGE", path + ".purity", "Purity cannot exceed 100 percent.")
        start = check.amount(item["original_principal"], path + ".original_principal", True)
        remaining = check.amount(item["remaining_principal"], path + ".remaining_principal")
        rate = check.amount(item["monthly_rate"], path + ".monthly_rate", places=6)
        if rate is not None and rate > 100:
            check.issue("RATE_RANGE", path + ".monthly_rate", "The rate exceeds the supported collateral model limit.")
        if start is not None and remaining is not None and remaining > start:
            check.issue("PRINCIPAL_INCREASE", path, "Capitalized or increased principal requires a separate review contract.")
        unverified = collection_profile and isinstance(item["valuation"], dict) and item["valuation"].get("status") == "UNVERIFIED"
        appraisal = check.object(item["valuation"], "status source_amount source_date evidence_reference" if unverified else "amount date evidence_reference", path + ".valuation")
        if appraisal and unverified:
            check.text(appraisal["evidence_reference"], path + ".valuation.evidence_reference")
            if appraisal["source_amount"] is not None:
                check.amount(appraisal["source_amount"], path + ".valuation.source_amount", True)
            if appraisal["source_date"] is not None:
                source_date = check.day(appraisal["source_date"], path + ".valuation.source_date")
                if source_date and cutoff and source_date > cutoff:
                    check.issue("VALUATION_AFTER_CUTOVER", path + ".valuation.source_date", "Source valuation cannot postdate the opening.")
            appraisal = None
        if appraisal:
            check.amount(appraisal["amount"], path + ".valuation.amount", True)
            valued_on = check.day(appraisal["date"], path + ".valuation.date")
            check.text(appraisal["evidence_reference"], path + ".valuation.evidence_reference")
            if valued_on and cutoff and valued_on > cutoff:
                check.issue("VALUATION_AFTER_CUTOVER", path + ".valuation.date", "Valuation evidence cannot postdate this opening.")
        if key:
            if key in items:
                check.issue("DUPLICATE_ITEM", path + ".id", "Collateral source IDs must be unique.")
            items[key] = {"original": start, "remaining": remaining, "rate": rate}
    if source:
        expected = source["item_ids"]
        if type(expected) is not list or not 1 <= len(expected) <= MAX_ITEMS or any(not isinstance(k, str) for k in expected):
            check.issue("SOURCE_ITEMS", "source.item_ids", "Supply the complete bounded source item identity list.")
        elif len(expected) != len(set(expected)) or set(expected) != set(items):
            check.issue("ITEM_SET_MISMATCH", "collateral", "Keep every source collateral item exactly once.")
    principal_parts = [i["remaining"] for i in items.values()]
    if principal_parts and all(p is not None for p in principal_parts) and amounts.get("principal") is not None:
        if sum(principal_parts) != amounts["principal"]:
            check.issue("ITEM_PRINCIPAL_MISMATCH", "collateral", "Item remaining principal must equal the opening principal.")
    principal_due, recognized_due, obligation_ids = [], [], set()
    for n, raw in enumerate(check.rows(doc["obligations"], "obligations", MAX_OBLIGATIONS)):
        path = f"obligations[{n}]"
        obligation = check.object(raw, "id due principal interest recognized_interest evidence_reference", path)
        if not obligation:
            continue
        key = check.text(obligation["id"], path + ".id")
        if key in obligation_ids:
            check.issue("DUPLICATE_OBLIGATION", path, "Obligation IDs must be unique.")
        obligation_ids.add(key)
        due = check.day(obligation["due"], path + ".due")
        p = check.amount(obligation["principal"], path + ".principal")
        interest = check.amount(obligation["interest"], path + ".interest")
        recognized = check.amount(obligation["recognized_interest"], path + ".recognized_interest")
        check.text(obligation["evidence_reference"], path + ".evidence_reference")
        principal_due.append(p)
        recognized_due.append(recognized)
        if due and original and due < original:
            check.issue("OBLIGATION_DATE", path + ".due", "An obligation cannot precede origination.")
        if due and maturity and p and due > maturity:
            check.issue("PRINCIPAL_REAGED", path + ".due", "Remaining principal cannot be moved beyond the original maturity.")
        if recognized is not None and interest is not None and recognized > interest:
            check.issue("OBLIGATION_INTEREST", path, "Recognized unpaid interest cannot exceed total obligation interest.")
    for parts, field in ((principal_due, "principal"), (recognized_due, "interest")):
        if parts and all(p is not None for p in parts) and amounts.get(field) is not None and sum(parts) != amounts[field]:
            check.issue("OBLIGATION_BALANCE_MISMATCH", "obligations", f"Remaining {field} obligations do not reconcile with the opening.")
    if collection_profile:
        _validate_collection_checkpoint(check, doc, items, amounts, original, cutoff, result)
        carry = None
    else:
        carry = check.object(doc["continuation"], "period_number period_start period_end bases recognized_interest recognized_unpaid_interest advance_covered_interest expected_period_interest evidence_reference", "continuation")
    if carry:
        ordinal = check.integer(carry["period_number"], "continuation.period_number", 1, 1200)
        start = check.day(carry["period_start"], "continuation.period_start")
        end = check.day(carry["period_end"], "continuation.period_end")
        check.text(carry["evidence_reference"], "continuation.evidence_reference")
        if ordinal and anchor and period_rule and start and end:
            try:
                if (start, end) != (_anniversary(anchor, ordinal - 1, period_rule), _anniversary(anchor, ordinal, period_rule) - timedelta(days=1)):
                    check.issue("PERIOD_RESET", "continuation", "Preserve the original period boundaries and anniversary rule.")
            except (ValueError, OverflowError):
                check.issue("PERIOD_RANGE", "continuation", "The period is outside supported calendar bounds.")
        if start and end and cutoff and not (-1 <= (cutoff - start).days and cutoff < end and start <= end):
            check.issue("PERIOD_CUTOVER", "continuation", "Supply the period containing cutover, or the next period starting immediately after it.")
        recognized = check.amount(carry["recognized_interest"], "continuation.recognized_interest")
        unpaid = check.amount(carry["recognized_unpaid_interest"], "continuation.recognized_unpaid_interest")
        advance = check.amount(carry["advance_covered_interest"], "continuation.advance_covered_interest")
        expected_charge = check.amount(carry["expected_period_interest"], "continuation.expected_period_interest")
        if unpaid is not None and recognized is not None and unpaid > recognized:
            check.issue("UNPAID_CARRY", "continuation", "Unpaid carried interest cannot exceed recognized carried interest.")
        if unpaid is not None and amounts.get("interest") is not None and unpaid > amounts["interest"]:
            check.issue("CARRY_BALANCE", "continuation", "Unpaid carried interest must be included in opening interest.")
        if start and cutoff and start > cutoff and ((recognized or 0) != 0 or (unpaid or 0) != 0):
            check.issue("UNSTARTED_RECOGNITION", "continuation", "An unstarted period cannot carry recognized interest in this slice.")
        seen, charges = set(), []
        for n, raw in enumerate(check.rows(carry["bases"], "continuation.bases", MAX_ITEMS)):
            path = f"continuation.bases[{n}]"
            line = check.object(raw, "item_id principal_base", path)
            if not line:
                continue
            key = check.text(line["item_id"], path + ".item_id")
            base = check.amount(line["principal_base"], path + ".principal_base")
            if key is None or key not in items or key in seen:
                check.issue("BASIS_ITEM", path, "Each current item must have exactly one period basis.")
                continue
            seen.add(key)
            item = items[key]
            if basis_rule == "ORIGINAL_PRINCIPAL" and base is not None and item["original"] is not None and base != item["original"]:
                check.issue("ORIGINAL_BASIS", path, "Preserve original principal as the agreed interest basis.")
            if basis_rule == "OUTSTANDING_AT_PERIOD_START" and base is not None and item["remaining"] is not None:
                if base < item["remaining"] or (start and cutoff and start > cutoff and base != item["remaining"]):
                    check.issue("PERIOD_BASIS", path, "The period basis disagrees with the retained principal and cutover boundary.")
                if item["original"] is not None and base > item["original"]:
                    check.issue("PRINCIPAL_INCREASE", path, "A basis above original principal requires a separate review contract.")
            if base is not None and item["rate"] is not None:
                charges.append(base * item["rate"] / 100)
        if seen != set(items):
            check.issue("BASIS_ITEM_SET", "continuation.bases", "Supply the complete set of item period bases.")
        if len(charges) == len(items) and items and quantum and rounding_scope and rounding_mode:
            mode = ROUND_HALF_UP if rounding_mode == "HALF_UP" else ROUND_HALF_EVEN
            full = sum(v.quantize(quantum, rounding=mode) for v in charges) if rounding_scope == "PER_ITEM" else sum(charges).quantize(quantum, rounding=mode)
            result["reconciliation"]["calculated_full_period_interest"] = str(full)
            if expected_charge is not None and full != expected_charge:
                check.issue("PERIOD_INTEREST_MISMATCH", "continuation.expected_period_interest", "The expected full-period charge differs from supplied bases, rates and rounding.")
            if recognized is not None and advance is not None:
                remainder = full - recognized - advance
                if remainder < 0:
                    check.issue("CARRY_OVER_COVERED", "continuation", "Recognized interest plus separate advance coverage exceeds the period charge.")
                else:
                    result["reconciliation"]["additional_full_period_interest"] = str(remainder)
    if amounts and all(value is not None for value in amounts.values()):
        result["reconciliation"]["opening_total"] = str(sum(amounts.values()))
    result["document_reconciled"] = not check.issues
    return result


def _validate_collection_checkpoint(check, doc, items, amounts, original, cutoff, result):
    from .legacy_interest import AGGREGATE_RULE, aggregate_collection_interest

    terms = doc["terms"]
    required = {"rule_id": AGGREGATE_RULE, "period_rule": "ORIGINAL_ANNIVERSARY",
                "interest_basis": "ORIGINAL_PRINCIPAL", "partial_rule": "INCLUSIVE_UPFRONT",
                "rounding_scope": "AGGREGATE", "rounding_mode": "HALF_EVEN", "interest_quantum": "1"}
    if not isinstance(terms, dict) or any(terms.get(k) != v for k, v in required.items()):
        check.issue("COLLECTION_RULE", "terms", "Version 2 requires the named inclusive upfront aggregate rule without overrides.")
    carry = check.object(doc["continuation"], "covered_through additional_months recognized_interest recognized_unpaid_interest first_month_paid evidence_reference", "continuation")
    if not carry:
        return
    check.text(carry["evidence_reference"], "continuation.evidence_reference")
    through = check.day(carry["covered_through"], "continuation.covered_through")
    months = check.integer(carry["additional_months"], "continuation.additional_months", 0, 1200)
    recognized = check.amount(carry["recognized_interest"], "continuation.recognized_interest")
    unpaid = check.amount(carry["recognized_unpaid_interest"], "continuation.recognized_unpaid_interest")
    if carry["first_month_paid"] is not True:
        check.issue("UPFRONT_COVERAGE", "continuation.first_month_paid", "Require reviewed evidence that the first month is already paid.")
    if through and cutoff and through != cutoff:
        check.issue("COLLECTION_CUTOVER", "continuation.covered_through", "Coverage must end at the exact business cutover.")
    if unpaid is not None and (unpaid != amounts.get("interest") or (recognized is not None and unpaid > recognized)):
        check.issue("COLLECTION_BALANCE", "continuation", "Opening unpaid interest must match the checkpoint and cannot exceed recognized interest.")
    for key, item in items.items():
        if item["remaining"] != item["original"]:
            check.issue("COLLECTION_PRINCIPAL_CHANGED", "collateral", "Reduced principal requires a separately reviewed continuation rule.")
    if original and cutoff and items and all(i["original"] is not None and i["rate"] is not None for i in items.values()):
        monthly = sum(i["original"] * i["rate"] / 100 for i in items.values())
        try:
            calculation = aggregate_collection_interest(original, cutoff, monthly)
        except ValueError:
            check.issue("COLLECTION_RANGE", "continuation", "Collection dates or amounts exceed the supported bounds.")
            return
        result["reconciliation"]["collection_checkpoint"] = calculation
        if months is not None and months != calculation["additional_months"]:
            check.issue("COLLECTION_MONTHS", "continuation.additional_months", "Preserve the inclusive original anniversary count.")
        if recognized is not None and recognized != Decimal(calculation["additional_interest"]):
            check.issue("COLLECTION_RECOGNITION", "continuation.recognized_interest", "Recognized baseline must include every charge through cutover, rounded once in aggregate.")
