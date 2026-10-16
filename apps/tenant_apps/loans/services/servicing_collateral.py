"""Source-local validation and exact item mapping for servicing bundle version 6."""
from copy import deepcopy
from types import SimpleNamespace

from .collateral_corrections import correction_facts, validate_correction_rows
from .recorded_history import _digest
from .servicing_bundle_contract import decode, require


def validate_corrections(document):
    tables = document["tables"]
    items = {row["id"]: SimpleNamespace(**decode("PawnCollateralItem", row), pk=row["id"]) for row in tables["PawnCollateralItem"]}
    for row in tables["LoanChangeLog"]:
        require((row["event_kind"] == "COLLATERAL_CORRECTED") == ("collateral_correction" in row["metadata"]),
            "Collateral facts require their explicit correction event.")
    for loan in tables["PawnLoan"]:
        logs = [SimpleNamespace(**decode("LoanChangeLog", row, profile=document["profile"]))
            for row in tables["LoanChangeLog"] if row["loan_id"] == loan["id"] and row["event_kind"] == "COLLATERAL_CORRECTED"]
        try:
            validate_correction_rows(logs, items)
        except ValueError as exc:
            require(False, str(exc))


def remap_correction(evidence, item_refs, source_workspace_id):
    result = deepcopy(evidence)
    require(evidence["item_id"] in item_refs, "Unmapped corrected collateral identity.")
    result["portable_source"] = dict(workspace_id=source_workspace_id, item_id=evidence["item_id"],
        request_sha256=evidence["request_sha256"])
    result["item_id"] = item_refs[evidence["item_id"]]
    result["request_sha256"] = _digest(correction_facts({key: result[key]
        for key in ("item_id", "after", "reference", "reason", "request_key")}))
    return result
