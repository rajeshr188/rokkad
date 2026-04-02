from django.test import SimpleTestCase

from apps.tenant_apps.girvi.transition_registry import (
    build_transition_payload,
    TRANSITION_REGISTRY,
    get_transition_form_ui,
    get_transition_form_class,
    normalize_transition_name,
)
from apps.tenant_apps.girvi.transitions.payloads import CancelPayload


class TransitionRegistryTests(SimpleTestCase):
    def test_mark_sold_alias_is_normalized(self):
        self.assertEqual(normalize_transition_name("mark sold"), "mark_sold")

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

    def test_build_transition_payload_returns_typed_dto(self):
        payload = build_transition_payload(
            "cancel",
            {"cancelled_by": "alice", "reason": "duplicate entry"},
        )
        self.assertIsInstance(payload, CancelPayload)
        self.assertEqual(payload.cancelled_by, "alice")
        self.assertEqual(payload.reason, "duplicate entry")
