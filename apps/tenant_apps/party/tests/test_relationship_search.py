"""Relationship selection reuses Party search without broadening its authority."""

import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.party.models import Party, PartyRelationship
from apps.tenant_apps.party.widgets import (
    PartyAutocompleteWidget,
    PartyRelationshipAutocompleteWidget,
)


@override_settings(ROOT_URLCONF="django_project.workspace_urls")
class RelationshipSearchTests(WorkspaceTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        owner = get_user_model().objects.create_user(
            username="relationship-search-owner"
        )
        tenant.owner = tenant.creator = owner
        tenant.save()
        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(company=tenant, user=owner, role=role)

    def setUp(self):
        super().setUp()
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.tenant.owner)
        self.party = Party.objects.create(display_name="Search source")
        self.related = Party.objects.create(
            display_name="Search related",
            party_code="REL-101",
            primary_phone="+919999999999",
            primary_email="related@example.test",
            relation_name="Ramesh",
            status="INACTIVE",
        )
        self.url = reverse(
            "workspace_party:party_relationship_autocomplete",
            args=[self.tenant.slug, self.party.pk],
        )
        self.token = signing.dumps(self.url, salt=PartyAutocompleteWidget.token_salt)

    def search(self, term="Search", **overrides):
        return self.client.get(
            self.url, {"field_id": self.token, "term": term, **overrides}
        )

    def test_form_loads_selected_party_only_and_preserves_validation(self):
        detail = reverse(
            "workspace_party:party_detail", args=[self.tenant.slug, self.party.pk]
        )
        response = self.client.get(detail, {"tab": "relationships"})
        field = response.context["relationship_form"].fields["to_party"]
        self.assertIsInstance(field.widget, PartyRelationshipAutocompleteWidget)
        self.assertContains(response, self.url)
        self.assertNotIn(
            f'<option value="{self.related.pk}"',
            str(response.context["relationship_form"]["to_party"]),
        )
        save = reverse(
            "workspace_party:party_relationship_add",
            args=[self.tenant.slug, self.party.pk],
        )
        invalid = self.client.post(save, {"to_party": self.related.pk})
        self.assertContains(invalid, f'<option value="{self.related.pk}" selected>')
        self.assertIn("relationship_type", invalid.context["relationship_form"].errors)
        payload = {
            "to_party": self.related.pk,
            "relationship_type": "FAMILY",
            "is_active": "on",
        }
        self.assertEqual(self.client.post(save, payload).status_code, 302)
        relation = PartyRelationship.objects.get(from_party=self.party)
        edit = self.client.get(
            detail, {"tab": "relationships", "edit_relationship": relation.pk}
        )
        self.assertContains(edit, f'<option value="{self.related.pk}" selected>')
        duplicate = self.client.post(save, payload)
        self.assertContains(duplicate, "This relationship already exists")
        self.assertEqual(
            PartyRelationship.objects.filter(from_party=self.party).count(), 1
        )
        self.assertEqual(
            self.client.post(save, payload | {"to_party": self.party.pk}).status_code,
            200,
        )

    def test_search_matches_party_details_and_retains_existing_status_eligibility(self):
        from django.core.cache import cache

        cache.clear()
        for term in ("related", "REL-101", "999999", "Ramesh", "related@example"):
            response = self.search(term)
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(
                [row["id"] for row in response.json()["results"]], [self.related.pk]
            )
        archived = Party.objects.create(
            display_name="Search archived", status="ARCHIVED"
        )
        blocked = Party.objects.create(display_name="Search blocked", status="BLOCKED")
        self.assertEqual(
            {row["id"] for row in self.search().json()["results"]},
            {self.related.pk, archived.pk, blocked.pk},
        )
        for index in range(30):
            Party.objects.create(display_name=f"Paged relationship {index:02}")
        first = self.search("Paged", page=1).json()
        second = self.search("Paged", page=2).json()
        self.assertTrue(first["more"])
        self.assertFalse(second["more"])
        self.assertEqual(
            len({row["id"] for row in first["results"] + second["results"]}), 30
        )

    def test_tokens_bind_source_workspace_and_expiry(self):
        for path in (
            self.url.replace(
                str(self.party.pk) + "/relationships/",
                str(self.related.pk) + "/relationships/",
            ),
            self.url.replace(self.tenant.slug, "another-workspace"),
            reverse("workspace_party:party_autocomplete", args=[self.tenant.slug]),
        ):
            token = signing.dumps(path, salt=PartyAutocompleteWidget.token_salt)
            self.assertEqual(self.search(field_id=token).status_code, 404)
        self.assertEqual(self.search(field_id="invalid").status_code, 404)
        with patch("django.core.signing.time.time", return_value=time.time() + 86401):
            self.assertEqual(self.search().status_code, 404)

    def test_search_and_submit_exclude_other_workspaces(self):
        other = Company.objects.create(
            name="Other relationship workspace",
            owner=self.tenant.owner,
            creator=self.tenant.owner,
        )
        with without_workspace_context(), workspace_context(other.pk):
            foreign = Party.objects.create(display_name="Search foreign")
        self.assertEqual(self.search("foreign").json()["results"], [])
        foreign_url = reverse(
            "workspace_party:party_relationship_autocomplete",
            args=[self.tenant.slug, foreign.pk],
        )
        token = signing.dumps(foreign_url, salt=PartyAutocompleteWidget.token_salt)
        self.assertEqual(
            self.client.get(foreign_url, {"field_id": token}).status_code, 404
        )
        save = reverse(
            "workspace_party:party_relationship_add",
            args=[self.tenant.slug, self.party.pk],
        )
        response = self.client.post(
            save, {"relationship_type": "FAMILY", "to_party": foreign.pk}
        )
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(
            PartyRelationship.objects.filter(from_party=self.party).exists()
        )

    def test_search_requires_relationship_edit_permission_and_login(self):
        viewer = get_user_model().objects.create_user(username="relationship-viewer")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.create(company=self.tenant, user=viewer, role=role)
        self.client.force_login(viewer)
        self.assertEqual(self.search().status_code, 403)
        self.client.logout()
        self.assertEqual(self.search().status_code, 302)
