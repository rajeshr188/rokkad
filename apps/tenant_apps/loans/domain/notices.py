"""Database-free PawnLoan notice vocabulary."""

from .vocabulary import StringEnum


class PawnLoanNoticeKind(StringEnum):
    REPAYMENT_REMINDER = "REPAYMENT_REMINDER"
    INTEREST_DUE = "INTEREST_DUE"
    OVERDUE_NOTICE = "OVERDUE_NOTICE"
    RELEASE_CONFIRMATION = "RELEASE_CONFIRMATION"
    AUCTION_NOTICE = "AUCTION_NOTICE"


class PawnLoanNoticeChannel(StringEnum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"


class PawnLoanNoticeStatus(StringEnum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


SUPPORTED_PAWN_LOAN_NOTICE_KINDS = frozenset(
    {
        PawnLoanNoticeKind.REPAYMENT_REMINDER,
        PawnLoanNoticeKind.INTEREST_DUE,
        PawnLoanNoticeKind.OVERDUE_NOTICE,
        PawnLoanNoticeKind.RELEASE_CONFIRMATION,
        PawnLoanNoticeKind.AUCTION_NOTICE,
    }
)

STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS = frozenset(
    SUPPORTED_PAWN_LOAN_NOTICE_KINDS - {PawnLoanNoticeKind.AUCTION_NOTICE}
)


__all__ = [
    "PawnLoanNoticeChannel",
    "PawnLoanNoticeKind",
    "PawnLoanNoticeStatus",
    "SUPPORTED_PAWN_LOAN_NOTICE_KINDS",
    "STAFF_CREATABLE_PAWN_LOAN_NOTICE_KINDS",
]
