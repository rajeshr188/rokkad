import tempfile
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, override_settings
from django.urls import reverse
from apps.tenancy.testing import WorkspaceClient, WorkspaceTestCase

from apps.tenant_apps.party import views as party_views
from apps.orgs.models import Membership, Role
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

User = get_user_model()


@override_settings(
    ROOT_URLCONF="django_project.tenant_urls",
    MEDIA_ROOT=tempfile.mkdtemp(),
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class PartyUITests(WorkspaceTestCase):
    test_schema_name = f"party_ui_{uuid.uuid4().hex[:8]}"
    test_domain = f"party-ui-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="party-ui-owner",
            defaults={"email": "party-ui-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save()
        tenant.name = f"party-ui-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=user,
            company=tenant,
            defaults={"role": owner_role},
        )

    def setUp(self):
        super().setUp()
        self.client = WorkspaceClient(self.tenant)
        self.factory = RequestFactory()
        self.user = User.objects.get(username="party-ui-owner")
        self.client.login(username="party-ui-owner", password="testpass123")

    def _login_workspace_user(self, username, role_name):
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.com"},
        )
        user.set_password("testpass123")
        user.save()
        role, _ = Role.objects.get_or_create(name=role_name)
        Membership.objects.update_or_create(
            user=user,
            company=self.tenant,
            defaults={"role": role},
        )
        self.client.logout()
        self.client.login(username=username, password="testpass123")
        return user

    def test_party_list_search_displays_party(self):
        Party.objects.create(party_code="P1001", display_name="Asha Traders")

        response = self.client.get(reverse("party:party_list"), {"q": "Asha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha Traders")
        self.assertContains(response, "P1001")

    def test_party_list_allows_member_with_view_permission(self):
        Party.objects.create(party_code="P1001", display_name="Asha Traders")
        self._login_workspace_user("party-ui-member", "Member")

        response = self.client.get(reverse("party:party_list"), {"q": "Asha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha Traders")

    def test_party_list_denies_role_without_view_permission(self):
        user = self._login_workspace_user("party-ui-noaccess", "NoAccess")
        request = self.factory.get(reverse("party:party_list"))
        request.user = user
        request.workspace = self.tenant

        with self.assertRaises(PermissionDenied):
            party_views.party_list(request)

    def test_party_list_csv_export_uses_current_filters(self):
        borrower = PartyRoleType.objects.create(key="BORROWER", label="Borrower")
        asha = Party.objects.create(
            party_code="P1001",
            display_name="Asha Traders",
            primary_phone="+919999999999",
        )
        PartyRole.objects.create(party=asha, role_type=borrower)
        Party.objects.create(party_code="P1002", display_name="Bala Supplies")

        response = self.client.get(
            reverse("party:party_list"),
            {"q": "Asha", "role": "BORROWER", "_export": "csv"},
        )

        content = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn('attachment; filename="parties.csv"', response["Content-Disposition"])
        self.assertIn("party_code", content)
        self.assertIn("active_roles", content)
        self.assertIn("P1001", content)
        self.assertIn("Asha Traders", content)
        self.assertIn("Borrower", content)
        self.assertNotIn("P1002", content)

    def test_party_list_export_denies_member_without_export_permission(self):
        Party.objects.create(party_code="P1001", display_name="Asha Traders")
        user = self._login_workspace_user("party-ui-export-member", "Member")
        request = self.factory.get(reverse("party:party_list"), {"_export": "csv"})
        request.user = user
        request.workspace = self.tenant

        with self.assertRaisesMessage(PermissionDenied, "Party export permission is required."):
            party_views.party_list(request)

    def test_party_list_xlsx_export_returns_spreadsheet(self):
        Party.objects.create(party_code="P1001", display_name="Asha Traders")

        response = self.client.get(
            reverse("party:party_list"),
            {"_export": "xlsx"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertIn('attachment; filename="parties.xlsx"', response["Content-Disposition"])
        self.assertGreater(len(response.content), 0)

    def test_party_create_sets_audit_fields(self):
        response = self.client.post(
            reverse("party:party_create"),
            {
                "party_type": Party.PartyType.ORGANIZATION,
                "display_name": "Mehta Supplies",
                "legal_name": "",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )

        party = Party.objects.get(display_name="Mehta Supplies")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(party.party_code, "P-000001")
        self.assertEqual(party.created_by, self.user)
        self.assertEqual(party.updated_by, self.user)

    def test_party_create_allows_member_with_create_permission(self):
        self._login_workspace_user("party-ui-create-member", "Member")

        response = self.client.post(
            reverse("party:party_create"),
            {
                "party_type": Party.PartyType.ORGANIZATION,
                "display_name": "Member Created Party",
                "legal_name": "",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Party.objects.filter(display_name="Member Created Party").exists())

    def test_party_create_denies_role_without_create_permission(self):
        user = self._login_workspace_user("party-ui-create-noaccess", "NoAccess")
        request = self.factory.post(reverse("party:party_create"))
        request.user = user
        request.workspace = self.tenant

        with self.assertRaises(PermissionDenied):
            party_views.party_create(request)

    def test_party_create_preserves_manual_code(self):
        response = self.client.post(
            reverse("party:party_create"),
            {
                "party_code": "custom-100",
                "party_type": Party.PartyType.ORGANIZATION,
                "display_name": "Custom Code Party",
                "legal_name": "",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Party.objects.filter(party_code="CUSTOM-100").exists())

    def test_party_create_saves_textual_relation(self):
        response = self.client.post(
            reverse("party:party_create"),
            {
                "party_type": Party.PartyType.INDIVIDUAL,
                "display_name": "Relation Party",
                "legal_name": "",
                "relation_label": Party.RelationLabel.SON_OF,
                "relation_name": "Kumar",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )
        party = Party.objects.get(display_name="Relation Party")

        self.assertEqual(response.status_code, 302)
        self.assertTrue(party.party_code.startswith("P-"))
        self.assertEqual(party.relation_label, Party.RelationLabel.SON_OF)
        self.assertEqual(party.relation_name, "Kumar")
        self.assertEqual(party.relation_display, "S/o Kumar")

    def test_party_relation_label_and_name_are_required_together(self):
        response = self.client.post(
            reverse("party:party_create"),
            {
                "party_code": "p1016",
                "party_type": Party.PartyType.INDIVIDUAL,
                "display_name": "Invalid Relation Party",
                "legal_name": "",
                "relation_label": Party.RelationLabel.CARE_OF,
                "relation_name": "",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Relation label and related person name must be entered together.",
        )
        self.assertFalse(Party.objects.filter(party_code="P1016").exists())

    def test_party_detail_has_no_retired_accounting_tab(self):
        party = Party.objects.create(party_code="P1003", display_name="Nira Retail")

        response = self.client.get(reverse("party:party_detail", args=[party.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Accounts / Ledger")
        self.assertNotContains(response, "account mappings")
        self.assertContains(response, "Save Photo")
        self.assertContains(response, "Merge")

    def test_party_update_allows_member_with_edit_permission(self):
        party = Party.objects.create(party_code="P1018", display_name="Editable Party")
        self._login_workspace_user("party-ui-edit-member", "Member")

        response = self.client.post(
            reverse("party:party_update", args=[party.pk]),
            {
                "party_code": "P1018",
                "party_type": Party.PartyType.ORGANIZATION,
                "display_name": "Member Edited Party",
                "legal_name": "",
                "primary_phone": "",
                "primary_email": "",
                "tax_pan": "",
                "gstin": "",
                "risk_level": "",
                "status": Party.PartyStatus.ACTIVE,
            },
        )

        party.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(party.display_name, "Member Edited Party")

    def test_party_update_denies_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1019", display_name="Locked Party")
        user = self._login_workspace_user("party-ui-edit-noaccess", "NoAccess")
        request = self.factory.get(reverse("party:party_update", args=[party.pk]))
        request.user = user
        request.workspace = self.tenant

        with self.assertRaises(PermissionDenied):
            party_views.party_update(request, party.pk)

    def test_party_role_add_and_end(self):
        party = Party.objects.create(party_code="P1004", display_name="Ravi")
        role_type = PartyRoleType.objects.create(key="CUSTOMER", label="Customer")

        add_response = self.client.post(
            reverse("party:party_role_add", args=[party.pk]),
            {
                "role_type": role_type.pk,
                "segment": "RETAIL",
                "effective_from": "",
                "effective_to": "",
                "status": PartyRole.RoleStatus.ACTIVE,
            },
        )

        role = PartyRole.objects.get(party=party, role_type=role_type)
        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(role.segment, "RETAIL")
        self.assertEqual(role.status, PartyRole.RoleStatus.ACTIVE)

        end_response = self.client.post(
            reverse("party:party_role_end", args=[party.pk, role.pk])
        )
        role.refresh_from_db()

        self.assertEqual(end_response.status_code, 302)
        self.assertEqual(role.status, PartyRole.RoleStatus.ENDED)
        self.assertIsNotNone(role.effective_to)

    def test_role_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1028", display_name="Locked Role")
        role_type = PartyRoleType.objects.create(
            key="LOCKED_CUSTOMER",
            label="Locked Customer",
        )
        role = PartyRole.objects.create(party=party, role_type=role_type)
        user = self._login_workspace_user("party-ui-role-noaccess", "NoAccess")

        add_request = self.factory.post(reverse("party:party_role_add", args=[party.pk]))
        add_request.user = user
        add_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_role_add(add_request, party.pk)

        end_request = self.factory.post(reverse("party:party_role_end", args=[party.pk, role.pk]))
        end_request.user = user
        end_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_role_end(end_request, party.pk, role.pk)

    def test_profile_photo_upload_and_remove(self):
        party = Party.objects.create(party_code="P1005", display_name="Photo Party")
        image = SimpleUploadedFile(
            "avatar.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        upload_response = self.client.post(
            reverse("party:party_photo_update", args=[party.pk]),
            {"profile_photo": image},
        )
        party.refresh_from_db()

        self.assertEqual(upload_response.status_code, 302)
        self.assertTrue(party.profile_photo)

        remove_response = self.client.post(
            reverse("party:party_photo_remove", args=[party.pk])
        )
        party.refresh_from_db()

        self.assertEqual(remove_response.status_code, 302)
        self.assertFalse(party.profile_photo)

    def test_profile_photo_can_be_saved_from_camera_capture_data(self):
        party = Party.objects.create(party_code="P1017", display_name="Camera Party")
        image_data = "data:image/jpeg;base64,aGVsbG8="

        response = self.client.post(
            reverse("party:party_photo_update", args=[party.pk]),
            {"image_data": image_data},
        )
        party.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(party.profile_photo)

    def test_profile_photo_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1021", display_name="Locked Photo")
        user = self._login_workspace_user("party-ui-photo-noaccess", "NoAccess")

        update_request = self.factory.post(reverse("party:party_photo_update", args=[party.pk]))
        update_request.user = user
        update_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_profile_photo_update(update_request, party.pk)

        remove_request = self.factory.post(reverse("party:party_photo_remove", args=[party.pk]))
        remove_request.user = user
        remove_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_profile_photo_remove(remove_request, party.pk)

    def test_primary_contacts_sync_to_party_fields_and_delete_clears(self):
        party = Party.objects.create(party_code="P1006", display_name="Contact Party")

        first_response = self.client.post(
            reverse("party:party_contact_add", args=[party.pk]),
            {
                "contact_type": PartyContactMethod.ContactType.MOBILE,
                "label": "Main",
                "value": "9999999999",
                "is_primary": "on",
            },
        )
        first = PartyContactMethod.objects.get(value="+919999999999")
        party.refresh_from_db()

        self.assertEqual(first_response.status_code, 302)
        self.assertTrue(first.is_primary)
        self.assertEqual(first.value, "+919999999999")
        self.assertEqual(party.primary_phone, "+919999999999")

        second_response = self.client.post(
            reverse("party:party_contact_add", args=[party.pk]),
            {
                "contact_type": PartyContactMethod.ContactType.MOBILE,
                "label": "Alt",
                "value": "8888888888",
                "is_primary": "on",
            },
        )
        first.refresh_from_db()
        second = PartyContactMethod.objects.get(value="+918888888888")
        party.refresh_from_db()

        self.assertEqual(second_response.status_code, 302)
        self.assertFalse(first.is_primary)
        self.assertTrue(second.is_primary)
        self.assertEqual(party.primary_phone, "+918888888888")

        delete_response = self.client.post(
            reverse("party:party_contact_delete", args=[party.pk, second.pk])
        )
        party.refresh_from_db()

        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(party.primary_phone, "")

    def test_contact_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1022", display_name="Locked Contact")
        contact = PartyContactMethod.objects.create(
            party=party,
            contact_type=PartyContactMethod.ContactType.EMAIL,
            value="locked@example.com",
        )
        user = self._login_workspace_user("party-ui-contact-noaccess", "NoAccess")

        save_request = self.factory.post(reverse("party:party_contact_add", args=[party.pk]))
        save_request.user = user
        save_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_contact_save(save_request, party.pk)

        delete_request = self.factory.post(
            reverse("party:party_contact_delete", args=[party.pk, contact.pk])
        )
        delete_request.user = user
        delete_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_contact_delete(delete_request, party.pk, contact.pk)

    def test_invalid_phone_contact_returns_form_error(self):
        party = Party.objects.create(party_code="P1011", display_name="Bad Phone")

        response = self.client.post(
            reverse("party:party_contact_add", args=[party.pk]),
            {
                "contact_type": PartyContactMethod.ContactType.MOBILE,
                "label": "Bad",
                "value": "123",
                "is_primary": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enter a valid phone number")
        self.assertFalse(PartyContactMethod.objects.filter(party=party).exists())

    def test_primary_email_syncs_to_party_field(self):
        party = Party.objects.create(party_code="P1007", display_name="Email Party")

        response = self.client.post(
            reverse("party:party_contact_add", args=[party.pk]),
            {
                "contact_type": PartyContactMethod.ContactType.EMAIL,
                "label": "Office",
                "value": "office@example.com",
                "is_primary": "on",
            },
        )
        party.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(party.primary_email, "office@example.com")

    def test_default_address_conflict_is_resolved_cleanly(self):
        party = Party.objects.create(party_code="P1008", display_name="Address Party")

        self.client.post(
            reverse("party:party_address_add", args=[party.pk]),
            {
                "address_type": PartyAddress.AddressType.BILLING,
                "line1": "First Street",
                "line2": "",
                "area": "",
                "city": "Chennai",
                "state": "TN",
                "postal_code": "600001",
                "country": "IN",
                "is_default": "on",
            },
        )
        self.client.post(
            reverse("party:party_address_add", args=[party.pk]),
            {
                "address_type": PartyAddress.AddressType.BILLING,
                "line1": "Second Street",
                "line2": "",
                "area": "",
                "city": "Chennai",
                "state": "TN",
                "postal_code": "600002",
                "country": "IN",
                "is_default": "on",
            },
        )

        addresses = PartyAddress.objects.filter(
            party=party,
            address_type=PartyAddress.AddressType.BILLING,
            is_default=True,
        )
        self.assertEqual(addresses.count(), 1)
        self.assertEqual(addresses.get().line1, "Second Street")

    def test_address_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1023", display_name="Locked Address")
        address = PartyAddress.objects.create(
            party=party,
            address_type=PartyAddress.AddressType.BILLING,
            line1="Locked Street",
            city="Chennai",
            country="IN",
        )
        user = self._login_workspace_user("party-ui-address-noaccess", "NoAccess")

        save_request = self.factory.post(reverse("party:party_address_add", args=[party.pk]))
        save_request.user = user
        save_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_address_save(save_request, party.pk)

        delete_request = self.factory.post(
            reverse("party:party_address_delete", args=[party.pk, address.pk])
        )
        delete_request.user = user
        delete_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_address_delete(delete_request, party.pk, address.pk)

    def test_duplicate_identifier_type_returns_form_error(self):
        party = Party.objects.create(party_code="P1009", display_name="KYC Party")
        PartyIdentifier.objects.create(
            party=party,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )

        response = self.client.post(
            reverse("party:party_identifier_add", args=[party.pk]),
            {
                "identifier_type": PartyIdentifier.IdentifierType.PAN,
                "value": "ZZZZZ9999Z",
                "masked_value": "",
                "expires_on": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This party already has an identifier of this type.",
        )
        self.assertEqual(PartyIdentifier.objects.filter(party=party).count(), 1)

    def test_identifier_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1024", display_name="Locked Identifier")
        identifier = PartyIdentifier.objects.create(
            party=party,
            identifier_type=PartyIdentifier.IdentifierType.PAN,
            value="ABCDE1234F",
        )
        user = self._login_workspace_user("party-ui-identifier-noaccess", "NoAccess")

        save_request = self.factory.post(reverse("party:party_identifier_add", args=[party.pk]))
        save_request.user = user
        save_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_identifier_save(save_request, party.pk)

        delete_request = self.factory.post(
            reverse("party:party_identifier_delete", args=[party.pk, identifier.pk])
        )
        delete_request.user = user
        delete_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_identifier_delete(delete_request, party.pk, identifier.pk)

    def test_document_upload_can_link_to_identifier(self):
        party = Party.objects.create(party_code="P1010", display_name="Doc Party")
        identifier = PartyIdentifier.objects.create(
            party=party,
            identifier_type=PartyIdentifier.IdentifierType.GSTIN,
            value="29ABCDE1234F1Z5",
        )
        file = SimpleUploadedFile(
            "gst.txt",
            b"gst certificate",
            content_type="text/plain",
        )

        response = self.client.post(
            reverse("party:party_document_add", args=[party.pk]),
            {
                "document_type": PartyDocument.DocumentType.TAX,
                "title": "GST Certificate",
                "identifier": identifier.pk,
                "file": file,
                "expires_on": "",
            },
        )
        document = PartyDocument.objects.get(party=party)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(document.identifier, identifier)
        self.assertTrue(document.file)

    def test_document_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1025", display_name="Locked Document")
        document = PartyDocument.objects.create(
            party=party,
            document_type=PartyDocument.DocumentType.OTHER,
            title="Locked Document",
        )
        user = self._login_workspace_user("party-ui-document-noaccess", "NoAccess")

        save_request = self.factory.post(reverse("party:party_document_add", args=[party.pk]))
        save_request.user = user
        save_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_document_save(save_request, party.pk)

        delete_request = self.factory.post(
            reverse("party:party_document_delete", args=[party.pk, document.pk])
        )
        delete_request.user = user
        delete_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_document_delete(delete_request, party.pk, document.pk)

    def test_party_relationship_add_edit_and_delete(self):
        party = Party.objects.create(party_code="P1012", display_name="Source Party")
        related = Party.objects.create(party_code="P1013", display_name="Related Party")

        add_response = self.client.post(
            reverse("party:party_relationship_add", args=[party.pk]),
            {
                "relationship_type": PartyRelationship.RelationshipType.CONTACT_PERSON,
                "to_party": related.pk,
                "notes": "Manager",
                "is_active": "on",
            },
        )
        relationship = PartyRelationship.objects.get(from_party=party, to_party=related)

        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(
            relationship.relationship_type,
            PartyRelationship.RelationshipType.CONTACT_PERSON,
        )
        self.assertEqual(relationship.notes, "Manager")

        update_response = self.client.post(
            reverse("party:party_relationship_update", args=[party.pk, relationship.pk]),
            {
                "relationship_type": PartyRelationship.RelationshipType.AGENT,
                "to_party": related.pk,
                "notes": "Field agent",
                "is_active": "",
            },
        )
        relationship.refresh_from_db()

        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(relationship.relationship_type, PartyRelationship.RelationshipType.AGENT)
        self.assertEqual(relationship.notes, "Field agent")
        self.assertFalse(relationship.is_active)

        delete_response = self.client.post(
            reverse("party:party_relationship_delete", args=[party.pk, relationship.pk])
        )

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(PartyRelationship.objects.filter(pk=relationship.pk).exists())

    def test_relationship_mutations_deny_role_without_edit_permission(self):
        party = Party.objects.create(party_code="P1026", display_name="Locked Relation")
        related = Party.objects.create(party_code="P1027", display_name="Related Lock")
        relationship = PartyRelationship.objects.create(
            from_party=party,
            to_party=related,
            relationship_type=PartyRelationship.RelationshipType.CONTACT_PERSON,
        )
        user = self._login_workspace_user("party-ui-relationship-noaccess", "NoAccess")

        save_request = self.factory.post(reverse("party:party_relationship_add", args=[party.pk]))
        save_request.user = user
        save_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_relationship_save(save_request, party.pk)

        delete_request = self.factory.post(
            reverse("party:party_relationship_delete", args=[party.pk, relationship.pk])
        )
        delete_request.user = user
        delete_request.workspace = self.tenant
        with self.assertRaises(PermissionDenied):
            party_views.party_relationship_delete(
                delete_request,
                party.pk,
                relationship.pk,
            )

    def test_party_relationship_rejects_self_reference(self):
        party = Party.objects.create(party_code="P1014", display_name="Self Party")

        response = self.client.post(
            reverse("party:party_relationship_add", args=[party.pk]),
            {
                "relationship_type": PartyRelationship.RelationshipType.FAMILY,
                "to_party": party.pk,
                "notes": "",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(PartyRelationship.objects.filter(from_party=party).exists())

    def test_party_merge_view_archives_duplicate(self):
        target = Party.objects.create(party_code="P1018", display_name="Merge Target")
        source = Party.objects.create(party_code="P1019", display_name="Merge Source")
        PartyContactMethod.objects.create(
            party=source,
            contact_type=PartyContactMethod.ContactType.EMAIL,
            value="merge@example.com",
        )

        response = self.client.post(
            reverse("party:party_merge", args=[target.pk]),
            {"source_party": source.pk, "confirm": "on"},
        )
        source.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(source.status, Party.PartyStatus.ARCHIVED)
        self.assertTrue(
            PartyContactMethod.objects.filter(
                party=target,
                value="merge@example.com",
            ).exists()
        )

    def test_party_merge_denies_role_without_edit_permission(self):
        target = Party.objects.create(party_code="P1029", display_name="Locked Merge Target")
        source = Party.objects.create(party_code="P1030", display_name="Locked Merge Source")
        user = self._login_workspace_user("party-ui-merge-noaccess", "NoAccess")
        request = self.factory.post(
            reverse("party:party_merge", args=[target.pk]),
            {"source_party": source.pk, "confirm": "on"},
        )
        request.user = user
        request.workspace = self.tenant

        with self.assertRaises(PermissionDenied):
            party_views.party_merge(request, target.pk)
