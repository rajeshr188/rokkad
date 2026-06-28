from django.conf import settings
from django.test import SimpleTestCase

from django_project import public_urls, tenant_urls, urls
from django_project.shared_urlpatterns import (
    AUTH_URLPATTERNS,
    GLOBAL_AUTHENTICATED_URLPATTERNS,
    PUBLIC_PLATFORM_URLPATTERNS,
    SERVICE_URLPATTERNS,
    shared_urlpatterns,
)


def _route_prefixes(patterns):
    return {str(pattern.pattern) for pattern in patterns}


class SaaSRouteIntentTests(SimpleTestCase):
    def test_active_urlconfs_match_current_django_tenants_settings(self):
        self.assertEqual(settings.ROOT_URLCONF, "django_project.tenant_urls")
        self.assertEqual(settings.PUBLIC_SCHEMA_URLCONF, "django_project.urls")

    def test_shared_urlpatterns_preserve_compatibility_order(self):
        expected = (
            SERVICE_URLPATTERNS
            + PUBLIC_PLATFORM_URLPATTERNS
            + AUTH_URLPATTERNS
            + GLOBAL_AUTHENTICATED_URLPATTERNS
        )

        self.assertEqual(shared_urlpatterns, expected)

    def test_public_schema_urlconf_does_not_expose_tenant_erp_prefixes(self):
        public_prefixes = _route_prefixes(urls.urlpatterns)
        tenant_only_prefixes = {
            "party/",
            "contact/",
            "data-tools/",
            "girvi/",
            "rates/",
            "product/",
            "notify/",
            "notify-v2/",
            "dea/",
        }

        self.assertTrue(tenant_only_prefixes.isdisjoint(public_prefixes))

    def test_tenant_urlconf_collects_tenant_erp_prefixes_separately(self):
        tenant_prefixes = _route_prefixes(tenant_urls.TENANT_ERP_URLPATTERNS)

        self.assertEqual(
            tenant_prefixes,
            {
                "party/",
                "contact/",
                "data-tools/",
                "girvi/",
                "rates/",
                "product/",
                "notify/",
                "notify-v2/",
                "dea/",
            },
        )

    def test_legacy_public_urlconf_uses_same_shared_control_plane_bundle(self):
        active_public_prefixes = _route_prefixes(urls.urlpatterns)
        legacy_public_prefixes = _route_prefixes(public_urls.urlpatterns)

        self.assertEqual(active_public_prefixes, legacy_public_prefixes)
