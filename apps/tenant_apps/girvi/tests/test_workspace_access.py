from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.views import View

from apps.tenant_apps.girvi.views.access import (
    GirviWorkspaceRequiredMixin,
    assert_girvi_workspace_access,
    girvi_workspace_required,
)
from apps.tenant_apps.girvi.views.custody_views import repledge_history_report
from apps.tenant_apps.girvi.views.forms import form_h
from apps.tenant_apps.girvi.views.notice import notice
from apps.tenant_apps.girvi.views.prints import payment_receipt_pdf, print_labels
from apps.tenant_apps.girvi.views.release import release_list
from apps.tenant_apps.girvi.views.reports import LoanTimeSeriesReport
from apps.tenant_apps.girvi.views.statement import verification_session_list
from apps.tenant_apps.girvi.views.template import template_preview_pdf


class GirviWorkspaceAccessTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, is_superuser=False)
        self.workspace = SimpleNamespace(
            schema_name="tenant1",
            owner=object(),
        )

    def _request(self, tenant=None, user=None):
        request = self.factory.get("/girvi/loan/")
        request.user = user or self.user
        if tenant is not None:
            request.tenant = tenant
        return request

    def test_no_workspace_fails_closed(self):
        with self.assertRaisesMessage(PermissionDenied, "No tenant workspace selected"):
            assert_girvi_workspace_access(self._request())

    def test_malformed_workspace_context_fails_closed(self):
        with self.assertRaisesMessage(PermissionDenied, "Invalid tenant workspace context"):
            assert_girvi_workspace_access(self._request(tenant=SimpleNamespace()))

    def test_workspace_owner_is_allowed(self):
        self.workspace.owner = self.user

        resolved = assert_girvi_workspace_access(self._request(tenant=self.workspace))

        self.assertIs(resolved, self.workspace)

    def test_platform_admin_is_allowed(self):
        admin = SimpleNamespace(is_authenticated=True, is_superuser=True)

        resolved = assert_girvi_workspace_access(
            self._request(tenant=self.workspace, user=admin)
        )

        self.assertIs(resolved, self.workspace)

    def test_non_member_fails_closed(self):
        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value=None,
        ):
            with self.assertRaisesMessage(PermissionDenied, "Not a workspace member"):
                assert_girvi_workspace_access(self._request(tenant=self.workspace))

    def test_member_is_allowed(self):
        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ):
            resolved = assert_girvi_workspace_access(self._request(tenant=self.workspace))

        self.assertIs(resolved, self.workspace)

    def test_decorator_runs_view_only_after_access_passes(self):
        calls = []

        @girvi_workspace_required
        def view(request):
            calls.append("called")
            return "ok"

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ):
            result = view(self._request(tenant=self.workspace))

        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["called"])

    def test_class_mixin_runs_view_only_after_access_passes(self):
        calls = []

        class DemoView(GirviWorkspaceRequiredMixin, View):
            def get(self, request, *args, **kwargs):
                calls.append("called")
                return "ok"

        with patch(
            "apps.tenant_apps.girvi.views.access.get_workspace_role_name",
            return_value="Member",
        ):
            result = DemoView.as_view()(self._request(tenant=self.workspace))

        self.assertEqual(result, "ok")
        self.assertEqual(calls, ["called"])

    def test_phase2_function_routes_fail_closed_without_workspace(self):
        routes = [
            release_list,
            notice,
            print_labels,
            repledge_history_report,
            verification_session_list,
        ]

        for view in routes:
            with self.subTest(view=view.__name__):
                with self.assertRaisesMessage(
                    PermissionDenied,
                    "No tenant workspace selected",
                ):
                    view(self._request())

    def test_phase2_document_routes_fail_closed_without_workspace(self):
        routes = [
            (form_h, (1,)),
            (template_preview_pdf, (1,)),
            (payment_receipt_pdf, (1,)),
        ]

        for view, args in routes:
            with self.subTest(view=view.__name__):
                with self.assertRaisesMessage(
                    PermissionDenied,
                    "No tenant workspace selected",
                ):
                    view(self._request(), *args)

    def test_phase2_report_class_route_fails_closed_without_workspace(self):
        view = LoanTimeSeriesReport.as_view()

        with self.assertRaisesMessage(
            PermissionDenied,
            "No tenant workspace selected",
        ):
            view(self._request())
