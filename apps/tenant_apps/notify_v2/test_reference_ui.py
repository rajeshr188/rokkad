from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from .models import NotificationBatch, NotificationEventType, NotificationRecipient, NotificationEvent, NotificationJob, WhatsAppCloudIntegration


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class NotificationReferenceUiTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "notification-reference-ui"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.owner = get_user_model().objects.create_user(username="notification-reference-owner")
        tenant.owner = tenant.creator = cls.owner
        tenant.name = "Notification reference"
        tenant.save()
        Membership.objects.create(company=tenant, user=cls.owner, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.event_type = NotificationEventType.objects.create(key="ui-review", name="Review event", domain="GENERAL")
        self.batch = NotificationBatch.objects.create(event_type=self.event_type, name="Review <batch>", created_by=self.owner)

    def url(self, name, **kwargs):
        return reverse("workspace_notify:notify_v2_" + name, kwargs={"workspace_slug": self.tenant.slug, **kwargs})

    def test_search_paging_and_fragment_contract(self):
        for number in range(26):
            NotificationBatch.objects.create(event_type=self.event_type, name=f"Page {number}", status="RENDERED")
        headers = {"HX-Request": "true", "HX-Target": "reference-results"}
        response = self.client.get(self.url("batch_list"), {"q": "Page", "status": "RENDERED", "page": 2}, headers=headers)
        self.assertEqual(len(response.context["objects"]), 1)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertEqual(response["X-Rokkad-Fragment"], "reference-results")
        self.assertNotContains(response, "<html")
        self.assertContains(response, "status=RENDERED")
        self.assertIn("no-store", response["Cache-Control"])
        for extra in ({"HX-History-Restore-Request": "true"}, {"HX-Boosted": "true"}):
            self.assertContains(self.client.get(self.url("batch_list"), headers={**headers, **extra}), "<html")

    def test_invalid_filter_is_linked_and_fails_closed(self):
        response = self.client.get(self.url("batch_list"), {"status": "INVALID"})
        self.assertContains(response, 'href="#id_status"')
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    @patch("apps.tenant_apps.notify_v2.views.dispatch_batch_jobs")
    def test_review_never_dispatches_and_only_offers_eligible_jobs(self, dispatch):
        recipient = NotificationRecipient.objects.create(name_snapshot="Customer <One>")
        for status in ("SENT", "CANCELLED", "FAILED"):
            event = NotificationEvent.objects.create(event_type=self.event_type, recipient=recipient, batch=self.batch)
            NotificationJob.objects.create(event=event, batch=self.batch, channel="EMAIL", status=status)
        response = self.client.get(self.url("batch_detail", pk=self.batch.pk))
        self.assertContains(response, "Customer &lt;One&gt;")
        self.assertTrue(response.context["can_send_digital"])
        self.assertEqual(response.context["digital_job_count"], 1)
        self.assertContains(response, "Send eligible digital jobs")
        NotificationJob.objects.filter(status="FAILED").update(status="SENT")
        self.assertNotContains(self.client.get(self.url("batch_detail", pk=self.batch.pk)), "Send eligible digital jobs")
        dispatch.assert_not_called()

    @patch("apps.tenant_apps.notify_v2.views.set_whatsapp_cloud_integration")
    def test_empty_setup_has_linked_errors_and_secrets_never_echo(self, save):
        url = self.url("whatsapp_cloud_integration")
        response = self.client.post(url, {})
        self.assertContains(response, 'href="#id_phone_number_id"')
        self.assertContains(response, 'href="#id_access_token"')
        failed = self.client.post(url, {"access_token": "secret-must-not-echo", "phone_number_id": "123"})
        self.assertNotContains(failed, "secret-must-not-echo")
        save.assert_not_called()
        self.assertFalse(WhatsAppCloudIntegration.objects.exists())

    def test_settings_and_empty_batch_render_in_hindi(self):
        self.client.cookies["django_language"] = "hi"
        for name, kwargs in [("settings", {}), ("whatsapp_cloud_integration", {}), ("batch_detail", {"pk": self.batch.pk})]:
            response = self.client.get(self.url(name, **kwargs))
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertContains(response, 'hx-history="false"')
