from django.conf import settings
from django.test import SimpleTestCase

from django_project import public_urls, tenant_urls, urls
from django_project.shared_urlpatterns import (
    AUTH_URLPATTERNS,
    CANONICAL_CONTROL_PLANE_URLPATTERNS,
    GLOBAL_AUTHENTICATED_URLPATTERNS,
    PUBLIC_PLATFORM_URLPATTERNS,
    SERVICE_URLPATTERNS,
    shared_urlpatterns,
)
from django.urls import resolve, reverse


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

    def test_global_authenticated_routes_start_with_canonical_aliases(self):
        self.assertEqual(
            GLOBAL_AUTHENTICATED_URLPATTERNS[: len(CANONICAL_CONTROL_PLANE_URLPATTERNS)],
            CANONICAL_CONTROL_PLANE_URLPATTERNS,
        )

    def test_canonical_control_plane_aliases_resolve(self):
        route_cases = {
            "app_dashboard": "/app/",
            "app_workspaces": "/app/workspaces/",
            "app_workspace_create": "/app/workspaces/new/",
            "app_invitations": "/app/invitations/",
            "app_memberships": "/app/memberships/",
            "workspace_settings_home": "/workspace/42/settings/",
            "workspace_settings_preferences": "/workspace/42/settings/preferences/",
            "workspace_settings_team": "/workspace/42/settings/team/",
            "workspace_settings_invitations": "/workspace/42/settings/invitations/",
            "workspace_settings_invite": "/workspace/42/settings/invitations/new/",
            "workspace_settings_leave": "/workspace/42/settings/leave/",
        }

        for route_name, expected_path in route_cases.items():
            if route_name.startswith("workspace_settings_"):
                kwargs = {"workspace_id": 42}
            else:
                kwargs = {}
            with self.subTest(route_name=route_name):
                self.assertEqual(reverse(route_name, kwargs=kwargs), expected_path)
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_legacy_org_routes_remain_unchanged_after_canonical_aliases(self):
        self.assertEqual(reverse("workspace_selector"), "/orgs/workspace/")
        self.assertEqual(reverse("workspace_create"), "/orgs/workspace/create/")
        self.assertEqual(reverse("team_invitations"), "/orgs/team/invitations/")
        self.assertEqual(reverse("team_members_list"), "/orgs/team/members/")
        self.assertEqual(reverse("team_invitations_list"), "/orgs/team/invitations/list/")
        self.assertEqual(
            reverse("team_invite", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/team/invite/",
        )

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
