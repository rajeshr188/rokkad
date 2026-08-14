from django.conf import settings
from django.test import SimpleTestCase

from django_project import public_urls, tenant_urls, urls
from django_project.shared_urlpatterns import (
    AUTH_URLPATTERNS,
    CANONICAL_CONTROL_PLANE_URLPATTERNS,
    CANONICAL_WORKSPACE_SLUG_URLPATTERNS,
    GLOBAL_AUTHENTICATED_URLPATTERNS,
    PUBLIC_PLATFORM_URLPATTERNS,
    SERVICE_URLPATTERNS,
    shared_urlpatterns,
)
from django.urls import NoReverseMatch, Resolver404, resolve, reverse


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
        self.assertEqual(
            GLOBAL_AUTHENTICATED_URLPATTERNS[
                len(CANONICAL_CONTROL_PLANE_URLPATTERNS) :
                len(CANONICAL_CONTROL_PLANE_URLPATTERNS)
                + len(CANONICAL_WORKSPACE_SLUG_URLPATTERNS)
            ],
            CANONICAL_WORKSPACE_SLUG_URLPATTERNS,
        )

    def test_canonical_control_plane_aliases_resolve(self):
        route_cases = {
            "app_dashboard": "/app/",
            "app_workspaces": "/app/workspaces/",
            "app_workspace_create": "/app/workspaces/new/",
            "app_invitations": "/app/invitations/",
            "app_memberships": "/app/memberships/",
            "workspace_settings_home": "/workspace/42/settings/",
            "workspace_settings_setup": "/workspace/42/settings/setup/",
            "workspace_settings_setup_state": "/workspace/42/settings/setup/state/",
            "workspace_settings_preferences": "/workspace/42/settings/preferences/",
            "workspace_settings_team": "/workspace/42/settings/team/",
            "workspace_settings_invitations": "/workspace/42/settings/invitations/",
            "workspace_settings_invite": "/workspace/42/settings/invitations/new/",
            "workspace_settings_modules": "/workspace/42/settings/modules/",
            "workspace_settings_security": "/workspace/42/settings/security/",
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

    def test_phase104_minimal_workspace_slug_aliases_resolve(self):
        route_cases = {
            "workspace_slug_dashboard": "/w/acme/",
            "workspace_slug_settings": "/w/acme/settings/",
            "workspace_slug_settings_preferences": "/w/acme/settings/preferences/",
            "workspace_slug_settings_team": "/w/acme/settings/team/",
            "workspace_slug_settings_invitations": "/w/acme/settings/invitations/",
            "workspace_slug_settings_profile": "/w/acme/settings/profile/",
            "workspace_slug_settings_billing": "/w/acme/settings/billing/",
            "workspace_slug_settings_roles": "/w/acme/settings/roles/",
            "workspace_slug_settings_numbering": "/w/acme/settings/numbering/",
            "workspace_slug_settings_modules": "/w/acme/settings/modules/",
            "workspace_slug_settings_security": "/w/acme/settings/security/",
            "workspace_slug_settings_accounting": "/w/acme/settings/accounting/",
            "workspace_slug_operations": "/w/acme/operations/",
            "workspace_slug_parties": "/w/acme/parties/",
            "workspace_slug_sales": "/w/acme/sales/",
            "workspace_slug_purchase": "/w/acme/purchase/",
            "workspace_slug_loans": "/w/acme/loans/",
            "workspace_slug_inventory": "/w/acme/inventory/",
            "workspace_slug_accounting": "/w/acme/accounting/",
            "workspace_slug_commodity": "/w/acme/commodity/",
            "workspace_slug_reports": "/w/acme/reports/",
        }

        for route_name, expected_path in route_cases.items():
            with self.subTest(route_name=route_name):
                kwargs = {"workspace_slug": "acme"}
                self.assertEqual(reverse(route_name, kwargs=kwargs), expected_path)
                self.assertEqual(resolve(expected_path).url_name, route_name)

    def test_phase104_workspace_slug_aliases_resolve_in_public_and_tenant_urlconfs(self):
        route_cases = {
            "/w/acme/": "workspace_slug_dashboard",
            "/w/acme/settings/": "workspace_slug_settings",
            "/w/acme/settings/preferences/": "workspace_slug_settings_preferences",
            "/w/acme/settings/team/": "workspace_slug_settings_team",
            "/w/acme/settings/invitations/": "workspace_slug_settings_invitations",
            "/w/acme/settings/profile/": "workspace_slug_settings_profile",
            "/w/acme/settings/billing/": "workspace_slug_settings_billing",
            "/w/acme/settings/roles/": "workspace_slug_settings_roles",
            "/w/acme/settings/numbering/": "workspace_slug_settings_numbering",
            "/w/acme/settings/modules/": "workspace_slug_settings_modules",
            "/w/acme/settings/security/": "workspace_slug_settings_security",
            "/w/acme/settings/accounting/": "workspace_slug_settings_accounting",
            "/w/acme/operations/": "workspace_slug_operations",
            "/w/acme/parties/": "workspace_slug_parties",
            "/w/acme/sales/": "workspace_slug_sales",
            "/w/acme/purchase/": "workspace_slug_purchase",
            "/w/acme/loans/": "workspace_slug_loans",
            "/w/acme/inventory/": "workspace_slug_inventory",
            "/w/acme/accounting/": "workspace_slug_accounting",
            "/w/acme/commodity/": "workspace_slug_commodity",
            "/w/acme/reports/": "workspace_slug_reports",
        }

        for path, route_name in route_cases.items():
            with self.subTest(path=path, urlconf="public"):
                self.assertEqual(resolve(path, urlconf=urls).url_name, route_name)
            with self.subTest(path=path, urlconf="tenant"):
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

    def test_current_canonical_control_plane_aliases_resolve_in_public_and_tenant_urlconfs(self):
        route_cases = {
            "/app/": "app_dashboard",
            "/app/workspaces/": "app_workspaces",
            "/app/workspaces/new/": "app_workspace_create",
            "/app/invitations/": "app_invitations",
            "/app/memberships/": "app_memberships",
            "/workspace/42/settings/": "workspace_settings_home",
            "/workspace/42/settings/setup/": "workspace_settings_setup",
            "/workspace/42/settings/setup/state/": "workspace_settings_setup_state",
            "/workspace/42/settings/preferences/": "workspace_settings_preferences",
            "/workspace/42/settings/team/": "workspace_settings_team",
            "/workspace/42/settings/invitations/": "workspace_settings_invitations",
            "/workspace/42/settings/invitations/new/": "workspace_settings_invite",
            "/workspace/42/settings/modules/": "workspace_settings_modules",
            "/workspace/42/settings/security/": "workspace_settings_security",
            "/workspace/42/settings/leave/": "workspace_settings_leave",
        }

        for path, route_name in route_cases.items():
            with self.subTest(path=path, urlconf="public"):
                self.assertEqual(resolve(path, urlconf=urls).url_name, route_name)
            with self.subTest(path=path, urlconf="tenant"):
                self.assertEqual(resolve(path, urlconf=tenant_urls).url_name, route_name)

    def test_legacy_org_routes_remain_unchanged_after_canonical_aliases(self):
        self.assertEqual(reverse("workspace_selector"), "/orgs/workspace/")
        self.assertEqual(reverse("workspace_create"), "/orgs/workspace/create/")
        self.assertEqual(
            reverse("workspace_setup", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/setup/",
        )
        self.assertEqual(
            reverse("workspace_setup_state", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/setup/state/",
        )
        self.assertEqual(reverse("team_invitations"), "/orgs/team/invitations/")
        self.assertEqual(reverse("team_members_list"), "/orgs/team/members/")
        self.assertEqual(reverse("team_invitations_list"), "/orgs/team/invitations/list/")
        self.assertEqual(
            reverse("team_invite", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/team/invite/",
        )

    def test_legacy_auth_invitation_and_org_paths_remain_resolvable(self):
        path_cases = {
            "/login/": "login",
            "/signup/": "signup",
            "/password/reset/": "password_reset",
            "/invitations/accept/example-key/": "public_invitation_accept",
            "/accounts/login/": "account_login",
            "/accounts/signup/": "account_signup",
            "/accounts/password/reset/": "account_reset_password",
            "/invitations/": "workspace_invitations",
            "/orgs/workspace/": "workspace_selector",
            "/orgs/workspace/create/": "workspace_create",
            "/orgs/workspace/42/setup/": "workspace_setup",
            "/orgs/workspace/42/setup/state/": "workspace_setup_state",
            "/orgs/team/invitations/": "team_invitations",
            "/orgs/team/members/": "team_members_list",
            "/orgs/team/invitations/list/": "team_invitations_list",
            "/orgs/workspace/42/team/invite/": "team_invite",
        }

        for path, route_name in path_cases.items():
            with self.subTest(path=path):
                self.assertEqual(resolve(path).url_name, route_name)

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

    def test_public_schema_urlconf_rejects_representative_tenant_erp_paths(self):
        tenant_only_paths = (
            "/party/",
            "/contact/customer/",
            "/data-tools/export/",
            "/girvi/deletemultiple/",
            "/rates/rates/",
            "/product/",
            "/notify/noticegroup/",
            "/notify-v2/",
            "/dea/",
        )

        for path in tenant_only_paths:
            with self.subTest(path=path):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)

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

    def test_tenant_urlconf_resolves_representative_tenant_erp_paths(self):
        path_cases = {
            "/party/": "party_list",
            "/contact/customer/": "contact_customer_list",
            "/data-tools/export/": "export_form",
            "/girvi/deletemultiple/": "girvi_loan_deletemultiple",
            "/rates/rates/": "rate_list",
            "/product/": "product_product_home",
            "/notify/noticegroup/": "notify_noticegroup_list",
            "/notify-v2/": "notify_v2_index",
            "/dea/": "dea_home",
        }

        for path, route_name in path_cases.items():
            with self.subTest(path=path):
                match = resolve(path, urlconf=tenant_urls)
                self.assertEqual(match.url_name, route_name)

    def test_legacy_public_urlconf_uses_same_shared_control_plane_bundle(self):
        active_public_prefixes = _route_prefixes(urls.urlpatterns)
        legacy_public_prefixes = _route_prefixes(public_urls.urlpatterns)

        self.assertEqual(active_public_prefixes, legacy_public_prefixes)

    def test_phase92_pricing_route_is_public_and_shared_compatibility_route(self):
        self.assertEqual(reverse("pricing"), "/pricing/")
        self.assertEqual(resolve("/pricing/", urlconf=urls).url_name, "pricing")
        self.assertEqual(resolve("/pricing/", urlconf=tenant_urls).url_name, "pricing")

    def test_still_deferred_public_and_tenant_route_aliases_are_intentionally_absent(self):
        absent_route_names = (
            "workspace_slug_contact",
        )

        for route_name in absent_route_names:
            with self.subTest(route_name=route_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(route_name, kwargs={"workspace_slug": "acme"})

        absent_paths = (
            "/w/acme/contact/",
        )

        for path in absent_paths:
            with self.subTest(path=path, urlconf="public"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=urls)
            with self.subTest(path=path, urlconf="tenant"):
                with self.assertRaises(Resolver404):
                    resolve(path, urlconf=tenant_urls)
