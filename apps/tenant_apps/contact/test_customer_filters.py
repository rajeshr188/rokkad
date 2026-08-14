import uuid
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django_tenants.test.cases import TenantTestCase

from .document_services import mask_proof_number
from .filters import CustomerFilter
from .models import Address, Contact, Customer, Proof
from .services import CustomerLoanSummary
from apps.tenant_apps.girvi.models import GivenLoan, License, LoanItem, Series


User = get_user_model()


class CustomerListFilterTests(TenantTestCase):
    test_schema_name = f"contact_filter_{uuid.uuid4().hex[:8]}"
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
            username="contact-filter-owner",
            defaults={"email": "contact-filter-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"contact-filter-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.customer_one = Customer.objects.create(firstname="Anita", lastname="Rao")
        self.customer_two = Customer.objects.create(firstname="Bala", lastname="Kumar")

        Address.objects.create(
            customer=self.customer_one,
            door_number="12A",
            street="Market Road",
            area="Lakshmi Nagar",
            city="Chennai",
            state="TN",
            zip_code="600001",
            is_default=True,
        )
        Address.objects.create(
            customer=self.customer_two,
            door_number="44",
            street="Temple Street",
            area="Mylapore",
            city="Chennai",
            state="TN",
            zip_code="600002",
            is_default=True,
        )

    def test_customer_filter_can_filter_by_area_and_street(self):
        by_area = CustomerFilter(
            {"area": "Lakshmi"}, queryset=Customer.objects.all()
        ).qs
        by_street = CustomerFilter(
            {"street": "Temple"}, queryset=Customer.objects.all()
        ).qs

        self.assertQuerySetEqual(by_area.order_by("id"), [self.customer_one], transform=lambda obj: obj)
        self.assertQuerySetEqual(by_street.order_by("id"), [self.customer_two], transform=lambda obj: obj)

    def test_customer_save_does_not_require_dea_account_creation(self):
        with mock.patch(
            "apps.tenant_apps.dea.facade.ensure_customer_account",
            side_effect=AssertionError("DEA account creation should not run"),
        ):
            customer = Customer.objects.create(firstname="No", lastname="Accounting")

        self.assertEqual(customer.name, "No Accounting")

    def test_customer_merge_moves_given_loans_to_surviving_customer(self):
        license_obj = License.objects.create(
            name="Pawn Broker License",
            license_number="PBL-CONTACT-MERGE",
        )
        series = Series.objects.create(
            license=license_obj,
            name="A",
            prefix="A",
            max_limit=5,
        )
        loan = GivenLoan.objects.create(
            loan_id="A00001",
            series=series,
            borrower=self.customer_two,
        )
        LoanItem.objects.create(
            loan=loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("75.00"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Ring",
        )

        self.customer_one.merge(self.customer_two)
        loan.refresh_from_db()

        self.assertEqual(loan.borrower, self.customer_one)
        self.assertEqual(self.customer_one.get_loans_count, 1)
        self.assertEqual(self.customer_one.get_total_loanamount(), 1000)
        self.assertEqual(self.customer_one.get_interestdue(), 20)

        summary = CustomerLoanSummary(self.customer_one)
        self.assertEqual(summary.loans_count, 1)
        self.assertEqual(summary.total_loan_amount, Decimal("1000.00"))
        self.assertEqual(summary.base_interest_due, Decimal("20.00"))

    def test_default_contact_is_database_enforced(self):
        Contact.objects.create(
            customer=self.customer_one,
            phone_number="+919876543210",
            contact_type=Contact.ContactType.Mobile,
            is_default=True,
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            Contact.objects.bulk_create(
                [
                    Contact(
                        customer=self.customer_one,
                        phone_number="+919876543211",
                        contact_type=Contact.ContactType.Home,
                        is_default=True,
                    )
                ]
            )

    def test_proof_number_is_normalized_masked_and_deduplicated(self):
        proof = Proof.objects.create(
            customer=self.customer_one,
            proof_type=Proof.DocType.PAN,
            proof_number="abcde 1234 f",
        )

        self.assertEqual(proof.proof_number, "ABCDE1234F")
        self.assertEqual(proof.masked_proof_number, "ABXXX1234X")
        self.assertEqual(mask_proof_number(Proof.DocType.AADHAR, "1234 5678 9012"), "XXXX-XXXX-9012")

        duplicate = Proof(
            customer=self.customer_two,
            proof_type=Proof.DocType.PAN,
            proof_number="ABCDE1234F",
        )
        with self.assertRaises(ValidationError):
            duplicate.full_clean()
