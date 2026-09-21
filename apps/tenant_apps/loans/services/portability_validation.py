"""Reporting vocabulary only. Categories never decide admission or permissions."""

MALFORMED_DATA = "MALFORMED_DATA"
MISSING_EVIDENCE = "MISSING_EVIDENCE"
HISTORICAL_INCONSISTENCY = "HISTORICAL_INCONSISTENCY"
OPERATIONAL_READINESS = "OPERATIONAL_READINESS"

CATEGORY_LABELS = {
    MALFORMED_DATA: "Malformed data",
    MISSING_EVIDENCE: "Missing evidence",
    HISTORICAL_INCONSISTENCY: "Historical inconsistency",
    OPERATIONAL_READINESS: "Operational readiness",
}


class PortabilityValidationError(ValueError):
    """Preserve existing exception text and ValueError compatibility."""

    def __init__(self, message, *, category=OPERATIONAL_READINESS,
                 code="ADMISSION_REJECTED", field="document"):
        super().__init__(message)
        self.issue = {"category": category, "code": code, "field": field,
                      "message": str(message), "severity": "ERROR", "rule_version": 1}

    @property
    def user_message(self):
        return f"{CATEGORY_LABELS[self.issue['category']]}: {self}"
