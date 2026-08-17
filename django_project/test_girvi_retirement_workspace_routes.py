from pathlib import Path

from django.test import SimpleTestCase
from django.test import RequestFactory
from django.urls import resolve, reverse

from django_project import workspace_urls


class GirviRetirementWorkspaceRouteTests(SimpleTestCase):
    def test_workspace_loan_routes_keep_their_public_names(self):
        self.assertEqual(
            reverse("workspace_slug_loan_list", kwargs={"workspace_slug": "acme"}),
            "/w/acme/loans/list/",
        )
        self.assertEqual(
            reverse(
                "workspace_slug_loan_detail",
                kwargs={"workspace_slug": "acme", "pk": 7},
            ),
            "/w/acme/loans/7/",
        )

    def test_orgs_workspace_loan_wrappers_do_not_import_girvi(self):
        source = Path("apps/orgs/views.py").read_text(encoding="utf-8")
        loan_section = source.split("def workspace_slug_loans", 1)[1].split(
            "def workspace_slug_inventory", 1
        )[0]

        self.assertNotIn("apps.tenant_apps.girvi", loan_section)
        self.assertIn("apps.tenant_apps.loans.views", loan_section)

    def test_orgs_navigation_surfaces_use_loans_routes(self):
        source = Path("apps/orgs/views.py").read_text(encoding="utf-8")

        self.assertNotIn('"route_name": "girvi:', source)
        self.assertNotIn('redirect("girvi:', source)
        self.assertIn('"route_name": "loans:pawn_loan_list"', source)
        self.assertIn('redirect("loans:license_list")', source)

    def test_legacy_notify_routes_redirect_to_notify_v2(self):
        factory = RequestFactory()
        for path in (
            "/notify/noticegroup/",
            "/notify/noticegroup/7/",
            "/notify/notification/",
            "/notify/notification/7/",
        ):
            with self.subTest(path=path):
                match = resolve(path, urlconf=workspace_urls)
                response = match.func(factory.get(path), **match.kwargs)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, "/notify-v2/batches/")

    def test_legacy_notify_runtime_package_is_removed(self):
        settings_source = Path("django_project/settings/base.py").read_text(
            encoding="utf-8"
        )
        workspace_urls_source = Path("django_project/workspace_urls.py").read_text(
            encoding="utf-8"
        )

        self.assertFalse(Path("apps/tenant_apps/notify").exists())
        self.assertFalse(Path("templates/notify").exists())
        self.assertFalse(Path("apps/tenant_apps/utils/loan_pdf.py").exists())
        self.assertNotIn('"apps.tenant_apps.notify",', settings_source)
        self.assertNotIn("apps.tenant_apps.notify.urls", workspace_urls_source)
        self.assertIn("django_project.legacy_notify_urls", workspace_urls_source)

    def test_orgs_notification_wrappers_do_not_import_legacy_notify(self):
        source = Path("apps/orgs/views.py").read_text(encoding="utf-8")
        notification_section = source.split(
            "def workspace_slug_notifications", 1
        )[1].split("def workspace_slug_data_tools_export", 1)[0]

        self.assertNotIn("apps.tenant_apps.notify.views", notification_section)
        self.assertEqual(
            notification_section.count('redirect("notify_v2_batch_list")'),
            4,
        )

    def test_workspace_seed_commands_do_not_schedule_legacy_notify(self):
        workspace_seed = Path(
            "apps/orgs/management/commands/seed_workspace_defaults.py"
        ).read_text(encoding="utf-8")
        all_workspaces_seed = Path(
            "apps/orgs/management/commands/seed_all_workspaces.py"
        ).read_text(encoding="utf-8")
        active_workspace_seed = workspace_seed.split(
            "def _seed_notification_template_defaults", 1
        )[0]

        self.assertNotIn("apps.tenant_apps.notify.models", workspace_seed)
        self.assertNotIn('actions.append("seed_notify")', active_workspace_seed)
        self.assertNotIn('if "seed_notify" in actions', active_workspace_seed)
        self.assertNotIn('"--skip-notify"', active_workspace_seed)
        self.assertNotIn('"--skip-notify"', all_workspaces_seed)
        self.assertNotIn(
            'skip_notify=options["skip_notify"]', all_workspaces_seed
        )
        self.assertIn('actions.append("seed_notify_v2")', active_workspace_seed)

    def test_girvi_runtime_package_is_removed(self):
        settings_source = Path("django_project/settings/base.py").read_text(
            encoding="utf-8"
        )
        workspace_urls_source = Path("django_project/workspace_urls.py").read_text(
            encoding="utf-8"
        )

        self.assertFalse(Path("apps/tenant_apps/girvi").exists())
        self.assertFalse(Path("templates/girvi").exists())
        self.assertNotIn('"apps.tenant_apps.girvi",', settings_source)
        self.assertNotIn("apps.tenant_apps.girvi.urls", workspace_urls_source)
        self.assertIn("django_project.legacy_girvi_urls", workspace_urls_source)
