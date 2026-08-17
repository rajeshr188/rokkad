from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import PawnLoanState
from apps.tenant_apps.party.selectors import (
    get_workspace_customer_party_dashboard_summary,
)


class PartyDashboardSelectorTests(SimpleTestCase):
    @patch("apps.tenant_apps.party.selectors.parties_with_role")
    def test_active_customer_filter_uses_current_loans_domain_states(self, roles):
        customers = MagicMock()
        roles.return_value.distinct.return_value = customers
        customers.count.return_value = 0
        customers.filter.return_value.distinct.return_value.count.return_value = 0

        summary = get_workspace_customer_party_dashboard_summary()

        roles.assert_called_once_with("CUSTOMER")
        customers.filter.assert_called_once_with(
            pawn_loans__state__in={
                PawnLoanState.APPROVED.value,
                PawnLoanState.ACTIVE.value,
            }
        )
        self.assertEqual(summary["active_customers"], 0)
