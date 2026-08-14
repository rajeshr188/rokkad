from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.access import girvi_permission_required
from apps.tenant_apps.girvi.views.loan import loan_create
from apps.tenant_apps.girvi.views.loanpayment import loan_payment_create_view
from apps.tenant_apps.girvi.views.prints import payment_receipt_pdf
from apps.tenant_apps.girvi.views.release import release_create
from apps.tenant_apps.girvi.views.reports import (
    girvi_operations_console,
    loan_operational_controls_report,
    loan_accounting_reconciliation_report,
)


class GirviPermissionGuardTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, username="member")
        self.owner = SimpleNamespace(is_authenticated=True, username="owner")

    def _request(self, path="/girvi/"):
        request = self.factory.get(path)
        request.user = self.user
        request.tenant = SimpleNamespace(
            schema_name="tenant-1",
            owner=self.owner,
            theme="default",
            logo="",
        )
        request.htmx = False
        return request

    def test_decorator_denies_missing_permission(self):
        @girvi_permission_required("girvi_loan_create")
        def protected_view(request):
            return HttpResponse("ok")

        request = self._request("/girvi/loan/create/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                protected_view(request)

    def test_decorator_allows_when_permission_present(self):
        @girvi_permission_required("girvi_loan_create")
        def protected_view(request):
            return HttpResponse("ok")

        request = self._request("/girvi/loan/create/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_create"},
        ):
            response = protected_view(request)

        self.assertEqual(response.status_code, 200)

    def test_loan_create_requires_create_permission(self):
        request = self._request("/girvi/loan/create/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                loan_create(request)

    def test_repayment_requires_payment_permission(self):
        request = self._request("/girvi/loan/1/payment/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                loan_payment_create_view(request, pk=1)

    def test_payment_receipt_pdf_requires_payment_permission(self):
        request = self._request("/girvi/loanpayment/1/receipt/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                payment_receipt_pdf(request, pk=1)

    def test_release_requires_release_permission(self):
        request = self._request("/girvi/release/create/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                release_create(request)

    def test_reconciliation_report_requires_report_permission(self):
        request = self._request("/girvi/reports/reconciliation/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                loan_accounting_reconciliation_report(request)

    def test_operations_console_requires_report_permission(self):
        request = self._request("/girvi/reports/operations-console/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                girvi_operations_console(request)

    def test_operational_controls_report_requires_report_permission(self):
        request = self._request("/girvi/reports/operational-controls/")

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ), patch(
            "apps.tenant_apps.girvi.views.access.get_effective_permissions",
            return_value={"girvi_loan_view"},
        ):
            with self.assertRaises(PermissionDenied):
                loan_operational_controls_report(request)
