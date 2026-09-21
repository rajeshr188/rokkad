"""Versioned, source-only profiles and reviewed corrections for Linode archives."""
from copy import deepcopy
from dataclasses import dataclass

from .parsers import PortabilityError


@dataclass(frozen=True)
class LegacySourceProfile:
    key: str
    schema: str
    display_name: str


PROFILES = {
    "linode-jcl/1": LegacySourceProfile("linode-jcl/1", "jcl", "JCL"),
    "linode-jsk/1": LegacySourceProfile("linode-jsk/1", "jsk", "JSK"),
    "linode-lakshmi/1": LegacySourceProfile("linode-lakshmi/1", "lakshmipawnbroker", "Lakshmi Pawn Broker"),
}

# Corrections are source facts with explicit owner decisions. They are never written
# back to the archive and only apply when the source identity and original value match.
CORRECTION_LEDGER_VERSION = "linode-production-corrections/1"
CORRECTIONS = (
    {
        "profile": "linode-jcl/1",
        "table": "girvi_loan",
        "source_id": "29887",
        "field": "loan_date",
        "original": "2026-12-16 09:47:00+00",
        "corrected": "2025-12-16 09:47:00+00",
        "decision": "owner-approved-2026-09-21:R09911-date",
    },
)


def get_profile(key):
    try:
        return PROFILES[key]
    except KeyError as exc:
        raise PortabilityError("Select a supported versioned Linode source profile.") from exc


def apply_corrections(tables, *, profile_key):
    """Return effective source tables and immutable evidence without mutating input."""
    profile = get_profile(profile_key)
    effective = deepcopy(tables)
    evidence = {}
    for correction in CORRECTIONS:
        if correction["profile"] != profile.key:
            continue
        try:
            row = effective[correction["table"]][correction["source_id"]]
        except KeyError as exc:
            raise PortabilityError("A reviewed correction does not match this source archive.") from exc
        if row.get(correction["field"]) != correction["original"]:
            raise PortabilityError("A reviewed correction's original value does not match this source archive.")
        row[correction["field"]] = correction["corrected"]
        evidence[correction["table"], correction["source_id"]] = {
            "ledger": CORRECTION_LEDGER_VERSION,
            **correction,
        }
    return effective, evidence
