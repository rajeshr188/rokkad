"""Read-only workspace setup checklist composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.apps import apps
from django.db import DatabaseError

from apps.orgs.models import CompanyInvitation, Membership


COMPLETE = "complete"
INCOMPLETE = "incomplete"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class WorkspaceSetupMetrics:
    """Counts used to derive workspace setup readiness."""

    member_count: int | None = None
    invitation_count: int | None = None
    accounting_period_count: int | None = None
    ledger_count: int | None = None
    opening_balance_count: int | None = None
    party_count: int | None = None
    product_count: int | None = None
    stock_count: int | None = None
    rate_count: int | None = None
    transaction_count: int | None = None


@dataclass(frozen=True)
class SetupChecklistItem:
    key: str
    title: str
    description: str
    status: str
    action_label: str
    url_name: str | None = None

    @property
    def is_complete(self) -> bool:
        return self.status == COMPLETE

    @property
    def is_unknown(self) -> bool:
        return self.status == UNKNOWN


@dataclass(frozen=True)
class WorkspaceSetupChecklist:
    workspace: object
    items: tuple[SetupChecklistItem, ...]

    @property
    def completed_count(self) -> int:
        return sum(1 for item in self.items if item.is_complete)

    @property
    def total_count(self) -> int:
        return len(self.items)

    @property
    def unknown_count(self) -> int:
        return sum(1 for item in self.items if item.is_unknown)

    @property
    def completion_percentage(self) -> int:
        if not self.items:
            return 0
        return round((self.completed_count / self.total_count) * 100)

    @property
    def is_complete(self) -> bool:
        return self.completed_count == self.total_count

    @property
    def incomplete_items(self) -> tuple[SetupChecklistItem, ...]:
        return tuple(item for item in self.items if item.status == INCOMPLETE)

    @property
    def unknown_items(self) -> tuple[SetupChecklistItem, ...]:
        return tuple(item for item in self.items if item.is_unknown)


def build_workspace_setup_checklist(
    *,
    workspace,
    metrics: WorkspaceSetupMetrics | None = None,
) -> WorkspaceSetupChecklist:
    """Build the workspace setup checklist without mutating application state."""

    metrics = metrics or collect_workspace_setup_metrics(workspace=workspace)
    has_profile = bool(getattr(workspace, "name", ""))
    team_count = _sum_known(metrics.member_count, metrics.invitation_count)

    items = (
        SetupChecklistItem(
            key="business_profile",
            title="Business profile",
            description="Confirm workspace identity and basic business details.",
            status=COMPLETE if has_profile else INCOMPLETE,
            action_label="Review profile",
            url_name="workspace_settings_preferences",
        ),
        SetupChecklistItem(
            key="accounting_setup",
            title="Accounting setup",
            description="Create the first accounting period and chart of accounts.",
            status=_status_from_any(
                metrics.accounting_period_count,
                metrics.ledger_count,
            ),
            action_label="Open accounting setup",
            url_name="dea_period_list",
        ),
        SetupChecklistItem(
            key="opening_balances",
            title="Opening balances",
            description="Record opening balances before day-to-day posting.",
            status=_status_from_count(metrics.opening_balance_count),
            action_label="Add opening balances",
            url_name="dea_opening_balance_wizard",
        ),
        SetupChecklistItem(
            key="parties",
            title="Parties",
            description="Add customers, suppliers, brokers, or employees.",
            status=_status_from_count(metrics.party_count),
            action_label="Add parties",
            url_name="party_list",
        ),
        SetupChecklistItem(
            key="products",
            title="Products",
            description="Add inventory items or product variants.",
            status=_status_from_count(metrics.product_count),
            action_label="Add products",
            url_name="product_product_list",
        ),
        SetupChecklistItem(
            key="opening_stock",
            title="Opening stock",
            description="Record initial stock lots before stock operations.",
            status=_status_from_count(metrics.stock_count),
            action_label="Add opening stock",
            url_name="stock_opening_balance_import",
        ),
        SetupChecklistItem(
            key="invite_team",
            title="Invite team",
            description="Invite at least one teammate or keep an invitation pending.",
            status=_status_from_count(team_count, complete_at=2),
            action_label="Invite team",
            url_name="workspace_settings_invite",
        ),
        SetupChecklistItem(
            key="rates",
            title="Rates",
            description="Configure commodity or market rates used by operations.",
            status=_status_from_count(metrics.rate_count),
            action_label="Configure rates",
            url_name="rate_list",
        ),
        SetupChecklistItem(
            key="first_transaction",
            title="First transaction",
            description="Create the first business event or posted source document.",
            status=_status_from_count(metrics.transaction_count),
            action_label="Create transaction",
            url_name="dea_business_events_dashboard",
        ),
    )
    return WorkspaceSetupChecklist(workspace=workspace, items=items)


def collect_workspace_setup_metrics(*, workspace) -> WorkspaceSetupMetrics:
    """Collect best-effort setup metrics for the active workspace/schema."""

    member_count = _safe_queryset_count(Membership.objects.filter(company=workspace))
    invitation_count = _safe_queryset_count(
        CompanyInvitation.pending_queryset().filter(company=workspace)
    )

    return WorkspaceSetupMetrics(
        member_count=member_count,
        invitation_count=invitation_count,
        accounting_period_count=_safe_model_count("dea", "AccountingPeriod"),
        ledger_count=_safe_model_count("dea", "Ledger"),
        opening_balance_count=_sum_known(
            _safe_model_count("dea", "AccountStatement"),
            _safe_model_count("dea", "LedgerStatement"),
        ),
        party_count=_safe_model_count("party", "Party"),
        product_count=_sum_known(
            _safe_model_count("product", "Product"),
            _safe_model_count("product", "ProductVariant"),
        ),
        stock_count=_sum_known(
            _safe_model_count("product", "Stock"),
            _safe_model_count("product", "StockItem"),
        ),
        rate_count=_sum_known(
            _safe_model_count("rates", "Rate"),
            _safe_model_count("rates", "RateSource"),
        ),
        transaction_count=_sum_known(
            _safe_model_count("dea", "Voucher"),
            _safe_model_count("dea", "JournalEntry"),
            _safe_model_count("dea", "BusinessEventDraft"),
            _safe_model_count("product", "StockTransaction"),
            _safe_model_count("girvi", "GivenLoan"),
            _safe_model_count("girvi", "TakenLoan"),
        ),
    )


def _status_from_count(count: int | None, *, complete_at: int = 1) -> str:
    if count is None:
        return UNKNOWN
    return COMPLETE if count >= complete_at else INCOMPLETE


def _status_from_any(*counts: int | None) -> str:
    if any(count is not None and count > 0 for count in counts):
        return COMPLETE
    if any(count is None for count in counts):
        return UNKNOWN
    return INCOMPLETE


def _sum_known(*counts: int | None) -> int | None:
    known_counts = [count for count in counts if count is not None]
    if not known_counts:
        return None
    return sum(known_counts)


def _safe_model_count(app_label: str, model_name: str) -> int | None:
    try:
        model = apps.get_model(app_label, model_name)
    except LookupError:
        return None
    return _safe_queryset_count(model._default_manager.all())


def _safe_queryset_count(queryset: Iterable[object]) -> int | None:
    try:
        return queryset.count()
    except (DatabaseError, LookupError, AttributeError, TypeError, ValueError):
        return None
