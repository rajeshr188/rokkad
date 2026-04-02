from django.test import SimpleTestCase

from apps.tenant_apps.girvi.flows import LoanFlow
from apps.tenant_apps.girvi.models.loan_refactored import LoanStatus
from apps.tenant_apps.girvi.transition_registry import (
    TRANSITION_REGISTRY,
    normalize_transition_name,
)


class _DummyLoan:
    def __init__(self, status):
        self.status = status

    def save(self):
        return None


class _DummyUser:
    pass


class LoanFlowMatrixTests(SimpleTestCase):
    def _outgoing_keys(self, status):
        flow = LoanFlow(_DummyLoan(status=status), _DummyUser(), tenant=None)
        return {
            normalize_transition_name(str(t.label))
            for t in flow.get_outgoing_transitions()
        }

    def test_created_outgoing_transitions(self):
        self.assertEqual(self._outgoing_keys(LoanStatus.CREATED), {"approve", "cancel"})

    def test_approved_outgoing_transitions(self):
        self.assertEqual(self._outgoing_keys(LoanStatus.APPROVED), {"disburse", "cancel"})

    def test_disbursed_outgoing_transitions(self):
        self.assertEqual(
            self._outgoing_keys(LoanStatus.DISBURSED),
            {
                "deliver",
                "undo_disburse",
                "mark_defaulted",
                "mark_sold",
                "repledge",
            },
        )

    def test_released_outgoing_transitions(self):
        self.assertEqual(self._outgoing_keys(LoanStatus.RELEASED), {"undo_release"})

    def test_repledged_outgoing_transitions(self):
        self.assertEqual(self._outgoing_keys(LoanStatus.REPLEDGED), {"undo_repledge"})

    def test_defaulted_outgoing_transitions(self):
        self.assertEqual(self._outgoing_keys(LoanStatus.DEFAULTED), {"mark_auctioned"})

    def test_every_non_deliver_outgoing_transition_is_registered(self):
        statuses = [
            LoanStatus.CREATED,
            LoanStatus.APPROVED,
            LoanStatus.DISBURSED,
            LoanStatus.RELEASED,
            LoanStatus.REPLEDGED,
            LoanStatus.DEFAULTED,
        ]
        all_outgoing = set()
        for status in statuses:
            all_outgoing.update(self._outgoing_keys(status))

        all_outgoing.discard("deliver")  # handled via Release flow endpoint
        missing = sorted(all_outgoing.difference(set(TRANSITION_REGISTRY.keys())))
        self.assertEqual(missing, [])
