from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.models import GivenLoan
from apps.tenant_apps.girvi.views.loanitem import (
    loanitem_create_update,
    repledged_loanitem_delete,
)


def attach_request_state(request):
    request._messages = MagicMock()
    request.user = MagicMock(is_authenticated=True)
    request.htmx = True
    return request


class RepledgedLoanItemLegacyGuardrailTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_taken_loan_item_create_update_route_is_gone(self):
        request = attach_request_state(self.factory.get("/"))
        taken_loan = MagicMock()
        taken_loan.status = "Draft"
        taken_loan.get_absolute_url.return_value = "/taken/"

        with (
            patch(
                "apps.tenant_apps.girvi.views.loanitem.GivenLoan.objects.get",
                side_effect=GivenLoan.DoesNotExist,
            ),
            patch(
                "apps.tenant_apps.girvi.views.loanitem.get_object_or_404",
                return_value=taken_loan,
            ),
        ):
            response = loanitem_create_update(request, parent_id=1)

        self.assertEqual(response.status_code, 410)

    def test_legacy_repledged_loanitem_delete_route_is_gone(self):
        request = attach_request_state(self.factory.delete("/"))

        response = repledged_loanitem_delete(request, parent_id=1, id=2)

        self.assertEqual(response.status_code, 410)
