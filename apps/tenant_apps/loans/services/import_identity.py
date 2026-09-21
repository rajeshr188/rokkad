"""Shared financial-origin identity for complete history and legacy openings."""
import re
from uuid import UUID

from .history_contract import HistoryError


def source_binding_id(namespace, source_id, borrower_source_system):
    """Scope schema-local legacy keys; ordinary portable identities stay unchanged."""
    prefix = f"legacy:{UUID(str(namespace)).hex}:"
    if borrower_source_system.startswith("legacy:"):
        if not borrower_source_system.startswith(prefix):
            raise HistoryError("Legacy source namespace and borrower scope must agree.")
        schema = borrower_source_system[len(prefix):]
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema) or schema == "public":
            raise HistoryError("Select a supported legacy source schema.")
        source_id = f"{schema}:{source_id}"
    if not isinstance(source_id, str) or not source_id.strip() or len(source_id) > 120:
        raise HistoryError("The scoped source loan ID must fit 120 characters.")
    return source_id


def find_source_origin(*, workspace_id, namespace, source_id, borrower_source_system):
    """Also recognize pre-scoping complete imports without editing immutable rows."""
    from apps.tenant_apps.loans.models import HistoricalLoanImport
    scoped = source_binding_id(namespace, source_id, borrower_source_system)
    matches = []
    for origin in HistoricalLoanImport.objects.select_related("loan").filter(
            workspace_id=workspace_id, source_namespace=namespace, source_id__in={scoped, source_id}):
        old_loan = origin.document.get("loan", {})
        if origin.source_id == scoped or (
                old_loan.get("id") == source_id and
                old_loan.get("borrower", {}).get("source_system") == borrower_source_system):
            matches.append(origin)
    if len(matches) > 1:
        raise HistoryError("Multiple accepted financial origins require investigation before import.")
    return matches[0] if matches else None
