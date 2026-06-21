"""Canonical Girvi lifecycle vocabulary and compatibility helpers.

The canonical business language is the next-generation lifecycle state set
(`Draft`, `PendingApproval`, `ActiveCurrent`, ...). Some production rows and
legacy flows still persist older status values (`Created`, `Disbursed`, ...).
New query/service code should import this module instead of comparing raw
status strings inline.
"""

LEGACY_DRAFT = "Created"
LEGACY_APPROVED = "Approved"
LEGACY_ACTIVE = "Disbursed"
LEGACY_RELEASED = "Released"
LEGACY_CLOSED = "Closed"
LEGACY_REJECTED = "Rejected"
LEGACY_CANCELLED = "Cancelled"
LEGACY_DEFAULTED = "Defaulted"
LEGACY_AUCTIONED = "Auctioned"
LEGACY_SOLD = "Sold"
LEGACY_REPLEDGED = "Repledged"

CANONICAL_DRAFT = "Draft"
CANONICAL_PENDING_APPROVAL = "PendingApproval"
CANONICAL_APPROVED = "Approved"
CANONICAL_ACTIVE_CURRENT = "ActiveCurrent"
CANONICAL_ACTIVE_OVERDUE = "ActiveOverdue"
CANONICAL_ACTIVE_NPA = "ActiveNPA"
CANONICAL_CLOSURE_PENDING = "ClosurePending"
CANONICAL_RENEWAL_PENDING = "RenewalPending"
CANONICAL_AUCTION_INITIATED = "AuctionInitiated"
CANONICAL_AUCTION_IN_PROGRESS = "AuctionInProgress"
CANONICAL_AUCTION_COMPLETE = "AuctionComplete"
CANONICAL_CLOSED = "Closed"
CANONICAL_RENEWED = "Renewed"
CANONICAL_WRITTEN_OFF = "WrittenOff"
CANONICAL_REJECTED = "Rejected"
CANONICAL_CANCELLED = "Cancelled"

TAKEN_DRAFT = "Draft"
TAKEN_ACTIVE = "Active"
TAKEN_SETTLEMENT_PENDING = "SettlementPending"
TAKEN_CLOSED = "Closed"
TAKEN_CANCELLED = "Cancelled"

LEGACY_TO_CANONICAL_STATUS = {
    LEGACY_DRAFT: CANONICAL_DRAFT,
    LEGACY_APPROVED: CANONICAL_APPROVED,
    LEGACY_ACTIVE: CANONICAL_ACTIVE_CURRENT,
    LEGACY_RELEASED: CANONICAL_CLOSED,
    LEGACY_CLOSED: CANONICAL_CLOSED,
    LEGACY_REJECTED: CANONICAL_REJECTED,
    LEGACY_CANCELLED: CANONICAL_CANCELLED,
    LEGACY_DEFAULTED: CANONICAL_ACTIVE_NPA,
    LEGACY_AUCTIONED: CANONICAL_AUCTION_COMPLETE,
    LEGACY_SOLD: CANONICAL_AUCTION_COMPLETE,
    LEGACY_REPLEDGED: CANONICAL_RENEWED,
}

CANONICAL_STATUS_VALUES = (
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    CANONICAL_APPROVED,
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_CLOSURE_PENDING,
    CANONICAL_RENEWAL_PENDING,
    CANONICAL_AUCTION_INITIATED,
    CANONICAL_AUCTION_IN_PROGRESS,
    CANONICAL_AUCTION_COMPLETE,
    CANONICAL_CLOSED,
    CANONICAL_RENEWED,
    CANONICAL_WRITTEN_OFF,
    CANONICAL_REJECTED,
    CANONICAL_CANCELLED,
)

NEXT_GEN_ACTIVE_COMPAT_STATUSES = (
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_CLOSURE_PENDING,
    CANONICAL_RENEWAL_PENDING,
)

ACTIVE_LOAN_STATUSES = (
    LEGACY_DRAFT,
    LEGACY_APPROVED,
    LEGACY_ACTIVE,
    *NEXT_GEN_ACTIVE_COMPAT_STATUSES,
    TAKEN_DRAFT,
    TAKEN_ACTIVE,
    TAKEN_SETTLEMENT_PENDING,
)

OVERDUE_LOAN_STATUSES = (
    LEGACY_DEFAULTED,
    LEGACY_AUCTIONED,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_ACTIVE_NPA,
)

V2_CLOSURE_STATUSES = (
    CANONICAL_ACTIVE_CURRENT,
    CANONICAL_ACTIVE_OVERDUE,
    CANONICAL_ACTIVE_NPA,
    CANONICAL_CLOSURE_PENDING,
)

RELEASED_COMPAT_STATUSES = (
    LEGACY_RELEASED,
    LEGACY_CLOSED,
    CANONICAL_CLOSED,
    TAKEN_CLOSED,
)

UNRELEASED_EXCLUDED_STATUSES = RELEASED_COMPAT_STATUSES

EDITABLE_ITEM_STATUSES = (
    LEGACY_DRAFT,
    CANONICAL_DRAFT,
    CANONICAL_PENDING_APPROVAL,
    LEGACY_APPROVED,
    CANONICAL_APPROVED,
    TAKEN_DRAFT,
)


def canonical_status(status: str | None) -> str | None:
    """Return the canonical lifecycle value for a legacy or canonical status."""
    if status is None:
        return None
    return LEGACY_TO_CANONICAL_STATUS.get(str(status), str(status))


GIVEN_STATUS_LABELS = {
    CANONICAL_DRAFT: "Draft",
    CANONICAL_PENDING_APPROVAL: "Pending Approval",
    CANONICAL_APPROVED: "Approved",
    CANONICAL_ACTIVE_CURRENT: "Active Current",
    CANONICAL_ACTIVE_OVERDUE: "Active Overdue",
    CANONICAL_ACTIVE_NPA: "Active NPA",
    CANONICAL_CLOSURE_PENDING: "Closure Pending",
    CANONICAL_RENEWAL_PENDING: "Renewal Pending",
    CANONICAL_AUCTION_INITIATED: "Auction Initiated",
    CANONICAL_AUCTION_IN_PROGRESS: "Auction In Progress",
    CANONICAL_AUCTION_COMPLETE: "Auction Complete",
    CANONICAL_CLOSED: "Closed",
    CANONICAL_RENEWED: "Renewed",
    CANONICAL_WRITTEN_OFF: "Written Off",
    CANONICAL_REJECTED: "Rejected",
    CANONICAL_CANCELLED: "Cancelled",
}

TAKEN_STATUS_LABELS = {
    TAKEN_DRAFT: "Draft",
    TAKEN_ACTIVE: "Active",
    TAKEN_SETTLEMENT_PENDING: "Settlement Pending",
    TAKEN_CLOSED: "Closed",
    TAKEN_CANCELLED: "Cancelled",
}

STATUS_BADGE_CLASSES = {
    CANONICAL_DRAFT: "bg-secondary",
    CANONICAL_PENDING_APPROVAL: "bg-warning text-dark",
    CANONICAL_APPROVED: "bg-success",
    CANONICAL_ACTIVE_CURRENT: "bg-primary",
    CANONICAL_ACTIVE_OVERDUE: "bg-warning text-dark",
    CANONICAL_ACTIVE_NPA: "bg-dark",
    CANONICAL_CLOSURE_PENDING: "bg-info text-dark",
    CANONICAL_RENEWAL_PENDING: "bg-info text-dark",
    CANONICAL_AUCTION_INITIATED: "bg-dark",
    CANONICAL_AUCTION_IN_PROGRESS: "bg-dark",
    CANONICAL_AUCTION_COMPLETE: "bg-dark",
    CANONICAL_CLOSED: "bg-info",
    CANONICAL_RENEWED: "bg-info",
    CANONICAL_WRITTEN_OFF: "bg-danger",
    CANONICAL_REJECTED: "bg-danger",
    CANONICAL_CANCELLED: "bg-danger",
    TAKEN_ACTIVE: "bg-primary",
    TAKEN_SETTLEMENT_PENDING: "bg-info text-dark",
}


def taken_canonical_status(status: str | None) -> str | None:
    """Return the canonical TakenLoan lifecycle value for legacy or current status."""
    if status is None:
        return None
    legacy_taken_map = {
        LEGACY_DRAFT: TAKEN_DRAFT,
        LEGACY_APPROVED: TAKEN_DRAFT,
        LEGACY_ACTIVE: TAKEN_ACTIVE,
        LEGACY_RELEASED: TAKEN_CLOSED,
        LEGACY_CLOSED: TAKEN_CLOSED,
        LEGACY_CANCELLED: TAKEN_CANCELLED,
        LEGACY_REJECTED: TAKEN_CANCELLED,
        LEGACY_DEFAULTED: TAKEN_ACTIVE,
        LEGACY_AUCTIONED: TAKEN_ACTIVE,
        LEGACY_SOLD: TAKEN_ACTIVE,
        LEGACY_REPLEDGED: TAKEN_ACTIVE,
    }
    return legacy_taken_map.get(str(status), str(status))


def lifecycle_status_label(status: str | None, *, loan_kind: str = "given") -> str:
    """Human-readable canonical lifecycle label for UI display."""
    if loan_kind == "taken":
        normalized = taken_canonical_status(status)
        return TAKEN_STATUS_LABELS.get(normalized, str(normalized or ""))
    normalized = canonical_status(status)
    return GIVEN_STATUS_LABELS.get(normalized, str(normalized or ""))


def lifecycle_status_badge_class(status: str | None, *, loan_kind: str = "given") -> str:
    """Bootstrap badge class for canonical lifecycle status display."""
    normalized = (
        taken_canonical_status(status)
        if loan_kind == "taken"
        else canonical_status(status)
    )
    return STATUS_BADGE_CLASSES.get(normalized, "bg-secondary")


def is_released_status(status: str | None) -> bool:
    return canonical_status(status) == CANONICAL_CLOSED


def is_active_status(status: str | None) -> bool:
    return canonical_status(status) in {
        CANONICAL_ACTIVE_CURRENT,
        CANONICAL_ACTIVE_OVERDUE,
        CANONICAL_ACTIVE_NPA,
        CANONICAL_CLOSURE_PENDING,
        CANONICAL_RENEWAL_PENDING,
    }
