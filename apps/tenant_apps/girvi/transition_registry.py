"""Central registry for GivenLoan transition wiring.

This module intentionally separates:
1) legal state transitions (defined in LoanFlow), and
2) app-layer wiring (form class + endpoint support).

Keeping this map in one place reduces flow/view/template drift.
"""

from dataclasses import dataclass

from django.urls import reverse

from .flows import resolve_runtime_transition_name
from .transitions.commands import get_transition_command_class


@dataclass(frozen=True)
class TransitionSpec:
    key: str
    form_class_path: str
    payload_class_path: str | None = None
    command_class: type | None = None
    enabled_in_loan_transition_view: bool = True


@dataclass(frozen=True)
class TransitionUISpec:
    key: str
    title: str
    button_class: str
    icon: str


@dataclass(frozen=True)
class TransitionStateSpec:
    key: str
    display_name: str
    source_statuses: tuple[str, ...]
    target_status: str
    execution_mode: str
    notes: str


@dataclass(frozen=True)
class TransitionFormUISpec:
    key: str
    heading: str
    icon: str
    badge_class: str


TRANSITION_ALIAS_MAP = {
    "mark sold": "mark_sold",
    "release": "deliver",
    "release_to_customer": "deliver",
    "close": "request_closure",
    "renew": "request_renewal",
    "writeoff": "write_off_loan",
}


TRANSITION_REGISTRY: dict[str, TransitionSpec] = {
    "approve": TransitionSpec("approve", "apps.tenant_apps.girvi.forms.ApproveLoanForm", "apps.tenant_apps.girvi.transitions.payloads.ApprovePayload", get_transition_command_class("approve")),
    "disburse": TransitionSpec("disburse", "apps.tenant_apps.girvi.forms.DisburseLoanForm", "apps.tenant_apps.girvi.transitions.payloads.DisbursePayload", get_transition_command_class("disburse")),
    "cancel": TransitionSpec("cancel", "apps.tenant_apps.girvi.forms.CancelLoanForm", "apps.tenant_apps.girvi.transitions.payloads.CancelPayload", get_transition_command_class("cancel")),
    "mark_defaulted": TransitionSpec("mark_defaulted", "apps.tenant_apps.girvi.forms.MarkDefaultedLoanForm", "apps.tenant_apps.girvi.transitions.payloads.MarkDefaultedPayload", get_transition_command_class("mark_defaulted")),
    "mark_auctioned": TransitionSpec("mark_auctioned", "apps.tenant_apps.girvi.forms.MarkAuctionedLoanForm", "apps.tenant_apps.girvi.transitions.payloads.MarkAuctionedPayload", get_transition_command_class("mark_auctioned")),
    "mark_sold": TransitionSpec("mark_sold", "apps.tenant_apps.girvi.forms.MarkSoldLoanForm", "apps.tenant_apps.girvi.transitions.payloads.MarkSoldPayload", get_transition_command_class("mark_sold")),
    "undo_disburse": TransitionSpec("undo_disburse", "apps.tenant_apps.girvi.forms.UndoDisburseLoanForm", "apps.tenant_apps.girvi.transitions.payloads.UndoDisbursePayload", get_transition_command_class("undo_disburse")),
    "undo_release": TransitionSpec("undo_release", "apps.tenant_apps.girvi.forms.UndoReleaseLoanForm", "apps.tenant_apps.girvi.transitions.payloads.UndoReleasePayload", get_transition_command_class("undo_release")),
    "repledge": TransitionSpec("repledge", "apps.tenant_apps.girvi.forms.RepledgeLoanForm", "apps.tenant_apps.girvi.transitions.payloads.RepledgePayload", get_transition_command_class("repledge")),
    "undo_repledge": TransitionSpec("undo_repledge", "apps.tenant_apps.girvi.forms.UndoRepledgeLoanForm", "apps.tenant_apps.girvi.transitions.payloads.UndoRepledgePayload", get_transition_command_class("undo_repledge")),
    # Next-generation lifecycle transitions are registered for service/runtime use
    # but remain hidden from the generic transition form until dedicated UI is added.
    "submit_for_approval": TransitionSpec("submit_for_approval", "apps.tenant_apps.girvi.forms.SubmitForApprovalLoanForm", "apps.tenant_apps.girvi.transitions.payloads.SubmitForApprovalPayload", get_transition_command_class("submit_for_approval"), enabled_in_loan_transition_view=True),
    "return_to_draft": TransitionSpec("return_to_draft", "", "apps.tenant_apps.girvi.transitions.payloads.ReturnToDraftPayload", get_transition_command_class("return_to_draft"), enabled_in_loan_transition_view=False),
    "approve_loan": TransitionSpec("approve_loan", "apps.tenant_apps.girvi.forms.ApproveLoanForm", "apps.tenant_apps.girvi.transitions.payloads.ApproveLoanPayload", get_transition_command_class("approve_loan"), enabled_in_loan_transition_view=True),
    "reject_loan": TransitionSpec("reject_loan", "apps.tenant_apps.girvi.forms.RejectLoanForm", "apps.tenant_apps.girvi.transitions.payloads.RejectLoanPayload", get_transition_command_class("reject_loan"), enabled_in_loan_transition_view=True),
    "cancel_loan": TransitionSpec("cancel_loan", "apps.tenant_apps.girvi.forms.CancelLoanForm", "apps.tenant_apps.girvi.transitions.payloads.CancelPayload", get_transition_command_class("cancel_loan"), enabled_in_loan_transition_view=True),
    "disburse_loan": TransitionSpec("disburse_loan", "apps.tenant_apps.girvi.forms.DisburseLoanForm", "apps.tenant_apps.girvi.transitions.payloads.DisbursePayload", get_transition_command_class("disburse_loan"), enabled_in_loan_transition_view=True),
    "undo_disbursal": TransitionSpec("undo_disbursal", "", "apps.tenant_apps.girvi.transitions.payloads.UndoDisbursePayload", get_transition_command_class("undo_disbursal"), enabled_in_loan_transition_view=False),
    "mark_overdue": TransitionSpec("mark_overdue", "", "apps.tenant_apps.girvi.transitions.payloads.MarkOverduePayload", get_transition_command_class("mark_overdue"), enabled_in_loan_transition_view=False),
    "cure_to_current": TransitionSpec("cure_to_current", "", "apps.tenant_apps.girvi.transitions.payloads.CureToCurrentPayload", get_transition_command_class("cure_to_current"), enabled_in_loan_transition_view=False),
    "mark_npa": TransitionSpec("mark_npa", "apps.tenant_apps.girvi.forms.MarkNPALoanForm", "apps.tenant_apps.girvi.transitions.payloads.MarkNPAPayload", get_transition_command_class("mark_npa"), enabled_in_loan_transition_view=True),
    "request_closure": TransitionSpec("request_closure", "apps.tenant_apps.girvi.forms.RequestClosureLoanForm", "apps.tenant_apps.girvi.transitions.payloads.RequestClosurePayload", get_transition_command_class("request_closure"), enabled_in_loan_transition_view=True),
    "complete_closure": TransitionSpec("complete_closure", "", "apps.tenant_apps.girvi.transitions.payloads.CompleteClosurePayload", get_transition_command_class("complete_closure"), enabled_in_loan_transition_view=False),
    "reopen_from_closure_pending": TransitionSpec("reopen_from_closure_pending", "", "apps.tenant_apps.girvi.transitions.payloads.ReopenClosurePendingPayload", get_transition_command_class("reopen_from_closure_pending"), enabled_in_loan_transition_view=False),
    "request_renewal": TransitionSpec("request_renewal", "apps.tenant_apps.girvi.forms.RequestRenewalLoanForm", "apps.tenant_apps.girvi.transitions.payloads.RequestRenewalPayload", get_transition_command_class("request_renewal"), enabled_in_loan_transition_view=True),
    "complete_renewal": TransitionSpec("complete_renewal", "", "apps.tenant_apps.girvi.transitions.payloads.CompleteRenewalPayload", get_transition_command_class("complete_renewal"), enabled_in_loan_transition_view=False),
    "cancel_renewal_request": TransitionSpec("cancel_renewal_request", "", "apps.tenant_apps.girvi.transitions.payloads.CancelRenewalRequestPayload", get_transition_command_class("cancel_renewal_request"), enabled_in_loan_transition_view=False),
    "initiate_auction": TransitionSpec("initiate_auction", "", "apps.tenant_apps.girvi.transitions.payloads.InitiateAuctionPayload", get_transition_command_class("initiate_auction"), enabled_in_loan_transition_view=False),
    "start_auction": TransitionSpec("start_auction", "", "apps.tenant_apps.girvi.transitions.payloads.StartAuctionPayload", get_transition_command_class("start_auction"), enabled_in_loan_transition_view=False),
    "cancel_auction": TransitionSpec("cancel_auction", "", "apps.tenant_apps.girvi.transitions.payloads.CancelAuctionPayload", get_transition_command_class("cancel_auction"), enabled_in_loan_transition_view=False),
    "complete_auction": TransitionSpec("complete_auction", "", "apps.tenant_apps.girvi.transitions.payloads.CompleteAuctionPayload", get_transition_command_class("complete_auction"), enabled_in_loan_transition_view=False),
    "close_after_auction": TransitionSpec("close_after_auction", "", None, get_transition_command_class("close_after_auction"), enabled_in_loan_transition_view=False),
    "write_off_loan": TransitionSpec("write_off_loan", "apps.tenant_apps.girvi.forms.WriteOffLoanForm", "apps.tenant_apps.girvi.transitions.payloads.WriteOffLoanPayload", get_transition_command_class("write_off_loan"), enabled_in_loan_transition_view=True),
    # Deliver/release is intentionally excluded from this endpoint.
    # It must run through Release create flow for custody + accounting checks.
}


TRANSITION_STATE_REGISTRY: dict[str, TransitionStateSpec] = {
    "approve": TransitionStateSpec(
        key="approve",
        display_name="Approve Loan",
        source_statuses=("Created",),
        target_status="Approved",
        execution_mode="generic-transition",
        notes="Administrative approval only; no accounting impact.",
    ),
    "disburse": TransitionStateSpec(
        key="disburse",
        display_name="Disburse Funds",
        source_statuses=("Approved",),
        target_status="Disbursed",
        execution_mode="transition-with-accounting",
        notes="Moves an approved loan into an active disbursed state and posts the disbursal entry.",
    ),
    "deliver": TransitionStateSpec(
        key="deliver",
        display_name="Release to Customer",
        source_statuses=("Disbursed",),
        target_status="Released",
        execution_mode="release-flow",
        notes="Business release action: create the Release document, run the deliver FSM transition, and post release accounting.",
    ),
    "cancel": TransitionStateSpec(
        key="cancel",
        display_name="Cancel Loan",
        source_statuses=("Created", "Approved"),
        target_status="Cancelled",
        execution_mode="generic-transition",
        notes="Cancels a loan before it is disbursed.",
    ),
    "mark_defaulted": TransitionStateSpec(
        key="mark_defaulted",
        display_name="Mark Defaulted",
        source_statuses=("Disbursed",),
        target_status="Defaulted",
        execution_mode="generic-transition",
        notes="Flags a disbursed loan as defaulted; follow-up recovery action may occur later.",
    ),
    "mark_auctioned": TransitionStateSpec(
        key="mark_auctioned",
        display_name="Record Auction",
        source_statuses=("Defaulted",),
        target_status="Auctioned",
        execution_mode="warning-transition",
        notes="Records auction outcome after default and may require downstream accounting handling.",
    ),
    "mark_sold": TransitionStateSpec(
        key="mark_sold",
        display_name="Record Sale",
        source_statuses=("Disbursed",),
        target_status="Sold",
        execution_mode="warning-transition",
        notes="Records a sale of collateral from the disbursed state.",
    ),
    "undo_disburse": TransitionStateSpec(
        key="undo_disburse",
        display_name="Undo Disbursal",
        source_statuses=("Disbursed",),
        target_status="Approved",
        execution_mode="reversal-transition",
        notes="Reverses the disbursal and its accounting entry.",
    ),
    "undo_release": TransitionStateSpec(
        key="undo_release",
        display_name="Undo Release",
        source_statuses=("Released",),
        target_status="Disbursed",
        execution_mode="reversal-transition",
        notes="Reverses the release document and related accounting entry.",
    ),
    "repledge": TransitionStateSpec(
        key="repledge",
        display_name="Mark Repledged",
        source_statuses=("Disbursed",),
        target_status="Repledged",
        execution_mode="renewal-flow",
        notes="Used when a disbursed loan is renewed/repledged while collateral remains in custody.",
    ),
    "undo_repledge": TransitionStateSpec(
        key="undo_repledge",
        display_name="Undo Repledge",
        source_statuses=("Repledged",),
        target_status="Disbursed",
        execution_mode="reversal-transition",
        notes="Cancels the renewal linkage and returns the source loan to Disbursed.",
    ),
    # Next-generation lifecycle contract (implementation scaffold)
    "submit_for_approval": TransitionStateSpec(
        key="submit_for_approval",
        display_name="Submit for Approval",
        source_statuses=("Draft",),
        target_status="PendingApproval",
        execution_mode="approval-flow",
        notes="Moves a draft loan into checker review once borrower, collateral, and terms are present.",
    ),
    "approve_loan": TransitionStateSpec(
        key="approve_loan",
        display_name="Approve Loan",
        source_statuses=("PendingApproval",),
        target_status="Approved",
        execution_mode="approval-flow",
        notes="Final approval step before disbursal; commercial edits should stop after this transition.",
    ),
    "reject_loan": TransitionStateSpec(
        key="reject_loan",
        display_name="Reject Loan",
        source_statuses=("PendingApproval",),
        target_status="Rejected",
        execution_mode="approval-flow",
        notes="Ends the loan request without activation; a rejection reason is mandatory.",
    ),
    "cancel_loan": TransitionStateSpec(
        key="cancel_loan",
        display_name="Cancel Loan",
        source_statuses=("Draft", "PendingApproval"),
        target_status="Cancelled",
        execution_mode="generic-transition",
        notes="Cancels a loan before it reaches the active servicing lifecycle.",
    ),
    "disburse_loan": TransitionStateSpec(
        key="disburse_loan",
        display_name="Disburse Loan",
        source_statuses=("Approved",),
        target_status="ActiveCurrent",
        execution_mode="transition-with-accounting",
        notes="Activates the loan and posts the disbursal entry.",
    ),
    "undo_disbursal": TransitionStateSpec(
        key="undo_disbursal",
        display_name="Undo Disbursal",
        source_statuses=("ActiveCurrent",),
        target_status="Approved",
        execution_mode="reversal-transition",
        notes="Restricted reversal that pulls an active current loan back to Approved.",
    ),
    "mark_overdue": TransitionStateSpec(
        key="mark_overdue",
        display_name="Mark Overdue",
        source_statuses=("ActiveCurrent",),
        target_status="ActiveOverdue",
        execution_mode="system-transition",
        notes="Moves the loan from performing to overdue servicing based on DPD policy.",
    ),
    "cure_to_current": TransitionStateSpec(
        key="cure_to_current",
        display_name="Cure to Current",
        source_statuses=("ActiveOverdue", "ActiveNPA"),
        target_status="ActiveCurrent",
        execution_mode="system-transition",
        notes="Returns the loan to current once overdue/default conditions are cured.",
    ),
    "mark_npa": TransitionStateSpec(
        key="mark_npa",
        display_name="Mark NPA",
        source_statuses=("ActiveOverdue",),
        target_status="ActiveNPA",
        execution_mode="warning-transition",
        notes="Escalates an overdue loan into the non-performing bucket under policy rules.",
    ),
    "request_closure": TransitionStateSpec(
        key="request_closure",
        display_name="Request Closure",
        source_statuses=("ActiveCurrent", "ActiveOverdue", "ActiveNPA"),
        target_status="ClosurePending",
        execution_mode="closure-flow",
        notes="Financial closure eligibility is satisfied and the operational release workflow can start.",
    ),
    "complete_closure": TransitionStateSpec(
        key="complete_closure",
        display_name="Complete Closure",
        source_statuses=("ClosurePending",),
        target_status="Closed",
        execution_mode="closure-flow",
        notes="Closure is finalized after release creation, custody return, delivery, and posting succeed.",
    ),
    "reopen_from_closure_pending": TransitionStateSpec(
        key="reopen_from_closure_pending",
        display_name="Reopen from Closure Pending",
        source_statuses=("ClosurePending",),
        target_status="ActiveCurrent",
        execution_mode="reversal-transition",
        notes="Backs out of the pending closure stage when dues or custody checks fail before final closure.",
    ),
    "request_renewal": TransitionStateSpec(
        key="request_renewal",
        display_name="Request Renewal",
        source_statuses=("ActiveCurrent", "ActiveOverdue", "ActiveNPA"),
        target_status="RenewalPending",
        execution_mode="renewal-flow",
        notes="Starts the renewal review workflow before the successor loan is finalized.",
    ),
    "complete_renewal": TransitionStateSpec(
        key="complete_renewal",
        display_name="Complete Renewal",
        source_statuses=("RenewalPending",),
        target_status="Renewed",
        execution_mode="renewal-flow",
        notes="Completes the renewal atomically and links the successor loan to the source loan.",
    ),
    "cancel_renewal_request": TransitionStateSpec(
        key="cancel_renewal_request",
        display_name="Cancel Renewal Request",
        source_statuses=("RenewalPending",),
        target_status="ActiveCurrent",
        execution_mode="reversal-transition",
        notes="Returns the loan to the active servicing lifecycle when the pending renewal is aborted.",
    ),
    "initiate_auction": TransitionStateSpec(
        key="initiate_auction",
        display_name="Initiate Auction",
        source_statuses=("ActiveNPA",),
        target_status="AuctionInitiated",
        execution_mode="auction-flow",
        notes="Administrative start of the recovery-by-auction process for an NPA loan.",
    ),
    "start_auction": TransitionStateSpec(
        key="start_auction",
        display_name="Start Auction",
        source_statuses=("AuctionInitiated",),
        target_status="AuctionInProgress",
        execution_mode="auction-flow",
        notes="Auction operations have formally started and are underway.",
    ),
    "cancel_auction": TransitionStateSpec(
        key="cancel_auction",
        display_name="Cancel Auction",
        source_statuses=("AuctionInitiated",),
        target_status="ActiveNPA",
        execution_mode="reversal-transition",
        notes="Returns the loan to Active NPA when the auction is stopped before meaningful progression.",
    ),
    "complete_auction": TransitionStateSpec(
        key="complete_auction",
        display_name="Complete Auction",
        source_statuses=("AuctionInProgress",),
        target_status="AuctionComplete",
        execution_mode="auction-flow",
        notes="Auction recovery has concluded and the realized amount is now known.",
    ),
    "close_after_auction": TransitionStateSpec(
        key="close_after_auction",
        display_name="Close After Auction",
        source_statuses=("AuctionComplete",),
        target_status="Closed",
        execution_mode="auction-flow",
        notes="Used when auction recovery fully settles the outstanding balance.",
    ),
    "write_off_loan": TransitionStateSpec(
        key="write_off_loan",
        display_name="Write Off Loan",
        source_statuses=("ActiveNPA", "AuctionComplete"),
        target_status="WrittenOff",
        execution_mode="loss-recognition-flow",
        notes="Terminates the loan with loss recognition once the unrecoverable balance is approved for write-off.",
    ),
}


TRANSITION_UI_REGISTRY: dict[str, TransitionUISpec] = {
    "approve": TransitionUISpec("approve", "Approve", "btn-success", "✓"),
    "disburse": TransitionUISpec("disburse", "Disburse Funds", "btn-primary", "💳"),
    "deliver": TransitionUISpec("deliver", "Release to Customer", "btn-info", "📦"),
    "cancel": TransitionUISpec("cancel", "Cancel", "btn-danger", "✕"),
    "mark_defaulted": TransitionUISpec(
        "mark_defaulted", "Mark Defaulted", "btn-warning", "⚠"
    ),
    "mark_auctioned": TransitionUISpec(
        "mark_auctioned", "Record Auction", "btn-dark", "🔨"
    ),
    "mark_sold": TransitionUISpec("mark_sold", "Record Sale", "btn-secondary", "💰"),
    "repledge": TransitionUISpec("repledge", "Mark Repledged", "btn-info", "🔁"),
    "undo_disburse": TransitionUISpec(
        "undo_disburse", "Undo Disbursal", "btn-outline-warning", "↩"
    ),
    "undo_release": TransitionUISpec(
        "undo_release", "Undo Release", "btn-outline-secondary", "↩"
    ),
    "undo_repledge": TransitionUISpec(
        "undo_repledge", "Undo Repledge", "btn-outline-secondary", "↩"
    ),
    "submit_for_approval": TransitionUISpec("submit_for_approval", "Submit for Approval", "btn-primary", "📝"),
    "approve_loan": TransitionUISpec("approve_loan", "Approve Loan", "btn-success", "✓"),
    "reject_loan": TransitionUISpec("reject_loan", "Reject Loan", "btn-danger", "✕"),
    "cancel_loan": TransitionUISpec("cancel_loan", "Cancel Loan", "btn-danger", "✕"),
    "disburse_loan": TransitionUISpec("disburse_loan", "Disburse Loan", "btn-primary", "💳"),
    "undo_disbursal": TransitionUISpec("undo_disbursal", "Undo Disbursal", "btn-outline-warning", "↩"),
    "mark_overdue": TransitionUISpec("mark_overdue", "Mark Overdue", "btn-warning", "⏰"),
    "cure_to_current": TransitionUISpec("cure_to_current", "Cure to Current", "btn-success", "✔"),
    "mark_npa": TransitionUISpec("mark_npa", "Mark NPA", "btn-dark", "⚠"),
    "request_closure": TransitionUISpec("request_closure", "Request Closure", "btn-info", "📦"),
    "complete_closure": TransitionUISpec("complete_closure", "Complete Closure", "btn-success", "✅"),
    "reopen_from_closure_pending": TransitionUISpec("reopen_from_closure_pending", "Reopen Closure", "btn-outline-secondary", "↩"),
    "request_renewal": TransitionUISpec("request_renewal", "Request Renewal", "btn-info", "🔁"),
    "complete_renewal": TransitionUISpec("complete_renewal", "Complete Renewal", "btn-success", "🔁"),
    "cancel_renewal_request": TransitionUISpec("cancel_renewal_request", "Cancel Renewal", "btn-outline-secondary", "↩"),
    "initiate_auction": TransitionUISpec("initiate_auction", "Initiate Auction", "btn-dark", "🔨"),
    "start_auction": TransitionUISpec("start_auction", "Start Auction", "btn-dark", "▶"),
    "cancel_auction": TransitionUISpec("cancel_auction", "Cancel Auction", "btn-outline-secondary", "↩"),
    "complete_auction": TransitionUISpec("complete_auction", "Complete Auction", "btn-dark", "🏁"),
    "close_after_auction": TransitionUISpec("close_after_auction", "Close After Auction", "btn-success", "✅"),
    "write_off_loan": TransitionUISpec("write_off_loan", "Write Off Loan", "btn-danger", "🧾"),
}


TRANSITION_FORM_UI_REGISTRY: dict[str, TransitionFormUISpec] = {
    "approve": TransitionFormUISpec("approve", "Approve Loan", "✓", "bg-success"),
    "disburse": TransitionFormUISpec(
        "disburse", "Disburse Loan", "💳", "bg-primary"
    ),
    "cancel": TransitionFormUISpec("cancel", "Cancel Loan", "✕", "bg-danger"),
    "mark_defaulted": TransitionFormUISpec(
        "mark_defaulted", "Mark as Defaulted", "⚠", "bg-warning"
    ),
    "mark_auctioned": TransitionFormUISpec(
        "mark_auctioned", "Record Auction", "🔨", "bg-dark"
    ),
    "mark_sold": TransitionFormUISpec("mark_sold", "Record Sale", "💰", "bg-secondary"),
    "repledge": TransitionFormUISpec("repledge", "Repledge Loan", "🔁", "bg-info"),
    "undo_disburse": TransitionFormUISpec(
        "undo_disburse", "Undo Disbursal", "↩", "bg-warning"
    ),
    "undo_release": TransitionFormUISpec(
        "undo_release", "Undo Release", "↩", "bg-secondary"
    ),
    "undo_repledge": TransitionFormUISpec(
        "undo_repledge", "Undo Repledge", "↩", "bg-secondary"
    ),
    "submit_for_approval": TransitionFormUISpec("submit_for_approval", "Submit for Approval", "📝", "bg-primary"),
    "approve_loan": TransitionFormUISpec("approve_loan", "Approve Loan", "✓", "bg-success"),
    "reject_loan": TransitionFormUISpec("reject_loan", "Reject Loan", "✕", "bg-danger"),
    "cancel_loan": TransitionFormUISpec("cancel_loan", "Cancel Loan", "✕", "bg-danger"),
    "disburse_loan": TransitionFormUISpec("disburse_loan", "Disburse Loan", "💳", "bg-primary"),
    "undo_disbursal": TransitionFormUISpec("undo_disbursal", "Undo Disbursal", "↩", "bg-warning"),
    "mark_overdue": TransitionFormUISpec("mark_overdue", "Mark Overdue", "⏰", "bg-warning"),
    "cure_to_current": TransitionFormUISpec("cure_to_current", "Cure to Current", "✔", "bg-success"),
    "mark_npa": TransitionFormUISpec("mark_npa", "Mark NPA", "⚠", "bg-dark"),
    "request_closure": TransitionFormUISpec("request_closure", "Request Closure", "📦", "bg-info"),
    "complete_closure": TransitionFormUISpec("complete_closure", "Complete Closure", "✅", "bg-success"),
    "reopen_from_closure_pending": TransitionFormUISpec("reopen_from_closure_pending", "Reopen Closure", "↩", "bg-secondary"),
    "request_renewal": TransitionFormUISpec("request_renewal", "Request Renewal", "🔁", "bg-info"),
    "complete_renewal": TransitionFormUISpec("complete_renewal", "Complete Renewal", "🔁", "bg-success"),
    "cancel_renewal_request": TransitionFormUISpec("cancel_renewal_request", "Cancel Renewal", "↩", "bg-secondary"),
    "initiate_auction": TransitionFormUISpec("initiate_auction", "Initiate Auction", "🔨", "bg-dark"),
    "start_auction": TransitionFormUISpec("start_auction", "Start Auction", "▶", "bg-dark"),
    "cancel_auction": TransitionFormUISpec("cancel_auction", "Cancel Auction", "↩", "bg-secondary"),
    "complete_auction": TransitionFormUISpec("complete_auction", "Complete Auction", "🏁", "bg-dark"),
    "close_after_auction": TransitionFormUISpec("close_after_auction", "Close After Auction", "✅", "bg-success"),
    "write_off_loan": TransitionFormUISpec("write_off_loan", "Write Off Loan", "🧾", "bg-danger"),
}


def normalize_transition_name(raw_name: str | None) -> str:
    if not raw_name:
        return ""
    cleaned = str(raw_name).strip()
    return TRANSITION_ALIAS_MAP.get(cleaned, cleaned)


def get_transition_form_class(transition_name: str):
    from django.utils.module_loading import import_string

    transition_name = normalize_transition_name(transition_name)
    spec = TRANSITION_REGISTRY.get(transition_name)
    if not spec or not spec.enabled_in_loan_transition_view:
        return None
    return import_string(spec.form_class_path)


def get_transition_command(transition_name: str):
    transition_name = normalize_transition_name(transition_name)
    spec = TRANSITION_REGISTRY.get(transition_name)
    if spec and spec.command_class:
        return spec.command_class
    return get_transition_command_class(transition_name)


def build_transition_payload(transition_name: str, payload_dict: dict):
    from django.utils.module_loading import import_string

    transition_name = normalize_transition_name(transition_name)
    spec = TRANSITION_REGISTRY.get(transition_name)
    if not spec or not spec.payload_class_path:
        if payload_dict:
            raise ValueError(
                f"No payload DTO is configured for transition '{transition_name}'."
            )
        return None

    payload_class = import_string(spec.payload_class_path)
    return payload_class(**payload_dict)


def get_transition_state_spec(transition_name: str) -> TransitionStateSpec | None:
    """Return the canonical state contract for a transition key or alias."""
    return TRANSITION_STATE_REGISTRY.get(normalize_transition_name(transition_name))


def build_transition_actions(loan, raw_transitions):
    """Build UI-ready transition action descriptors from outgoing transition labels."""
    actions = []
    for raw in raw_transitions:
        key = normalize_transition_name(str(raw))
        key = resolve_runtime_transition_name(loan, key)
        spec = TRANSITION_REGISTRY.get(key)
        if spec and not spec.enabled_in_loan_transition_view:
            continue

        ui = TRANSITION_UI_REGISTRY.get(
            key,
            TransitionUISpec(
                key=key,
                title=key.replace("_", " ").title(),
                button_class="btn-outline-secondary",
                icon="→",
            ),
        )

        if key == "deliver":
            actions.append(
                {
                    "key": key,
                    "title": ui.title,
                    "button_class": ui.button_class,
                    "icon": ui.icon,
                    "is_htmx": True,
                    "hx_get": reverse("girvi:release_loan_check_custody", args=[loan.id]),
                }
            )
            continue

        actions.append(
            {
                "key": key,
                "title": ui.title,
                "button_class": ui.button_class,
                "icon": ui.icon,
                "is_htmx": False,
                "href": f"{reverse('girvi:girvi_loan_transition', args=[loan.pk])}?transition={key}",
            }
        )

    return actions


def get_transition_form_ui(transition_name: str) -> TransitionFormUISpec:
    """Return form-page UI metadata for a transition, with safe default fallback."""
    key = normalize_transition_name(transition_name)
    return TRANSITION_FORM_UI_REGISTRY.get(
        key,
        TransitionFormUISpec(
            key=key,
            heading=key.replace("_", " ").title() if key else "Transition",
            icon="→",
            badge_class="bg-secondary",
        ),
    )
