"""Central registry for GivenLoan transition wiring.

This module intentionally separates:
1) legal state transitions (defined in LoanFlow), and
2) app-layer wiring (form class + endpoint support).

Keeping this map in one place reduces flow/view/template drift.
"""

from dataclasses import dataclass

from django.urls import reverse
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
