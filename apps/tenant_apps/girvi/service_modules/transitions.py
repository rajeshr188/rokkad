from apps.tenant_apps.girvi.transition_registry import (
    build_transition_payload,
    get_transition_command,
    normalize_transition_name,
)
from apps.tenant_apps.girvi.transitions.types import TransitionResult


class LoanTransitionService:
    """Orchestrates a single GivenLoan FSM transition end-to-end."""

    def __init__(self, loan, user, tenant):
        self.loan = loan
        self.user = user
        self.tenant = tenant

    def execute(self, transition_name: str, **payload) -> "TransitionResult":
        from django.utils.translation import gettext_lazy as _
        from apps.tenant_apps.girvi.flows import LoanFlow

        transition_name = normalize_transition_name(transition_name)
        flow = LoanFlow(self.loan, self.user, self.tenant)
        transition_method = getattr(flow, transition_name, None)

        if not (transition_method and transition_method.can_proceed()):
            return TransitionResult(
                success=False,
                level="error",
                message=str(
                    _(
                        "You do not have permission to perform this action "
                        "or the transition is not valid."
                    )
                ),
            )

        command_class = get_transition_command(transition_name)
        command = command_class(self.loan, self.user, self.tenant)
        try:
            payload_obj = build_transition_payload(transition_name, payload)
        except (TypeError, ValueError) as exc:
            return TransitionResult(
                success=False,
                level="error",
                message=str(exc),
            )
        return command.execute(transition_method, payload=payload_obj)
