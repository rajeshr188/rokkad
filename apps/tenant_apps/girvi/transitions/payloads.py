from dataclasses import dataclass
from decimal import Decimal


@dataclass
class ApprovePayload:
    approved_by: str


@dataclass
class DisbursePayload:
    disbursed_by: str


@dataclass
class CancelPayload:
    cancelled_by: str
    reason: str


@dataclass
class MarkDefaultedPayload:
    marked_by: str
    reason: str


@dataclass
class MarkAuctionedPayload:
    auctioned_by: str
    amount: Decimal


@dataclass
class MarkSoldPayload:
    sold_by: str
    amount: Decimal


@dataclass
class RepledgePayload:
    created_by: str


@dataclass
class UndoDisbursePayload:
    undone_by: str
    reason: str


@dataclass
class UndoReleasePayload:
    undone_by: str
    reason: str


@dataclass
class UndoRepledgePayload:
    undone_by: str
    reason: str = ""


@dataclass
class SubmitForApprovalPayload:
    submitted_by: str | None = None


@dataclass
class ReturnToDraftPayload:
    returned_by: str | None = None
    reason: str = ""


@dataclass
class ApproveLoanPayload:
    approved_by: str | None = None


@dataclass
class RejectLoanPayload:
    rejected_by: str | None = None
    reason: str = ""


@dataclass
class MarkOverduePayload:
    marked_by: str | None = None


@dataclass
class CureToCurrentPayload:
    cured_by: str | None = None
    note: str = ""


@dataclass
class MarkNPAPayload:
    marked_by: str | None = None
    reason: str = ""


@dataclass
class RequestClosurePayload:
    requested_by: str | None = None


@dataclass
class CompleteClosurePayload:
    completed_by: str | None = None
    release_id: str | None = None


@dataclass
class ReopenClosurePendingPayload:
    reopened_by: str | None = None
    reason: str = ""


@dataclass
class RequestRenewalPayload:
    requested_by: str | None = None


@dataclass
class CompleteRenewalPayload:
    completed_by: str | None = None
    successor_loan_id: str | None = None


@dataclass
class CancelRenewalRequestPayload:
    cancelled_by: str | None = None
    reason: str = ""


@dataclass
class InitiateAuctionPayload:
    initiated_by: str | None = None


@dataclass
class StartAuctionPayload:
    started_by: str | None = None


@dataclass
class CancelAuctionPayload:
    cancelled_by: str | None = None
    reason: str = ""


@dataclass
class CompleteAuctionPayload:
    completed_by: str | None = None
    recovery_amount: Decimal | None = None


@dataclass
class WriteOffLoanPayload:
    written_off_by: str | None = None
    reason: str = ""
