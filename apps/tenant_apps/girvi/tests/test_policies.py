from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
from apps.tenant_apps.girvi.policies import (
    assert_loan_header_editable,
    can_edit_loan_header,
)


class GirviPolicyTests(SimpleTestCase):
    def test_draft_and_approved_loan_headers_are_editable(self):
        self.assertTrue(can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.DRAFT)))
        self.assertTrue(
            can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.APPROVED))
        )

    def test_active_and_closed_loan_headers_are_immutable(self):
        self.assertFalse(
            can_edit_loan_header(SimpleNamespace(status=LoanLifecycleState.ACTIVE_CURRENT))
        )
        with self.assertRaises(ValidationError):
            assert_loan_header_editable(
                SimpleNamespace(loan_id="GL-001", status=LoanLifecycleState.CLOSED)
            )
