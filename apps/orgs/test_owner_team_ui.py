import io
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from apps.tenancy.testing import WorkspaceTestCase
from apps.orgs.models import Membership, Role, CompanyInvitation
from apps.orgs.services.membership_capacity import SeatCapacitySnapshot


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"}, "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OwnerTeamUiTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "owner-team-ui"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.owner = get_user_model().objects.create_user(username="owner-ui", email="owner@example.com")
        tenant.owner = tenant.creator = cls.owner
        tenant.name = "Branch <North>"
        tenant.save()
        Membership.objects.create(company=tenant, user=cls.owner, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.staff = get_user_model().objects.create_user(username="staff-ui", email="staff@example.com")
        self.member_role = Role.objects.get_or_create(name="Member")[0]
        self.member = Membership.objects.create(company=self.tenant, user=self.staff, role=self.member_role)

    def url(self, suffix):
        return reverse("workspace_slug_settings" + suffix, kwargs={"workspace_slug": self.tenant.slug})

    def role_url(self):
        return reverse("team_change_role", kwargs={"workspace_id": self.tenant.pk, "membership_id": self.member.pk})

    def test_owner_pages_render_private_and_escape_branch(self):
        for suffix in ("", "_team", "_invitations", "_invite", "_profile", "_setup"):
            with self.subTest(suffix=suffix):
                response = self.client.get(self.url(suffix))
                self.assertEqual(response.status_code, 200)
                self.assertIn("no-store", response["Cache-Control"])
                self.assertContains(response, 'hx-history="false"')
                self.assertNotContains(response, "Branch <North>")

    @patch("apps.orgs.web.invitations.control_plane.send_team_invitation")
    def test_invitation_errors_preserve_input_and_never_send(self, send):
        initial = self.client.get(self.url("_invite"))
        self.assertContains(initial, f'<option value="{self.member_role.pk}">Member</option>', html=True)
        response = self.client.post(self.url("_invite"), {"email": "not-an-email", "role": self.member_role.pk, "company": self.tenant.pk, "inviter": self.owner.pk})
        self.assertContains(response, 'href="#id_email"')
        self.assertContains(response, 'value="not-an-email"')
        self.assertNotIn("django-select2", response.context["form"].fields["role"].widget.attrs.get("class", ""))
        send.assert_not_called()

    def test_invitation_capacity_uses_actual_snapshot_fields(self):
        invite = CompanyInvitation.create(email="invited@example.com", company=self.tenant, role=self.member_role, inviter=self.owner)
        with patch("apps.orgs.web.invitations.get_workspace_seat_capacity_snapshot", return_value=SeatCapacitySnapshot(limit=5, members_used=2, members_and_pending_used=3)):
            response = self.client.get(self.url("_invitations"))
        self.assertContains(response, "3/5")
        self.assertContains(response, "Seats remaining for invitations: 2")
        self.assertContains(response, reverse("team_delete_invitation", kwargs={"invitation_id": invite.pk}))
        self.assertNotContains(response, "No remaining seats")

    def test_role_change_requires_explicit_valid_post(self):
        response = self.client.get(self.role_url())
        self.assertContains(response, "Save role")
        self.assertNotContains(response, "hx-trigger")
        self.member.refresh_from_db()
        self.assertEqual(self.member.role_id, self.member_role.pk)
        owner_role = Role.objects.get(name="Owner")
        for data in ({}, {"role": owner_role.pk}, {"role": "invalid"}):
            response = self.client.post(self.role_url(), data)
            self.assertContains(response, 'href="#id_role"')
            self.member.refresh_from_db()
            self.assertEqual(self.member.role_id, self.member_role.pk)

    def test_role_change_still_uses_audited_service(self):
        with patch("apps.orgs.web.team_members.control_plane.change_membership_role") as change:
            response = self.client.post(self.role_url(), {"role": self.member_role.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(change.call_args.kwargs["actor"], self.owner)
        self.assertEqual(change.call_args.kwargs["new_role"], self.member_role)

    def test_staff_cannot_change_role_or_edit_profile(self):
        self.client.force_login(self.staff)
        for url in (self.role_url(), self.url("_profile")):
            response = self.client.post(url, {"role": self.member_role.pk, "name": "Changed"})
            self.assertEqual(response.status_code, 403)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Branch <North>")

    def test_profile_update_binds_uploaded_logo(self):
        buffer = io.BytesIO()
        Image.new("RGB", (8, 8), "blue").save(buffer, format="PNG")
        photo = SimpleUploadedFile("logo.png", buffer.getvalue(), content_type="image/png")
        with patch("apps.orgs.web.workspace_settings.control_plane.save_workspace_update_form") as save:
            response = self.client.post(self.url("_profile"), {"name": self.tenant.name, "theme": "#123456", "logo": photo})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(save.call_args.kwargs["form"].cleaned_data["logo"].name, "logo.png")

    def test_hindi_navigation_and_team_labels(self):
        self.client.cookies["django_language"] = "hi"
        response = self.client.get(self.url("_team"))
        self.assertContains(response, "टीम के सदस्य")
        self.assertContains(response, "नया ऋण")
        self.assertContains(response, "भूमिका बदलें")
