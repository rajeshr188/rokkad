from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import LoanStatus
from apps.tenant_apps.girvi.transition_registry import (
    build_transition_actions,
    build_transition_payload,
    TRANSITION_REGISTRY,
    get_transition_form_ui,
    get_transition_form_class,
    get_transition_state_spec,
    normalize_transition_name,
)
from apps.tenant_apps.girvi.transitions.payloads import CancelPayload


class _DummyLoan:
    pk = 99
    id = 99

    def __init__(self, status=None):
        self.status = status


class TransitionRegistryTests(SimpleTestCase):
    def test_mark_sold_alias_is_normalized(self):
        self.assertEqual(normalize_transition_name("mark sold"), "mark_sold")

    def test_release_alias_is_normalized_to_deliver(self):
        self.assertEqual(normalize_transition_name("release"), "deliver")

    def test_registry_has_core_given_loan_transitions(self):
        expected = {
            "approve",
            "disburse",
            "cancel",
            "mark_defaulted",
            "mark_auctioned",
            "mark_sold",
            "undo_disburse",
            "undo_release",
            "repledge",
            "undo_repledge",
        }
        self.assertTrue(expected.issubset(set(TRANSITION_REGISTRY.keys())))

    def test_deliver_is_not_exposed_via_transition_view(self):
        self.assertIsNone(get_transition_form_class("deliver"))

    def test_transition_form_ui_metadata_exists_for_registered_transition(self):
        ui = get_transition_form_ui("mark_sold")
        self.assertEqual(ui.heading, "Record Sale")
        self.assertEqual(ui.icon, "💰")
        self.assertEqual(ui.badge_class, "bg-secondary")

    def test_transition_state_spec_clarifies_release_contract(self):
        spec = get_transition_state_spec("release")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key, "deliver")
        self.assertEqual(spec.target_status, "Released")
        self.assertEqual(spec.execution_mode, "release-flow")

    def test_transition_state_spec_supports_new_closure_flow(self):
        spec = get_transition_state_spec("request_closure")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key, "request_closure")
        self.assertEqual(spec.target_status, "ClosurePending")
        self.assertEqual(spec.execution_mode, "closure-flow")

    def test_build_transition_payload_returns_typed_dto(self):
        payload = build_transition_payload(
            "cancel",
            {"cancelled_by": "alice", "reason": "duplicate entry"},
        )
        self.assertIsInstance(payload, CancelPayload)
        self.assertEqual(payload.cancelled_by, "alice")
        self.assertEqual(payload.reason, "duplicate entry")

    def test_v2_transition_forms_are_exposed_for_generic_view(self):
        self.assertIsNotNone(get_transition_form_class("submit_for_approval"))
        self.assertIsNotNone(get_transition_form_class("request_closure"))
        self.assertIsNotNone(get_transition_form_class("request_renewal"))

    def test_build_transition_actions_includes_enabled_v2_actions(self):
        actions = build_transition_actions(
            _DummyLoan(),
            ["submit_for_approval", "request_closure"],
        )
        self.assertEqual([action["key"] for action in actions], [
            "submit_for_approval",
            "request_closure",
        ])
        self.assertTrue(all(action["is_htmx"] is False for action in actions))

    def test_build_transition_actions_canonicalizes_approved_disburse_to_v2_key(self):
        actions = build_transition_actions(
            _DummyLoan(status=LoanStatus.APPROVED),
            ["disburse"],
        )
        self.assertEqual([action["key"] for action in actions], ["disburse_loan"])
        self.assertIn("transition=disburse_loan", actions[0]["href"])
