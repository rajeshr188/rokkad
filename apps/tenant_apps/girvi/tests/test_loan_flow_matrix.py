from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.flows import (
    GivenLoanFlow,
    TakenLoanFlow,
    normalize_legacy_given_loan_status,
    normalize_legacy_taken_loan_status,
)
from apps.tenant_apps.girvi.lifecycle import (
    lifecycle_status_badge_class,
    lifecycle_status_label,
)
from apps.tenant_apps.girvi.models.loan_refactored import (
    LoanLifecycleState,
    LoanStatus,
    TakenLoanLifecycleState,
)
from apps.tenant_apps.girvi.selectors import build_unified_loan_rows
from apps.tenant_apps.girvi.transition_registry import (
    TRANSITION_REGISTRY,
    TRANSITION_STATE_REGISTRY,
    get_transition_state_spec,
    normalize_transition_name,
)


class _DummyLoan:
    def __init__(self, status, loan_type="Given"):
        self.status = status
        self.loan_type = loan_type

    def save(self, *args, **kwargs):
        return None


class _DummyUser:
    pass


class GivenLoanFlowMatrixTests(SimpleTestCase):
    def _outgoing_keys(self, status):
        flow = GivenLoanFlow(_DummyLoan(status=status), _DummyUser(), tenant=None)
        return {
            normalize_transition_name(str(t.label))
            for t in flow.get_outgoing_transitions()
        }

    def test_draft_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.DRAFT),
            {"submit_for_approval", "cancel_loan"},
        )

    def test_legacy_created_status_maps_to_canonical_draft_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanStatus.CREATED),
            {"submit_for_approval", "cancel_loan"},
        )

    def test_pending_approval_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.PENDING_APPROVAL),
            {"return_to_draft", "approve_loan", "reject_loan", "cancel_loan"},
        )

    def test_approved_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.APPROVED),
            {"disburse_loan"},
        )

    def test_active_current_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.ACTIVE_CURRENT),
            {
                "undo_disbursal",
                "mark_overdue",
                "request_closure",
                "request_renewal",
            },
        )

    def test_active_npa_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.ACTIVE_NPA),
            {
                "cure_to_current",
                "request_closure",
                "request_renewal",
                "initiate_auction",
                "write_off_loan",
            },
        )

    def test_closure_pending_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanLifecycleState.CLOSURE_PENDING),
            {"complete_closure", "reopen_from_closure_pending"},
        )

    def test_every_exposed_given_transition_is_registered(self):
        statuses = [
            LoanLifecycleState.DRAFT,
            LoanLifecycleState.PENDING_APPROVAL,
            LoanLifecycleState.APPROVED,
            LoanLifecycleState.ACTIVE_CURRENT,
            LoanLifecycleState.ACTIVE_OVERDUE,
            LoanLifecycleState.ACTIVE_NPA,
            LoanLifecycleState.CLOSURE_PENDING,
            LoanLifecycleState.RENEWAL_PENDING,
            LoanLifecycleState.AUCTION_INITIATED,
            LoanLifecycleState.AUCTION_IN_PROGRESS,
            LoanLifecycleState.AUCTION_COMPLETE,
        ]
        all_outgoing = set()
        for status in statuses:
            all_outgoing.update(self._outgoing_keys(status))

        missing = sorted(all_outgoing.difference(set(TRANSITION_REGISTRY.keys())))
        self.assertEqual(missing, [])


class TakenLoanFlowMatrixTests(SimpleTestCase):
    def _outgoing_keys(self, status):
        flow = TakenLoanFlow(
            _DummyLoan(status=status, loan_type="Taken"),
            _DummyUser(),
            tenant=None,
        )
        return {
            normalize_transition_name(str(t.label))
            for t in flow.get_outgoing_transitions()
        }

    def test_draft_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(TakenLoanLifecycleState.DRAFT),
            {"activate", "cancel_loan"},
        )

    def test_active_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(TakenLoanLifecycleState.ACTIVE),
            {"request_settlement"},
        )

    def test_settlement_pending_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(TakenLoanLifecycleState.SETTLEMENT_PENDING),
            {"complete_settlement"},
        )

    def test_legacy_status_maps_to_minimal_taken_lifecycle(self):
        self.assertEqual(
            normalize_legacy_taken_loan_status(LoanStatus.DISBURSED),
            TakenLoanLifecycleState.ACTIVE,
        )


def _status_value(status):
    return getattr(status, "value", str(status))


def _flow_transition_matrix(flow_cls):
    matrix = {}
    for transitions in flow_cls.status.get_transitions().values():
        for transition in transitions:
            key = normalize_transition_name(str(transition.label))
            matrix.setdefault(
                key,
                {
                    "sources": set(),
                    "targets": set(),
                },
            )
            matrix[key]["sources"].add(_status_value(transition.source))
            matrix[key]["targets"].add(_status_value(transition.target))
    return matrix


class FlowTransitionRegistryContractTests(SimpleTestCase):
    def test_flow_transitions_have_matching_registry_state_specs(self):
        for flow_cls in (GivenLoanFlow, TakenLoanFlow):
            matrix = _flow_transition_matrix(flow_cls)
            for key, observed in matrix.items():
                with self.subTest(flow=flow_cls.__name__, transition=key):
                    self.assertIn(key, TRANSITION_REGISTRY)

                    spec = get_transition_state_spec(key)
                    self.assertIsNotNone(spec)
                    self.assertEqual(observed["targets"], {spec.target_status})
                    self.assertTrue(
                        observed["sources"].issubset(set(spec.source_statuses)),
                        f"{key} source mismatch: observed={observed['sources']} "
                        f"documented={set(spec.source_statuses)}",
                    )

    def test_canonical_state_registry_matches_flow_transition_matrix(self):
        observed_keys = set()
        for flow_cls in (GivenLoanFlow, TakenLoanFlow):
            observed_keys.update(_flow_transition_matrix(flow_cls).keys())

        self.assertEqual(observed_keys, set(TRANSITION_STATE_REGISTRY.keys()))


class LifecycleMappingTests(SimpleTestCase):
    def test_given_legacy_mapping(self):
        self.assertEqual(
            normalize_legacy_given_loan_status(LoanStatus.RELEASED),
            LoanLifecycleState.CLOSED,
        )

    def test_taken_legacy_mapping(self):
        self.assertEqual(
            normalize_legacy_taken_loan_status(LoanStatus.AUCTIONED),
            TakenLoanLifecycleState.ACTIVE,
        )

    def test_given_lifecycle_display_uses_canonical_labels(self):
        self.assertEqual(
            lifecycle_status_label(LoanStatus.DISBURSED),
            "Active Current",
        )
        self.assertEqual(
            lifecycle_status_badge_class(LoanStatus.DISBURSED),
            "bg-primary",
        )

    def test_taken_lifecycle_display_uses_taken_mapping(self):
        self.assertEqual(
            lifecycle_status_label(LoanStatus.DISBURSED, loan_kind="taken"),
            "Active",
        )
        self.assertEqual(
            lifecycle_status_label(
                TakenLoanLifecycleState.SETTLEMENT_PENDING,
                loan_kind="taken",
            ),
            "Settlement Pending",
        )

    def test_unified_loan_rows_include_canonical_status_labels(self):
        borrower = SimpleNamespace(name="Borrower")
        lender = SimpleNamespace(name="Lender")
        given = SimpleNamespace(
            id=1,
            loan_id="G-1",
            loan_date=1,
            borrower=borrower,
            status=LoanStatus.DISBURSED,
            get_loan_amount=100,
        )
        taken = SimpleNamespace(
            id=2,
            loan_id="T-1",
            loan_date=2,
            lender=lender,
            status=LoanStatus.DISBURSED,
            get_loan_amount=80,
        )

        rows = build_unified_loan_rows([given], [taken])

        self.assertEqual(rows[0]["status_label"], "Active")
        self.assertEqual(rows[1]["status_label"], "Active Current")
