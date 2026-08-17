from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role


User = get_user_model()

TEST_STORAGES = {
    **settings.STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class UserProfileEndpointSecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="profile-owner",
            email="owner@example.com",
            password="test-password",
        )
        self.other_user = User.objects.create_user(
            username="profile-other",
            email="other@example.com",
            password="test-password",
        )

    def test_anonymous_profile_detail_and_update_redirect_to_login(self):
        detail_url = reverse("userprofile_detail", args=[self.user.profile.pk])
        update_url = reverse("userprofile_update", args=[self.user.profile.pk])

        self.assertEqual(self.client.get(detail_url).status_code, 302)
        self.assertEqual(self.client.get(update_url).status_code, 302)

    def test_user_cannot_read_another_users_profile(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("userprofile_detail", args=[self.other_user.profile.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_user_cannot_update_another_users_profile(self):
        self.client.force_login(self.user)
        original_phone = self.other_user.profile.phone_number

        response = self.client.post(
            reverse("userprofile_update", args=[self.other_user.profile.pk]),
            {
                "workspace": "",
                "timezone": "Asia/Kolkata",
                "phone_number": "9999999999",
                "address": "Unauthorized change",
            },
        )

        self.assertEqual(response.status_code, 404)
        self.other_user.profile.refresh_from_db()
        self.assertEqual(self.other_user.profile.phone_number, original_phone)

    def test_user_can_read_and_update_own_profile(self):
        self.client.force_login(self.user)
        detail_url = reverse("userprofile_detail", args=[self.user.profile.pk])
        update_url = reverse("userprofile_update", args=[self.user.profile.pk])

        self.assertEqual(self.client.get(detail_url).status_code, 200)
        response = self.client.post(
            update_url,
            {
                "workspace": "",
                "timezone": "Asia/Kolkata",
                "phone_number": "9876543210",
                "address": "Own profile",
            },
        )

        self.assertRedirects(response, detail_url)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.phone_number, "9876543210")
        self.assertEqual(self.user.profile.address, "Own profile")

    def test_superuser_does_not_gain_cross_profile_access_through_self_service_route(self):
        admin = User.objects.create_superuser(
            username="platform-admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(admin)

        response = self.client.get(
            reverse("userprofile_detail", args=[self.other_user.profile.pk])
        )

        self.assertEqual(response.status_code, 404)

    def test_profile_workspace_choices_are_limited_to_memberships(self):
        own_workspace = Company.objects.create(
            schema_name="profile_own",
            name="Profile Own",
            owner=self.user,
            creator=self.user,
        )
        foreign_workspace = Company.objects.create(
            schema_name="profile_foreign",
            name="Profile Foreign",
            owner=self.other_user,
            creator=self.other_user,
        )
        member_role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(
            user=self.user, company=own_workspace, role=member_role
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("userprofile_update", args=[self.user.profile.pk])
        )

        workspace_ids = set(
            response.context["form"].fields["workspace"].queryset.values_list(
                "pk", flat=True
            )
        )
        self.assertEqual(workspace_ids, {own_workspace.pk})
        self.assertNotIn(foreign_workspace.pk, workspace_ids)


@override_settings(STORAGES=TEST_STORAGES)
class PersistentPreferenceMethodTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="method-user",
            email="method@example.com",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_clear_reset_and_legacy_switch_reject_get(self):
        for url in (
            reverse("clear_workspace"),
            reverse("reset_workspace"),
            reverse("switch_workspace", args=[999]),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_clear_workspace_requires_csrf(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)

        response = csrf_client.post(reverse("clear_workspace"))

        self.assertEqual(response.status_code, 403)


class MutationTemplateContractTests(SimpleTestCase):
    def test_control_plane_templates_do_not_link_to_mutation_routes(self):
        template_root = Path(__file__).resolve().parents[1] / "templates"
        forbidden_fragments = (
            "href=\"{% url 'workspace_select'",
            "href=\"{% url 'clear_workspace'",
            "href=\"{% url 'team_remove_member'",
            "window.location='{% url 'team_remove_member'",
        )

        violations = []
        for template_path in template_root.rglob("*.html"):
            source = template_path.read_text(encoding="utf-8")
            for fragment in forbidden_fragments:
                if fragment in source:
                    violations.append(f"{template_path.relative_to(template_root)}: {fragment}")

        self.assertEqual(violations, [])

    def test_persistent_preference_views_reject_get_before_mutating(self):
        from accounts import views

        request = RequestFactory().get("/profile/clear/workspace/")
        request.user = type("User", (), {"is_authenticated": True})()

        clear_response = views.clear_workspace.__wrapped__(request)
        reset_response = views.reset_workspace.__wrapped__(request)

        self.assertEqual(clear_response.status_code, 405)
        self.assertEqual(reset_response.status_code, 405)
