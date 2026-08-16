from types import SimpleNamespace
from unittest.mock import patch

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase, override_settings

from apps.tenant_apps.rates.middleware import RateMiddleware
from apps.tenant_apps.rates.models import Rate, RateSource


class RateWorkspaceIsolationTests(SimpleTestCase):
    def test_rate_inherits_workspace_from_source(self):
        rate = Rate(
            rate_source=RateSource(id=1, workspace_id=7),
            buying_rate="1.00",
            selling_rate="2.00",
        )

        with patch.object(Rate.__mro__[1], "save", autospec=True):
            rate.save()

        self.assertEqual(rate.workspace_id, 7)

    def test_rate_rejects_source_from_another_workspace(self):
        rate = Rate(
            workspace_id=8,
            rate_source=RateSource(id=1, workspace_id=7),
            buying_rate="1.00",
            selling_rate="2.00",
        )

        with self.assertRaises(ValidationError):
            rate.save()


@override_settings(CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}})
class RateCacheIsolationTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_middleware_reads_only_workspace_cache_keys(self):
        cache.set("workspace:1:gold_rate", "workspace-one")
        cache.set("workspace:2:gold_rate", "workspace-two")
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(is_authenticated=True)
        request.workspace = SimpleNamespace(pk=2)

        with patch("apps.tenant_apps.rates.middleware.Rate.objects") as objects:
            objects.filter.return_value.values.return_value.annotate.return_value = []
            RateMiddleware(lambda _request: None).process_request(request)

        self.assertEqual(request.grate, "workspace-two")
