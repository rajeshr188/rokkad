from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from .models import Rate, RateSource
from .services import record_quote


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RateReferenceUiTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "rate-reference-ui"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.owner = get_user_model().objects.create_user(username="rate-reference-owner")
        tenant.owner = tenant.creator = cls.owner
        tenant.name = "Rate reference"
        tenant.save()
        Membership.objects.create(company=tenant, user=cls.owner, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.source = RateSource.objects.create(name="Market <North>", location="Local")
        self.quote = record_quote(workspace=self.tenant, actor=self.owner, values={
            "rate_source": self.source, "metal": "Gold", "currency": "INR", "purity": "24k",
            "buying_rate": "7000", "selling_rate": "7100", "effective_at": timezone.now() - timedelta(days=1),
        })

    def url(self, name, **kwargs):
        return reverse("workspace_rates:" + name, kwargs={"workspace_slug": self.tenant.slug, **kwargs})

    def test_search_uses_quote_snapshot_and_fragment_contract(self):
        self.source.name = "Renamed"
        self.source.save()
        url = self.url("rate_list")
        headers = {"HX-Request": "true", "HX-Target": "reference-results"}
        response = self.client.get(url, {"q": "North", "metal": "Gold"}, headers=headers)
        self.assertContains(response, "Market &lt;North&gt;")
        self.assertNotContains(response, "<html")
        self.assertEqual(response["X-Rokkad-Fragment"], "reference-results")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("HX-Target", response["Vary"])
        for extra in ({"HX-History-Restore-Request": "true"}, {"HX-Boosted": "true"}, {"HX-Target": "other"}):
            full = self.client.get(url, headers={**headers, **extra})
            self.assertContains(full, "<html")
            self.assertNotIn("X-Rokkad-Fragment", full)

    def test_invalid_filter_is_linked_and_does_not_show_quotes(self):
        response = self.client.get(self.url("rate_list"), {"metal": "invalid"})
        self.assertContains(response, 'href="#id_metal"')
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_paging_preserves_filters(self):
        for number in range(26):
            record_quote(workspace=self.tenant, actor=self.owner, values={
                "rate_source": self.source, "metal": "Silver", "currency": "INR", "purity": "24k",
                "buying_rate": "90", "selling_rate": "95", "reason": "Paging",
                "effective_at": timezone.now() - timedelta(minutes=number),
            })
        response = self.client.get(self.url("rate_list"), {"q": "Paging", "metal": "Silver", "page": 2})
        self.assertEqual(len(response.context["rates"]), 1)
        self.assertEqual(response.context["page_obj"].paginator.count, 26)
        self.assertContains(response, "metal=Silver")
        self.assertContains(response, "q=Paging")

    def test_empty_withdrawal_is_bound_and_keeps_quote(self):
        count = Rate.objects.count()
        response = self.client.post(self.url("rate_delete", pk=self.quote.pk), {})
        self.assertContains(response, 'href="#id_reason"')
        self.assertTrue(response.context["form"].is_bound)
        self.quote.refresh_from_db()
        self.assertEqual(self.quote.record_status, "Available")
        self.assertEqual(Rate.objects.count(), count)

    def test_forms_and_history_render_in_hindi(self):
        self.client.cookies["django_language"] = "hi"
        for name, kwargs in [("rate_create", {}), ("rate_update", {"pk": self.quote.pk}),
                             ("rate_detail", {"pk": self.quote.pk}), ("ratesource_create", {}),
                             ("ratesource_detail", {"pk": self.source.pk}), ("ratesource_list", {})]:
            with self.subTest(name=name):
                response = self.client.get(self.url(name, **kwargs))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'hx-history="false"')
                self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(self.client.get(self.url("rate_create")), "शुद्ध धातु")
