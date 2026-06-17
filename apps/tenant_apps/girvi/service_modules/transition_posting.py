"""Transition-specific posting helpers for Girvi recovery commands."""

from apps.tenant_apps.girvi.service_modules.loan_posting import GivenLoanPostingService


def post_auction_recovery_for_transition(loan, amount, user):
    """Post an auction recovery payment after a transition completes."""
    return GivenLoanPostingService().post_auction_recovery(loan, amount, user)


def post_sale_recovery_for_transition(loan, amount, user):
    """Post a sale recovery payment after a transition completes."""
    return GivenLoanPostingService().post_sale_recovery(loan, amount, user)
