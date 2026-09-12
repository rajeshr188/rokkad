"""Quote guidance using the same reference lookup as loan valuation."""

from apps.tenancy.context import current_workspace_id
from .origination_rates import get_origination_quote_rows


def get_metal_rate_readiness(*, workspace, as_of_date, metals=("GOLD", "SILVER")):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Rate readiness requires the active Workspace.")
    return get_origination_quote_rows(workspace_id=workspace.pk, loan_date=as_of_date, metals=metals)
