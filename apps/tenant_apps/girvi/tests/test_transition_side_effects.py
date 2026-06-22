from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
from apps.tenant_apps.girvi.service_modules.transition_side_effects import (
    execute_disbursal_transition,
    execute_recovery_transition,
    parse_recovery_amount,
)


class TransitionSideEffectsTests(SimpleTestCase):
    def test_parse_recovery_amount_normalizes_amount_key(self):
        payload = {"amount": 150}

        parsed = parse_recovery_amount(
            payload,
            missing_message="missing",
            non_positive_message="non-positive",
        )

        self.assertEqual(parsed.amount, 150)
        self.assertEqual(payload["recovery_amount"], 150)
        self.assertNotIn("amount", payload)

    def test_parse_recovery_amount_rejects_non_positive(self):
        payload = {"recovery_amount": 0}

        parsed = parse_recovery_amount(
            payload,
            missing_message="missing",
            non_positive_message="non-positive",
        )

        self.assertEqual(parsed.error_message, "non-positive")

    def test_execute_disbursal_transition_posts_when_status_is_active(self):
        loan = SimpleNamespace(status=LoanLifecycleState.APPROVED)

        def transition_method(**_kwargs):
            loan.status = LoanLifecycleState.ACTIVE_CURRENT

        post_disbursal = MagicMock(return_value=(SimpleNamespace(payment_id="PV-1"), True))

        with patch(
            "apps.tenant_apps.girvi.service_modules.transition_side_effects.transaction.atomic",
            return_value=nullcontext(),
        ):
            result = execute_disbursal_transition(
                loan=loan,
                user=SimpleNamespace(),
                transition_method=transition_method,
                payload_kwargs={},
                active_statuses={LoanLifecycleState.ACTIVE_CURRENT},
                post_disbursal=post_disbursal,
            )

        self.assertTrue(result.success)
        self.assertIn("posted", result.message)
        post_disbursal.assert_called_once()

    def test_execute_recovery_transition_posts_when_status_matches_success(self):
        loan = SimpleNamespace(status=LoanLifecycleState.AUCTION_IN_PROGRESS)
        user = SimpleNamespace()

        def transition_method(**_kwargs):
            loan.status = LoanLifecycleState.AUCTION_COMPLETE

        post_recovery = MagicMock(return_value=(SimpleNamespace(payment_id="RV-1"), True))

        with patch(
            "apps.tenant_apps.girvi.service_modules.transition_side_effects.transaction.atomic",
            return_value=nullcontext(),
        ):
            result = execute_recovery_transition(
                loan=loan,
                user=user,
                transition_method=transition_method,
                payload_kwargs={"recovery_amount": 250},
                success_status=LoanLifecycleState.AUCTION_COMPLETE,
                post_recovery=post_recovery,
                posted_message="posted {payment_id}",
                existing_message="existing {payment_id}",
            )

        self.assertTrue(result.success)
        self.assertIn("posted RV-1", result.message)
        post_recovery.assert_called_once_with(loan, 250, user)
