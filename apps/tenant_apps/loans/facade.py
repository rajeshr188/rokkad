"""Public read boundary for Loans consumers."""
from apps.tenant_apps.loans.feature_flags import (
    LoanModuleFeatureState,
    get_loan_module_feature_state,
    is_new_loans_enabled,
)


__all__ = [
    "LoanModuleFeatureState",
    "get_loan_module_feature_state",
    "is_new_loans_enabled",
]
