"""Readable retained closed-loan facts; no balance replay or identity remapping."""
from datetime import date


FIELD_LABELS = {
    "loan_amount": "Stored loan amount", "loanamount": "Recorded item amount",
    "interest": "Recorded interest", "interestrate": "Recorded interest rate",
    "interest_type": "Interest method (source)", "loan_type": "Loan type (source)",
    "loan_date": "Loan timestamp (source)", "loan_id": "Loan reference (source)",
    "lid": "Register ID (source)", "tenure": "Recorded tenure", "value": "Recorded value",
    "weight": "Source weight", "item_desc": "Inline collateral description",
    "itemdesc": "Item description", "itemtype": "Metal / item type", "purity": "Recorded purity",
    "quantity": "Quantity", "pic": "Original image reference", "item_id": "Product reference (source)",
    "payment_date": "Payment timestamp (source)", "payment_amount": "Recorded payment amount",
    "principal_payment": "Recorded principal payment", "interest_payment": "Recorded interest payment",
    "with_release": "Payment marked with release", "release_date": "Release timestamp (source)",
    "release_id": "Release number", "released_by_id": "Recipient reference (source)",
    "created_by_id": "Operator reference (source)", "customer_id": "Customer reference (source)",
    "series_id": "Series reference (source)", "license_id": "Licence reference (source)",
    "relatedas": "Relationship code (source)", "relatedto": "Related person's name",
    "shopname": "Business name", "propreitor": "Proprietor", "phonenumber": "Phone",
    "renewal_date": "Licence renewal date (source)", "is_active": "Active flag (source)",
    "is_repledged": "Repledged flag (source)", "created_at": "Created timestamp (source)",
    "updated_at": "Updated timestamp (source)", "max_limit": "Numbering limit (source)",
}


def _day(value):
    return date.fromisoformat(value) if value else None


def _fields(record):
    """Only scalar fields are promoted; arbitrary nested evidence stays in the export."""
    return [{"label": FIELD_LABELS.get(key, key.replace("_", " ").capitalize()), "value": value}
            for key, value in record["facts"].items()
            if value is None or type(value) in {str, int, bool}]


def historical_loan_summary(document):
    facts = document["facts"]
    return {"opened_on": _day(facts["opened_on"]), "closed_on": _day(facts["closed_on"])}


def historical_loan_details(document):
    """Internal presenter for an already-authorized, validated archive document.

    Raw fields are explicitly source values, never verified original principal,
    current balances, local people, or reconstructed settlement. A foreign or
    ambiguous source graph is not guessed into the main loan sections.
    """
    facts, source = document["facts"], document["source"]
    records = [row for row in document["source_records"]
               if isinstance(row.get("source"), dict) and isinstance(row.get("facts"), dict)
               and row["source"].get("source_system") == source["system"]]

    def matching(table, **values):
        return [row for row in records if row["source"].get("table") == table
                and row["source"].get("external_id") == f'{table}:{row["source"].get("id")}'
                and all(row["facts"].get(key) == value for key, value in values.items())]

    origins = [row for row in matching("girvi_loan")
               if row["source"]["external_id"] == source["loan_id"]]
    origin = origins[0] if len(origins) == 1 else None
    groups = {"loan": [], "borrower": [], "items": [], "payments": [], "releases": [], "setup": []}

    def display(rows):
        return [{"reference": row["source"]["external_id"], "fields": _fields(row)} for row in rows]

    stored_amount = None
    if origin:
        pk = origin["source"]["id"]
        stored_amount = origin["facts"].get("loan_amount")
        groups["loan"] = display([origin])
        for table, group in (("girvi_loanitem", "items"), ("girvi_loanpayment", "payments"),
                             ("girvi_release", "releases")):
            groups[group] = display(matching(table, loan_id=pk))
        for release, shown in zip(matching("girvi_release", loan_id=pk), groups["releases"]):
            recipients = [row for row in matching("contact_customer")
                          if row["source"]["id"] == release["facts"].get("released_by_id")]
            if len(recipients) == 1:
                shown["fields"].append({"label": "Recipient name (source snapshot)",
                                         "value": recipients[0]["facts"].get("name")})
        borrower = facts["borrower_reference"]
        if borrower and borrower["system"] == source["system"]:
            groups["borrower"] = display([row for row in matching("contact_customer")
                if row["source"]["id"] == origin["facts"].get("customer_id")
                and row["source"]["external_id"] == borrower["id"]])
        series = [row for row in matching("girvi_series")
                  if row["source"]["id"] == origin["facts"].get("series_id")]
        if len(series) == 1:
            licences = [row for row in matching("girvi_license")
                        if row["source"]["id"] == series[0]["facts"].get("license_id")]
            groups["setup"] = display(series + licences)

    return {**historical_loan_summary(document),
            "stored_amount": stored_amount, "collateral": facts["collateral"],
            "payments": None if facts["payments"] is None else [dict(row, date=_day(row["date"]))
                                                                 for row in facts["payments"]],
            "source_groups": groups}
