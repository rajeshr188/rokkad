from apps.tenancy.testing import workspace_role_permissions
import uuid

from django.contrib.auth import get_user_model
from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.party.models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyDocument,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
    PartyRoleType,
)
from apps.tenant_apps.party.services.party_merge import merge_parties


User = get_user_model()


class PartyMergeTests(WorkspaceTestCase):
    test_schema_name = f"party_merge_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="party-merge-owner",
            defaults={"email": "party-merge-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"party-merge-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        self.actor = self.tenant.owner
        role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.get_or_create(user=self.actor, company=self.tenant, defaults={"role": role})

    def test_merge_moves_profile_children_and_archives_source(self):
        target = Party.objects.create(
            party_code="P-MERGE-T",
            display_name="Target Party",
            primary_phone="+919999999999",
        )
        source = Party.objects.create(
            party_code="P-MERGE-S",
            display_name="Source Party",
            primary_email="source@example.com",
        )
        role_type = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")
        PartyRole.objects.create(party=source, role_type=role_type)
        PartyContactMethod.objects.create(
            party=source,
            contact_type=PartyContactMethod.ContactType.EMAIL,
            value="source@example.com",
            is_primary=True,
        )
        PartyAddress.objects.create(
            party=source,
            address_type=PartyAddress.AddressType.HOME,
            line1="Source Street",
            city="Chennai",
            is_default=True,
        )
        identifier = PartyIdentifier.objects.create(
            party=source,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        PartyDocument.objects.create(
            party=source,
            document_type=PartyDocument.DocumentType.KYC,
            title="PAN Copy",
            identifier=identifier,
        )
        related = Party.objects.create(party_code="P-REL", display_name="Related")
        PartyRelationship.objects.create(
            from_party=source,
            to_party=related,
            relationship_type=PartyRelationship.RelationshipType.FAMILY,
        )

        result = merge_parties(target=target, source=source, actor=self.actor)
        target.refresh_from_db()
        source.refresh_from_db()

        self.assertEqual(source.status, Party.PartyStatus.ARCHIVED)
        self.assertEqual(target.primary_email, "source@example.com")
        self.assertEqual(result.roles_moved, 1)
        self.assertEqual(target.contact_methods.count(), 1)
        self.assertEqual(target.addresses.count(), 1)
        self.assertEqual(target.identifiers.count(), 1)
        self.assertEqual(target.documents.count(), 1)
        self.assertEqual(target.relationships_from.count(), 1)
        self.assertIn(source.pk, target.metadata["merged_from_party_ids"])
        self.assertEqual(source.metadata["merged_into_party_id"], target.pk)

    def test_merge_repoints_documents_when_identifier_already_exists(self):
        target = Party.objects.create(party_code="P-ID-T", display_name="Target")
        source = Party.objects.create(party_code="P-ID-S", display_name="Source")
        target_identifier = PartyIdentifier.objects.create(
            party=target,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        source_identifier = PartyIdentifier.objects.create(
            party=source,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        document = PartyDocument.objects.create(
            party=source,
            document_type=PartyDocument.DocumentType.KYC,
            title="PAN Copy",
            identifier=source_identifier,
        )

        merge_parties(target=target, source=source, actor=self.actor)
        document.refresh_from_db()

        self.assertEqual(document.party, target)
        self.assertEqual(document.identifier, target_identifier)

    def test_merge_denial_preserves_both_profiles(self):
        from django.core.exceptions import PermissionDenied
        target = Party.objects.create(display_name="Target")
        source = Party.objects.create(display_name="Source", primary_email="source@example.com")
        role, _ = Role.objects.get_or_create(name="Viewer")
        Membership.objects.filter(user=self.actor, company=self.tenant).update(role=role)
        for actor in (None, self.actor):
            with self.assertRaises(PermissionDenied):
                merge_parties(target=target, source=source, actor=actor)
        Membership.objects.filter(user=self.actor, company=self.tenant).delete()
        with self.assertRaises(PermissionDenied):
            merge_parties(target=target, source=source, actor=self.actor)
        target.refresh_from_db()
        source.refresh_from_db()
        self.assertFalse(target.primary_email)
        self.assertEqual(source.status, Party.PartyStatus.ACTIVE)
        self.assertNotIn("merged_into_party_id", source.metadata)

    def test_each_existing_edit_alias_can_merge_and_scope_mismatch_is_denied(self):
        from types import SimpleNamespace
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.core.exceptions import PermissionDenied
        from apps.orgs.models import Company
        for code in ("contact_edit", "data_edit"):
            role = Role.objects.create(name="MergeDelegate-" + uuid.uuid4().hex[:8])
            permission, _ = Permission.objects.get_or_create(
                content_type=ContentType.objects.get_for_model(Company), codename=code,
                defaults={"name": code})
            workspace_role_permissions(role, self.tenant).add(permission)
            Membership.objects.filter(user=self.actor, company=self.tenant).update(role=role)
            target = Party.objects.create(display_name="Target")
            source = Party.objects.create(display_name="Source")
            with self.assertRaises(PermissionDenied):
                merge_parties(target=target, source=SimpleNamespace(workspace_id=self.tenant.pk + 1), actor=self.actor)
            merge_parties(target=target, source=source, actor=self.actor)
            source.refresh_from_db()
            self.assertEqual(source.metadata["merged_by_user_id"], self.actor.pk)
