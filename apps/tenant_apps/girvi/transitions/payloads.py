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
