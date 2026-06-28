from contextlib import nullcontext
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
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

    def test_execute_disbursal_transition_persists_givenloan_deduction_fields(self):
        loan = SimpleNamespace(
            status=LoanLifecycleState.APPROVED,
            get_loan_amount=Decimal("1000.00"),
            disbursal_upfront_interest_deduction=Decimal("0.00"),
            disbursal_document_charge=Decimal("0.00"),
            save=MagicMock(),
        )

        def transition_method(**_kwargs):
            loan.status = LoanLifecycleState.ACTIVE_CURRENT

        with patch(
            "apps.tenant_apps.girvi.service_modules.transition_side_effects.transaction.atomic",
            return_value=nullcontext(),
        ):
            execute_disbursal_transition(
                loan=loan,
                user=SimpleNamespace(),
                transition_method=transition_method,
                payload_kwargs={
                    "disbursed_by": "cashier",
                    "upfront_interest_deduction": Decimal("100.00"),
                    "document_charge": Decimal("25.00"),
                },
                active_statuses={LoanLifecycleState.ACTIVE_CURRENT},
                post_disbursal=MagicMock(return_value=(SimpleNamespace(payment_id="PV-2"), True)),
            )

        self.assertEqual(loan.disbursal_upfront_interest_deduction, Decimal("100.00"))
        self.assertEqual(loan.disbursal_document_charge, Decimal("25.00"))
        loan.save.assert_called_once_with(
            update_fields=[
                "disbursal_upfront_interest_deduction",
                "disbursal_document_charge",
            ]
        )

    def test_execute_disbursal_transition_rejects_deductions_exceeding_principal(self):
        loan = SimpleNamespace(
            status=LoanLifecycleState.APPROVED,
            get_loan_amount=Decimal("100.00"),
            disbursal_upfront_interest_deduction=Decimal("0.00"),
            disbursal_document_charge=Decimal("0.00"),
            save=MagicMock(),
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.transition_side_effects.transaction.atomic",
            return_value=nullcontext(),
        ):
            with self.assertRaisesMessage(
                ValidationError,
                "cannot exceed the loan principal",
            ):
                execute_disbursal_transition(
                    loan=loan,
                    user=SimpleNamespace(),
                    transition_method=MagicMock(),
                    payload_kwargs={
                        "disbursed_by": "cashier",
                        "upfront_interest_deduction": Decimal("80.00"),
                        "document_charge": Decimal("30.00"),
                    },
                    active_statuses={LoanLifecycleState.ACTIVE_CURRENT},
                    post_disbursal=MagicMock(return_value=(SimpleNamespace(payment_id="PV-3"), True)),
                )

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
