"""Public read boundary for Loans and Girvi/Loans coexistence consumers."""

from apps.tenant_apps.loans.selectors.coexistence import (
    UnifiedLoanPortfolio,
    UnifiedLoanReadRow,
    UnifiedLoanSourceTotals,
    get_unified_loan_portfolio,
)
from apps.tenant_apps.loans.feature_flags import (
    LoanModuleFeatureState,
    get_loan_module_feature_state,
    is_new_loans_enabled,
)


__all__ = [
    "UnifiedLoanPortfolio",
    "UnifiedLoanReadRow",
    "UnifiedLoanSourceTotals",
    "get_unified_loan_portfolio",
    "LoanModuleFeatureState",
    "get_loan_module_feature_state",
    "is_new_loans_enabled",
]
