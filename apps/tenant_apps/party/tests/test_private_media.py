from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import Http404
from django.test import RequestFactory, TestCase, override_settings

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import workspace_role_permissions
from apps.tenant_apps.party.models import Party, PartyDocument
from apps.tenant_apps.party.views import party_document_download, party_profile_photo


class PrivatePartyMediaTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=directory))
        self.user = get_user_model().objects.create_user(username="media-owner")
        self.role, _ = Role.objects.get_or_create(name="Viewer")
        self.workspaces = []
        for index in range(2):
            workspace = Company.objects.create(
                name=f"Media {index}", schema_name=f"media-{index}",
                slug=f"media-{index}", owner=self.user, creator=self.user,
            )
            Membership.objects.create(company=workspace, user=self.user, role=self.role)
            self.workspaces.append(workspace)
        self.workspace = self.workspaces[0]
        with workspace_context(self.workspace.pk):
            self.party = Party.objects.create(party_code="PHOTO", display_name="Photo borrower")
            self.party.profile_photo.save("photo.png", ContentFile(b"photo evidence"))
            self.document = PartyDocument.objects.create(party=self.party, title="KYC")
            self.document.file.save("kyc.pdf", ContentFile(b"document evidence"))

    @staticmethod
    def close_response(response):
        # RequestFactory has no client handler to isolate request-finished signals.
        with patch("django.http.response.signals.request_finished.send"):
            response.close()

    def request(self, workspace=None, user=None):
        request = RequestFactory().get("/w/media-0/party/1/photo/view/")
        request.workspace = workspace or self.workspace
        request.user = self.user if user is None else user
        return request

    def calls(self, request):
        return (
            (party_profile_photo, (request, self.party.pk)),
            (party_document_download, (request, self.party.pk, self.document.pk)),
        )

    def test_authorized_files_and_private_cache_headers(self):
        with workspace_context(self.workspace.pk):
            for (view, args), content in zip(self.calls(self.request()), (b"photo evidence", b"document evidence")):
                response = view(*args)
                try:
                    self.assertEqual(b"".join(response.streaming_content), content)
                    self.assertIn("no-store", response["Cache-Control"])
                    self.assertEqual(response["X-Content-Type-Options"], "nosniff")
                finally:
                    self.close_response(response)
            response = party_document_download(self.request(), self.party.pk, self.document.pk)
            self.assertIn("attachment", response["Content-Disposition"])
            self.close_response(response)

    def test_anonymous_removed_and_revoked_members_cannot_read(self):
        with workspace_context(self.workspace.pk):
            for view, args in self.calls(self.request(user=AnonymousUser())):
                self.assertEqual(view(*args).status_code, 302)
            workspace_role_permissions(self.role, self.workspace).clear()
            for view, args in self.calls(self.request()):
                with self.assertRaises(PermissionDenied):
                    view(*args)
            Membership.objects.filter(company=self.workspace, user=self.user).delete()
            for view, args in self.calls(self.request()):
                with self.assertRaises(PermissionDenied):
                    view(*args)

    def test_other_workspace_and_wrong_parent_are_hidden(self):
        other = self.workspaces[1]
        with workspace_context(other.pk):
            for view, args in self.calls(self.request(workspace=other)):
                with self.assertRaises(Http404):
                    view(*args)
        with workspace_context(self.workspace.pk):
            with self.assertRaises(Http404):
                party_document_download(self.request(), self.party.pk + 100, self.document.pk)

    def test_missing_storage_file_returns_404(self):
        with workspace_context(self.workspace.pk):
            self.party.profile_photo.storage.delete(self.party.profile_photo.name)
            with self.assertRaises(Http404):
                party_profile_photo(self.request(), self.party.pk)

    def test_upload_widgets_do_not_emit_storage_links(self):
        from apps.tenant_apps.party.forms import PartyForm, PartyProfilePhotoForm, PartyDocumentForm

        with workspace_context(self.workspace.pk):
            for form, field in (
                (PartyForm(instance=self.party), "profile_photo"),
                (PartyProfilePhotoForm(instance=self.party), "profile_photo"),
                (PartyDocumentForm(instance=self.document, party=self.party), "file"),
            ):
                html = str(form[field])
                self.assertIn("File saved", html)
                self.assertNotIn("/media/", html)
                self.assertIn("-clear", html)
