from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import LoanStatus
from apps.tenant_apps.girvi.transition_registry import (
    build_transition_actions,
    build_transition_payload,
    LEGACY_TRANSITION_FORM_UI_COMPAT_REGISTRY,
    LEGACY_TRANSITION_STATE_COMPAT_REGISTRY,
    LEGACY_TRANSITION_UI_COMPAT_REGISTRY,
    TRANSITION_FORM_UI_REGISTRY,
    TRANSITION_REGISTRY,
    TRANSITION_STATE_REGISTRY,
    TRANSITION_UI_REGISTRY,
    get_transition_form_ui,
    get_transition_form_class,
    get_transition_state_spec,
    normalize_transition_name,
)
from apps.tenant_apps.girvi.transitions.payloads import CancelPayload


class _DummyLoan:
    pk = 99
    id = 99

    def __init__(self, status=None, loan_type="Given"):
        self.status = status
        self.loan_type = loan_type


class TransitionRegistryTests(SimpleTestCase):
    def test_mark_sold_alias_is_normalized(self):
        self.assertEqual(normalize_transition_name("mark sold"), "mark_sold")

    def test_release_alias_is_normalized_to_deliver(self):
        self.assertEqual(normalize_transition_name("release"), "request_closure")

    def test_registry_has_core_given_loan_transitions(self):
        expected = {
            "submit_for_approval",
            "approve_loan",
            "reject_loan",
            "cancel_loan",
            "disburse_loan",
            "undo_disbursal",
            "mark_npa",
            "request_closure",
            "request_renewal",
            "complete_auction",
            "write_off_loan",
        }
        self.assertTrue(expected.issubset(set(TRANSITION_REGISTRY.keys())))

    def test_legacy_approve_alias_resolves_to_canonical_form(self):
        self.assertIs(get_transition_form_class("approve"), get_transition_form_class("approve_loan"))

    def test_transition_form_ui_metadata_exists_for_registered_transition(self):
        ui = get_transition_form_ui("mark_sold")
        self.assertEqual(ui.heading, "Record Sale")
        self.assertEqual(ui.icon, "💰")
        self.assertEqual(ui.badge_class, "bg-secondary")

    def test_transition_state_spec_clarifies_release_contract(self):
        spec = get_transition_state_spec("release")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key, "request_closure")
        self.assertEqual(spec.target_status, "ClosurePending")
        self.assertEqual(spec.execution_mode, "closure-flow")

    def test_transition_state_spec_supports_new_closure_flow(self):
        spec = get_transition_state_spec("request_closure")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.key, "request_closure")
        self.assertEqual(spec.target_status, "ClosurePending")
        self.assertEqual(spec.execution_mode, "closure-flow")

    def test_build_transition_payload_returns_typed_dto(self):
        payload = build_transition_payload(
            "cancel_loan",
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

    def test_build_transition_actions_canonicalizes_taken_disburse_alias(self):
        actions = build_transition_actions(
            _DummyLoan(status="Draft", loan_type="Taken"),
            ["disburse"],
        )

        self.assertEqual([action["key"] for action in actions], ["activate"])
        self.assertEqual(actions[0]["title"], "Activate Taken Loan")
        self.assertIn("transition=activate", actions[0]["href"])

    def test_taken_loan_transition_state_specs_are_canonical(self):
        activate = get_transition_state_spec("activate")
        settlement = get_transition_state_spec("request_settlement")
        complete = get_transition_state_spec("complete_settlement")

        self.assertEqual(activate.target_status, "Active")
        self.assertEqual(activate.execution_mode, "transition-with-accounting")
        self.assertEqual(settlement.target_status, "SettlementPending")
        self.assertEqual(complete.target_status, "Closed")

    def test_legacy_keys_are_not_primary_registry_entries(self):
        self.assertNotIn("approve", TRANSITION_REGISTRY)
        self.assertNotIn("disburse", TRANSITION_REGISTRY)
        self.assertNotIn("cancel", TRANSITION_REGISTRY)

    def test_legacy_keys_are_not_primary_ui_or_state_entries(self):
        legacy_keys = {
            "approve",
            "disburse",
            "deliver",
            "cancel",
            "mark_defaulted",
            "mark_auctioned",
            "undo_disburse",
        }

        self.assertTrue(legacy_keys.isdisjoint(TRANSITION_STATE_REGISTRY))
        self.assertTrue(legacy_keys.isdisjoint(TRANSITION_UI_REGISTRY))
        self.assertTrue(legacy_keys.isdisjoint(TRANSITION_FORM_UI_REGISTRY))

    def test_legacy_only_transition_metadata_is_explicitly_compatibility_scoped(self):
        for key in {"mark_sold", "repledge", "undo_release", "undo_repledge"}:
            self.assertNotIn(key, TRANSITION_STATE_REGISTRY)
            self.assertNotIn(key, TRANSITION_UI_REGISTRY)
            self.assertNotIn(key, TRANSITION_FORM_UI_REGISTRY)
            self.assertIn(key, LEGACY_TRANSITION_STATE_COMPAT_REGISTRY)
            self.assertIn(key, LEGACY_TRANSITION_UI_COMPAT_REGISTRY)
            self.assertIn(key, LEGACY_TRANSITION_FORM_UI_COMPAT_REGISTRY)
