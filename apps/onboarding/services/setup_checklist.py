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
    party_count: int | None = None
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
    optional: bool = False

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
        return sum(1 for item in self.items if item.is_complete and not item.optional)

    @property
    def total_count(self) -> int:
        return sum(1 for item in self.items if not item.optional)

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
            key="parties",
            title="Parties",
            description="Add customers, suppliers, brokers, or employees.",
            status=_status_from_count(metrics.party_count),
            action_label="Add parties",
            url_name="party_list",
        ),
        SetupChecklistItem(
            key="invite_team",
            title="Team (optional)",
            description="Optional: invite staff when you need them. A sole owner can work alone.",
            optional=True,
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
        party_count=_safe_model_count("party", "Party"),
        rate_count=_sum_known(
            _safe_model_count("rates", "Rate"),
            _safe_model_count("rates", "RateSource"),
        ),
        transaction_count=_sum_known(
            _safe_model_count("loans", "PawnLoanEvent"),
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


def build_business_setup(*, workspace):
    """Resume from persisted lending configuration; GET never creates setup records."""
    from django.urls import reverse
    from apps.tenant_apps.loans.selectors.setup import get_pawn_setup_checklist
    from apps.tenant_apps.party.models import Party

    lending = get_pawn_setup_checklist(workspace)
    steps = [{
        "key": "business_profile", "title": "Business details", "complete": bool(workspace.name),
        "description": "Review your business name and branding.",
        "action_label": "Review business details",
        "action_url": reverse("workspace_update", kwargs={"workspace_id": workspace.pk}),
    }, *lending["steps"], {
        "key": "borrower", "title": "First borrower",
        "complete": Party.objects.filter(workspace=workspace, status=Party.PartyStatus.ACTIVE).exists(),
        "description": "Add a borrower, then record their collateral and photos in a new loan.",
        "action_label": "Manage borrowers",
        "action_url": reverse("workspace_slug_parties", kwargs={"workspace_slug": workspace.slug}),
    }]
    return {
        "steps": steps, "next_step": next((step for step in steps if not step["complete"]), None),
        "completed_count": sum(step["complete"] for step in steps), "total_count": len(steps),
        "ready": all(step["complete"] for step in steps), "as_of_date": lending["as_of_date"],
    }
