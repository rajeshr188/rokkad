"""Fail-closed workspace activation policy for the standalone accounting MVP."""

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection

from apps.configuration.services import PreferenceService
from apps.orgs.permissions import get_effective_permissions

from .diagnostics import accounting_integrity_findings
from .models import AccountingBook, PeriodStatus


ACCOUNTING_SUCCESSOR_ENABLED_KEY = "accounting__successor_enabled"
ACCOUNTING_WORKFLOW_MODE_KEY = "accounting__workflow_mode"
REQUIRED_LEDGER_KEYS = frozenset({"CASH", "ACCOUNTS_RECEIVABLE", "SALES"})


@dataclass(frozen=True, slots=True)
class AccountingActivationState:
    workspace_id: int
    enabled: bool
    blockers: tuple[str, ...]

    @property
    def ready(self):
        return not self.blockers


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def activation_blockers(workspace) -> tuple[str, ...]:
    if workspace is None or getattr(workspace, "pk", None) is None:
        return ("A persisted workspace is required.",)
    if connection.schema_name != workspace.schema_name:
        return ("The active tenant does not match the workspace.",)
    books = list(AccountingBook.objects.select_related("organization").filter(book_key="PRIMARY"))
    if len(books) != 1:
        return ("Exactly one PRIMARY accounting book is required.",)
    book = books[0]
    blockers = []
    if book.organization.external_tenant_key != workspace.schema_name:
        blockers.append("The PRIMARY book is not bound to this tenant.")
    ledger_keys = set(book.ledgers.filter(is_active=True).values_list("ledger_key", flat=True))
    missing = sorted(REQUIRED_LEDGER_KEYS - ledger_keys)
    if missing:
        blockers.append(f"Required ledgers are missing: {', '.join(missing)}.")
    if not book.periods.filter(status=PeriodStatus.OPEN).exists():
        blockers.append("At least one open accounting period is required.")
    findings = [
        row for row in accounting_integrity_findings()
        if not row.book_key or row.book_key == book.book_key
    ]
    if findings:
        blockers.append(f"Accounting diagnostics report {len(findings)} finding(s).")
    return tuple(blockers)


def get_accounting_activation_state(workspace) -> AccountingActivationState:
    blockers = activation_blockers(workspace)
    configured = _as_bool(
        PreferenceService.get_workspace(
            workspace, ACCOUNTING_SUCCESSOR_ENABLED_KEY, False
        )
    )
    return AccountingActivationState(
        workspace_id=workspace.pk,
        enabled=configured and not blockers,
        blockers=blockers,
    )


def is_accounting_successor_enabled(workspace) -> bool:
    if workspace is None or getattr(workspace, "pk", None) is None:
        return False
    return get_accounting_activation_state(workspace).enabled


def get_accounting_workflow_mode(workspace) -> str:
    value = str(PreferenceService.get_workspace(
        workspace, ACCOUNTING_WORKFLOW_MODE_KEY, "OWNER"
    )).upper()
    return value if value in {"OWNER", "TEAM"} else "OWNER"


def set_accounting_workflow_mode(workspace, *, mode, actor):
    if connection.schema_name != getattr(workspace, "schema_name", None):
        raise ValidationError("Accounting workflow changes require the matching tenant schema.")
    if "accounting_period_manage" not in get_effective_permissions(actor, workspace):
        raise PermissionDenied("Only an accounting administrator may change workflow mode.")
    mode = str(mode).upper()
    if mode not in {"OWNER", "TEAM"}:
        raise ValidationError("Workflow mode must be OWNER or TEAM.")
    PreferenceService.set_workspace(
        workspace, ACCOUNTING_WORKFLOW_MODE_KEY, mode, user=actor
    )
    return mode


def set_accounting_successor_enabled(workspace, *, enabled, actor):
    if connection.schema_name != getattr(workspace, "schema_name", None):
        raise ValidationError("Accounting activation requires the matching tenant schema.")
    if "accounting_period_manage" not in get_effective_permissions(actor, workspace):
        raise PermissionDenied("Only an accounting administrator may change activation.")
    if enabled:
        blockers = activation_blockers(workspace)
        if blockers:
            raise ValidationError({"activation": list(blockers)})
    PreferenceService.set_workspace(
        workspace,
        ACCOUNTING_SUCCESSOR_ENABLED_KEY,
        bool(enabled),
        user=actor,
    )
    return get_accounting_activation_state(workspace)


__all__ = [
    "ACCOUNTING_SUCCESSOR_ENABLED_KEY",
    "ACCOUNTING_WORKFLOW_MODE_KEY",
    "AccountingActivationState",
    "activation_blockers",
    "get_accounting_activation_state",
    "is_accounting_successor_enabled",
    "get_accounting_workflow_mode",
    "set_accounting_workflow_mode",
    "set_accounting_successor_enabled",
]
