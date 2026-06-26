import tempfile
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from django_tenants.test.client import TenantClient

from apps.orgs.models import Membership, Role
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import GivenLoan, License, LoanItem, Release, Series, TakenLoan
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
)
class PartyUITests(TenantTestCase):
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
        connection.set_tenant(self.tenant)
        self.client = TenantClient(self.tenant)
        self.user = User.objects.get(username="party-ui-owner")
        self.client.login(username="party-ui-owner", password="testpass123")

    def test_party_list_search_displays_party(self):
        Party.objects.create(party_code="P1001", display_name="Asha Traders")

        response = self.client.get(reverse("party:party_list"), {"q": "Asha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Asha Traders")
        self.assertContains(response, "P1001")

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

        connection.set_tenant(self.tenant)
        party = Party.objects.get(display_name="Mehta Supplies")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(party.party_code, "P-000001")
        self.assertEqual(party.created_by, self.user)
        self.assertEqual(party.updated_by, self.user)

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
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Relation label and related person name must be entered together.",
        )
        self.assertFalse(Party.objects.filter(party_code="P1016").exists())

    def test_party_detail_displays_accounts_tab_without_mappings(self):
        party = Party.objects.create(party_code="P1003", display_name="Nira Retail")

        response = self.client.get(reverse("party:party_detail", args=[party.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Accounts / Ledger")
        self.assertContains(response, "No account mappings found.")
        self.assertContains(response, "Save Photo")
        self.assertContains(response, "Merge")

    def test_party_detail_loans_tab_shows_active_closed_with_operational_metrics(self):
        party = Party.objects.create(party_code="P1020", display_name="Loan Party")
        customer = Customer.objects.create(firstname="Loan", lastname="Customer", party=party)

        license_record = License.objects.create(
            name="Loan Party License",
            license_number=f"LPL-{uuid.uuid4().hex[:6]}",
        )
        given_series = Series.objects.create(
            license=license_record,
            name="Given Series",
            prefix="LG",
            loan_type=Series.LoanType.GIVEN,
        )
        taken_series = Series.objects.create(
            license=license_record,
            name="Taken Series",
            prefix="LT",
            loan_type=Series.LoanType.TAKEN,
        )

        active_given = GivenLoan.objects.create(
            loan_id="LG0001",
            series=given_series,
            borrower=customer,
            status="Draft",
        )
        LoanItem.objects.create(
            loan=active_given,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("91.60"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Ring",
        )
        active_given.status = "ActiveCurrent"
        active_given.save(update_fields=["status"])

        closed_given = GivenLoan.objects.create(
            loan_id="LG0002",
            series=given_series,
            borrower=customer,
            status="Draft",
        )
        LoanItem.objects.create(
            loan=closed_given,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("5.000"),
            purity=Decimal("91.60"),
            loanamount=Decimal("500.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Chain",
        )
        closed_given.status = "Closed"
        closed_given.save(update_fields=["status"])
        Release.objects.create(
            loan=closed_given,
            created_by=self.user,
            released_by=customer,
        )

        TakenLoan.objects.create(
            loan_id="LT0001",
            series=taken_series,
            lender=customer,
            status="Closed",
        )

        response = self.client.get(reverse("party:party_detail", args=[party.pk]), {"tab": "loans"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Loans")
        self.assertContains(response, "Closed Loans")
        self.assertContains(response, "Payments")
        self.assertContains(response, "Notices")
        self.assertContains(response, "Active Outstanding")
        self.assertContains(response, "Final Outstanding")
        self.assertContains(response, "Collateral Items")
        self.assertContains(response, "LG0001")
        self.assertContains(response, "LG0002")
        self.assertContains(response, "LT0001")
        self.assertContains(response, "Repay")
        self.assertContains(response, "Form H")

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

        connection.set_tenant(self.tenant)
        role = PartyRole.objects.get(party=party, role_type=role_type)
        self.assertEqual(add_response.status_code, 302)
        self.assertEqual(role.segment, "RETAIL")
        self.assertEqual(role.status, PartyRole.RoleStatus.ACTIVE)

        end_response = self.client.post(
            reverse("party:party_role_end", args=[party.pk, role.pk])
        )
        connection.set_tenant(self.tenant)
        role.refresh_from_db()

        self.assertEqual(end_response.status_code, 302)
        self.assertEqual(role.status, PartyRole.RoleStatus.ENDED)
        self.assertIsNotNone(role.effective_to)

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
        connection.set_tenant(self.tenant)
        party.refresh_from_db()

        self.assertEqual(upload_response.status_code, 302)
        self.assertTrue(party.profile_photo)

        remove_response = self.client.post(
            reverse("party:party_photo_remove", args=[party.pk])
        )
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)
        party.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(party.profile_photo)

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
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)
        party.refresh_from_db()

        self.assertEqual(delete_response.status_code, 302)
        self.assertEqual(party.primary_phone, "")

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
        connection.set_tenant(self.tenant)

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
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)

        addresses = PartyAddress.objects.filter(
            party=party,
            address_type=PartyAddress.AddressType.BILLING,
            is_default=True,
        )
        self.assertEqual(addresses.count(), 1)
        self.assertEqual(addresses.get().line1, "Second Street")

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
        connection.set_tenant(self.tenant)

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "This party already has an identifier of this type.",
        )
        self.assertEqual(PartyIdentifier.objects.filter(party=party).count(), 1)

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
        connection.set_tenant(self.tenant)
        document = PartyDocument.objects.get(party=party)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(document.identifier, identifier)
        self.assertTrue(document.file)

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
        connection.set_tenant(self.tenant)
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
        connection.set_tenant(self.tenant)
        relationship.refresh_from_db()

        self.assertEqual(update_response.status_code, 302)
        self.assertEqual(relationship.relationship_type, PartyRelationship.RelationshipType.AGENT)
        self.assertEqual(relationship.notes, "Field agent")
        self.assertFalse(relationship.is_active)

        delete_response = self.client.post(
            reverse("party:party_relationship_delete", args=[party.pk, relationship.pk])
        )
        connection.set_tenant(self.tenant)

        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(PartyRelationship.objects.filter(pk=relationship.pk).exists())

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
        connection.set_tenant(self.tenant)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Select a valid choice")
        self.assertFalse(PartyRelationship.objects.filter(from_party=party).exists())

    def test_convert_customer_view_creates_party_link(self):
        customer = Customer.objects.create(
            firstname="Convert",
            lastname="Customer",
            email="convert@example.com",
        )

        response = self.client.post(
            reverse("party:party_customer_convert"),
            {"customer": customer.pk},
        )
        connection.set_tenant(self.tenant)
        customer.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertIsNotNone(customer.party_id)
        self.assertEqual(customer.party.display_name, "Convert Customer")

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
        connection.set_tenant(self.tenant)
        source.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(source.status, Party.PartyStatus.ARCHIVED)
        self.assertTrue(
            PartyContactMethod.objects.filter(
                party=target,
                value="merge@example.com",
            ).exists()
        )
