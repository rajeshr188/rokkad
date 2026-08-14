from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.notice import create_loan_notification
from apps.tenant_apps.girvi.views.prints import notify_print, notify_print_v2
from apps.tenant_apps.notify.models import Notification
from apps.tenant_apps.notify_v2.models import NotificationJob


class GirviNoticeDispatchFlowTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(is_authenticated=True, username="demo-user")

    def _request(self, method="post", path="/girvi/outdatedloans/notify-v2/", data=None, htmx=False):
        request_factory = self.factory.post if method.lower() == "post" else self.factory.get
        request = request_factory(path, data=data or {})
        request.user = self.user
        request.tenant = SimpleNamespace(
            schema_name="tenant-1",
            owner=SimpleNamespace(username="owner-user"),
            theme="default",
            logo="",
        )
        request.htmx = htmx
        if htmx:
            request.META["HTTP_HX_REQUEST"] = "true"
        return request

    def _selection(self, loans=None):
        return SimpleNamespace(is_valid=True, invalid_ids=[], loans=list(loans or []), error="")

    @patch("apps.tenant_apps.girvi.views.prints.create_girvi_reminder_batch")
    @patch("apps.tenant_apps.girvi.views.prints.unreleased_given_loan_selection")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_notify_print_v2_uses_notify_v2_mapping(
        self,
        _role_name,
        _effective_permissions,
        mock_selection,
        mock_create_batch,
    ):
        loan = SimpleNamespace(pk=12, loan_id="GL-012")
        mock_selection.return_value = self._selection([loan])
        mock_create_batch.return_value = SimpleNamespace(
            batch=SimpleNamespace(get_absolute_url=lambda: "/notify/v2/batches/77/"),
            preview=SimpleNamespace(borrower_count=1, loan_count=1),
        )

        request = self._request(
            data={
                "notice_code": "LOAN_FINAL_NOTICE",
                "medium_type": Notification.MediumType.SMS,
            }
        )

        response = notify_print_v2(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/notify/v2/batches/77/")
        kwargs = mock_create_batch.call_args.kwargs
        self.assertEqual(kwargs["event_key"], "loan.final_notice_due")
        self.assertEqual(kwargs["channel"], NotificationJob.Channel.SMS)
        self.assertIn("girvi_create_notice_v2", kwargs["notes"])

    @patch("apps.tenant_apps.girvi.views.prints.create_girvi_reminder_batch")
    @patch("apps.tenant_apps.girvi.views.prints.unreleased_given_loan_selection")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_notify_print_legacy_alias_routes_to_notify_v2(
        self,
        _role_name,
        _effective_permissions,
        mock_selection,
        mock_create_batch,
    ):
        loan = SimpleNamespace(pk=99, loan_id="GL-099")
        mock_selection.return_value = self._selection([loan])
        mock_create_batch.return_value = SimpleNamespace(
            batch=SimpleNamespace(get_absolute_url=lambda: "/notify/v2/batches/88/"),
            preview=SimpleNamespace(borrower_count=1, loan_count=1),
        )

        request = self._request(path="/girvi/outdatedloans/notify/")
        response = notify_print(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/notify/v2/batches/88/")
        kwargs = mock_create_batch.call_args.kwargs
        self.assertIn("legacy alias", kwargs["notes"])

    @patch("apps.tenant_apps.girvi.views.notice.create_girvi_reminder_batch")
    @patch("apps.tenant_apps.girvi.views.notice.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_create_loan_notification_creates_single_loan_batch(
        self,
        _role_name,
        _effective_permissions,
        mock_get_object,
        mock_create_batch,
    ):
        loan = SimpleNamespace(pk=5, loan_id="GL-005", borrower=SimpleNamespace(pk=1))
        mock_get_object.return_value = loan
        mock_create_batch.return_value = SimpleNamespace(
            batch=SimpleNamespace(get_absolute_url=lambda: "/notify/v2/batches/55/")
        )

        request = self._request(
            method="get",
            path="/girvi/loan/5/notify/",
            data={
                "notice_code": "LOAN_AUCTION_NOTICE",
                "medium_type": Notification.MediumType.Whatsapp,
            },
        )

        response = create_loan_notification(request, pk=5)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/notify/v2/batches/55/")
        kwargs = mock_create_batch.call_args.kwargs
        self.assertEqual(kwargs["event_key"], "loan.auction_notice_due")
        self.assertEqual(kwargs["channel"], NotificationJob.Channel.WHATSAPP)
        self.assertEqual(kwargs["loans"], [loan])

    @patch("apps.tenant_apps.girvi.views.prints.create_girvi_reminder_batch")
    @patch("apps.tenant_apps.girvi.views.prints.unreleased_given_loan_selection")
    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value={"girvi_report_view"})
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_notify_print_v2_htmx_responds_with_hx_redirect(
        self,
        _role_name,
        _effective_permissions,
        mock_selection,
        mock_create_batch,
    ):
        loan = SimpleNamespace(pk=18, loan_id="GL-018")
        mock_selection.return_value = self._selection([loan])
        mock_create_batch.return_value = SimpleNamespace(
            batch=SimpleNamespace(get_absolute_url=lambda: "/notify/v2/batches/18/"),
            preview=SimpleNamespace(borrower_count=1, loan_count=1),
        )

        request = self._request(htmx=True)
        response = notify_print_v2(request)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response["HX-Redirect"], "/notify/v2/batches/18/")

    @patch("apps.tenant_apps.girvi.views.access.get_effective_permissions", return_value=set())
    @patch("apps.tenant_apps.girvi.views.access.get_workspace_role_name", return_value="Member")
    def test_notify_print_v2_requires_report_permission(
        self,
        _role_name,
        _effective_permissions,
    ):
        request = self._request()

        with self.assertRaises(PermissionDenied):
            notify_print_v2(request)
