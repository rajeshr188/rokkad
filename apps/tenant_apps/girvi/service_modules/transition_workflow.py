"""Workflow helpers for loan transition view orchestration."""

from django.core.exceptions import ValidationError

from apps.tenant_apps.girvi.flows import resolve_runtime_transition_name
from apps.tenant_apps.girvi.lifecycle import (
    lifecycle_status_badge_class,
    lifecycle_status_label,
)
from apps.tenant_apps.girvi.policies import assert_loan_transition_allowed
from apps.tenant_apps.girvi.transition_registry import (
    get_transition_form_class,
    get_transition_form_ui,
    normalize_transition_name,
)


class TransitionWorkflowService:
    """Resolve transition state and centralized policy checks for transition forms."""

    @staticmethod
    def resolve_transition_context(loan, request):
        raw_transition_name = request.GET.get("transition") or request.POST.get(
            "transition"
        )
        transition_name = normalize_transition_name(raw_transition_name)
        transition_name = resolve_runtime_transition_name(loan, transition_name)

        return {
            "status_label": lifecycle_status_label(loan.status),
            "status_badge_class": lifecycle_status_badge_class(loan.status),
            "transition_name": transition_name,
            "form_class": get_transition_form_class(transition_name),
            "transition_ui": get_transition_form_ui(transition_name),
        }

    @staticmethod
    def assert_allowed(loan, transition_name, *, user, workspace):
        try:
            assert_loan_transition_allowed(
                loan,
                transition_name,
                user=user,
                workspace=workspace,
            )
            return None
        except ValidationError as exc:
            return "; ".join(getattr(exc, "messages", None) or [str(exc)])
