"""DEA posting rule for full-debt PawnLoan auction recovery."""

from apps.tenant_apps.dea.posting.registry import register_rule
from apps.tenant_apps.dea.posting.rules.pawn_loan_release import PawnLoanReleaseRule


@register_rule("PAWN_LOAN_AUCTION_RECOVERY")
class PawnLoanAuctionRecoveryRule(PawnLoanReleaseRule):
    voucher_type = "PAWN_LOAN_AUCTION_RECOVERY"
    event_kind = "AUCTION_RECOVERY"
    event_label = "auction recovery"
    recognition_section = "auction"
