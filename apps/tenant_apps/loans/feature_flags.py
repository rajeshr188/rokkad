"""Workspace-scoped Loans cutover policy."""

from dataclasses import dataclass

from apps.configuration.services import PreferenceService
from apps.tenant_apps.loans.models import current_tenant_workspace_id


LOANS_NEW_MODULE_ENABLED_KEY = "loan__new_module_enabled"


@dataclass(frozen=True)
class LoanModuleFeatureState:
    workspace_id: int
    enabled: bool

    @property
    def primary_app(self):
        return "loans" if self.enabled else "girvi"


def get_loan_module_feature_state(workspace):
    if workspace is None or getattr(workspace, "pk", None) is None:
        raise ValueError("A persisted workspace is required for the Loans feature gate.")
    return LoanModuleFeatureState(
        workspace_id=workspace.pk,
        enabled=_as_bool(
            PreferenceService.get_workspace(
                workspace,
                LOANS_NEW_MODULE_ENABLED_KEY,
                False,
            )
        ),
    )


def is_new_loans_enabled(workspace):
    if workspace is None or getattr(workspace, "pk", None) is None:
        return False
    return get_loan_module_feature_state(workspace).enabled


def set_new_loans_enabled(workspace, *, enabled, actor=None):
    tenant_workspace_id = current_tenant_workspace_id()
    if tenant_workspace_id is None:
        raise ValueError("Loans cutover changes require an active tenant schema.")
    if workspace.pk != tenant_workspace_id:
        raise ValueError("Loans cutover workspace must match the active tenant.")
    PreferenceService.set_workspace(
        workspace,
        LOANS_NEW_MODULE_ENABLED_KEY,
        bool(enabled),
        user=actor,
    )
    return get_loan_module_feature_state(workspace)


def _as_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


__all__ = [
    "LOANS_NEW_MODULE_ENABLED_KEY",
    "LoanModuleFeatureState",
    "get_loan_module_feature_state",
    "is_new_loans_enabled",
    "set_new_loans_enabled",
]
