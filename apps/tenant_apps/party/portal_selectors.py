from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied

from apps.tenant_apps.party.portal_access import PortalIdentity, validate_portal_identity


class PortalSelectorNotImplemented(PermissionDenied):
    """Raised until a portal selector has a verified tenant data source."""


@dataclass(frozen=True)
class PortalLoanSummary:
    total_count: int = 0
    active_count: int = 0
    closed_count: int = 0
    outstanding_amount: Decimal = Decimal("0")
    items: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortalInvoiceSummary:
    total_count: int = 0
    unpaid_count: int = 0
    overdue_count: int = 0
    outstanding_amount: Decimal = Decimal("0")
    items: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortalPaymentSummary:
    total_count: int = 0
    total_amount: Decimal = Decimal("0")
    items: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortalDocumentSummary:
    total_count: int = 0
    items: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortalStatementSummary:
    period_label: str = ""
    opening_balance: Decimal = Decimal("0")
    closing_balance: Decimal = Decimal("0")
    items: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PortalDashboardSummary:
    loans: PortalLoanSummary
    invoices: PortalInvoiceSummary
    payments: PortalPaymentSummary
    documents: PortalDocumentSummary
    statements: PortalStatementSummary


def _require_verified_identity(identity: PortalIdentity) -> PortalIdentity:
    return validate_portal_identity(identity)


def _raise_missing_selector(selector_name: str):
    raise PortalSelectorNotImplemented(
        f"{selector_name} requires a verified PartyPortalAccess-backed selector "
        "before live portal routes are exposed."
    )


def get_portal_loans_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalLoanSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_loans_summary")


def get_portal_invoices_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalInvoiceSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_invoices_summary")


def get_portal_payments_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalPaymentSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_payments_summary")


def get_portal_documents_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalDocumentSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_documents_summary")


def get_portal_statements_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalStatementSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_statements_summary")


def get_portal_dashboard_summary(identity: PortalIdentity) -> PortalDashboardSummary:
    _require_verified_identity(identity)
    _raise_missing_selector("get_portal_dashboard_summary")
