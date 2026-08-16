from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from djmoney.money import Money

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
class PortalLoanPaymentRow:
    payment_id: str
    payment_date: Any
    total_amount: Money


def _portal_loan_payment_row(event) -> PortalLoanPaymentRow:
    values = event.payload.get("values") or {}
    amount = sum(
        (_money_amount(values.get(key)) for key in ("principal", "interest", "fees")),
        Decimal("0"),
    )
    return PortalLoanPaymentRow(
        payment_id=f"PAWN-{event.pk}",
        payment_date=event.effective_date,
        total_amount=Money(amount, event.payload.get("currency") or "INR"),
    )


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


def _money_amount(value) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    amount = getattr(value, "amount", value)
    return Decimal(str(amount or "0"))


def get_portal_loans_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalLoanSummary:
    identity = _require_verified_identity(identity)
    from apps.tenant_apps.loans.selectors import get_party_pawn_loan_history_summary

    loan_history = get_party_pawn_loan_history_summary(identity.party, limit=limit)
    active_rows = tuple(loan_history.get("active_loans", ()))
    closed_rows = tuple(loan_history.get("closed_loans", ()))
    counts = loan_history.get("counts", {})
    return PortalLoanSummary(
        total_count=(counts.get("active_loans") or 0) + (counts.get("closed_loans") or 0),
        active_count=counts.get("active_loans") or 0,
        closed_count=counts.get("closed_loans") or 0,
        outstanding_amount=_money_amount(counts.get("active_outstanding")),
        items=(active_rows + closed_rows)[:limit],
    )


def get_portal_invoices_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalInvoiceSummary:
    identity = _require_verified_identity(identity)
    from apps.tenant_apps.dea.models import SalesInvoiceVoucher

    invoices = SalesInvoiceVoucher.objects.filter(party=identity.party).order_by(
        "-invoice_date", "-id"
    )
    rows = tuple(invoices[:limit])
    unpaid = invoices.filter(is_fully_paid=False)
    outstanding = sum((_money_amount(invoice.outstanding_balance) for invoice in unpaid), Decimal("0"))
    overdue_count = sum(1 for invoice in unpaid if getattr(invoice, "is_overdue", False))
    return PortalInvoiceSummary(
        total_count=invoices.count(),
        unpaid_count=unpaid.count(),
        overdue_count=overdue_count,
        outstanding_amount=outstanding,
        items=rows,
    )


def get_portal_payments_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalPaymentSummary:
    identity = _require_verified_identity(identity)
    from django.contrib.contenttypes.models import ContentType

    from apps.tenant_apps.dea.models import PaymentVoucher, SalesInvoiceVoucher
    from apps.tenant_apps.loans.domain import TransactionKind
    from apps.tenant_apps.loans.models import PawnLoanAccountingEvent

    source_filters = Q()
    invoice_ids = list(SalesInvoiceVoucher.objects.filter(party=identity.party).values_list("pk", flat=True))
    if invoice_ids:
        source_filters |= Q(
            source_content_type=ContentType.objects.get_for_model(SalesInvoiceVoucher),
            source_object_id__in=invoice_ids,
        )
    invoice_payments = (
        PaymentVoucher.objects.filter(source_filters).order_by("-payment_date", "-id")
        if source_filters
        else PaymentVoucher.objects.none()
    )
    repayment_events = PawnLoanAccountingEvent.objects.filter(
        loan__borrower=identity.party,
        event_kind=TransactionKind.REPAYMENT.value,
        reversed_by_event__isnull=True,
    ).order_by("-effective_date", "-id")
    loan_payment_rows = []
    for event in repayment_events:
        loan_payment_rows.append(_portal_loan_payment_row(event))
    combined_rows = list(invoice_payments) + loan_payment_rows
    combined_rows.sort(
        key=lambda row: (getattr(row, "payment_date", None), getattr(row, "pk", 0) or 0),
        reverse=True,
    )
    return PortalPaymentSummary(
        total_count=invoice_payments.count() + len(loan_payment_rows),
        total_amount=(
            sum((_money_amount(payment.total_amount) for payment in invoice_payments), Decimal("0"))
            + sum((_money_amount(payment.total_amount) for payment in loan_payment_rows), Decimal("0"))
        ),
        items=tuple(combined_rows[:limit]),
    )


def get_portal_documents_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalDocumentSummary:
    identity = _require_verified_identity(identity)
    documents = identity.party.documents.all().order_by("document_type", "title", "-created_at")
    return PortalDocumentSummary(
        total_count=documents.count(),
        items=tuple(documents[:limit]),
    )


def get_portal_statements_summary(
    identity: PortalIdentity, *, limit: int = 20
) -> PortalStatementSummary:
    identity = _require_verified_identity(identity)
    loans = get_portal_loans_summary(identity, limit=limit)
    invoices = get_portal_invoices_summary(identity, limit=limit)
    payments = get_portal_payments_summary(identity, limit=limit)
    rows = (
        {"label": "Loan outstanding", "amount": loans.outstanding_amount},
        {"label": "Invoice outstanding", "amount": invoices.outstanding_amount},
        {"label": "Payments recorded", "amount": payments.total_amount},
    )
    closing = loans.outstanding_amount + invoices.outstanding_amount - payments.total_amount
    return PortalStatementSummary(
        period_label="Current",
        opening_balance=Decimal("0"),
        closing_balance=closing,
        items=rows,
    )


def get_portal_dashboard_summary(identity: PortalIdentity) -> PortalDashboardSummary:
    identity = _require_verified_identity(identity)
    return PortalDashboardSummary(
        loans=get_portal_loans_summary(identity, limit=5),
        invoices=get_portal_invoices_summary(identity, limit=5),
        payments=get_portal_payments_summary(identity, limit=5),
        documents=get_portal_documents_summary(identity, limit=5),
        statements=get_portal_statements_summary(identity, limit=5),
    )
