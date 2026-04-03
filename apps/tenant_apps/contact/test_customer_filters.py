from django.contrib.auth import get_user_model
from django_tenants.test.cases import TenantTestCase

from .filters import CustomerFilter
from .models import Address, Customer


User = get_user_model()


class CustomerListFilterTests(TenantTestCase):
    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="contact-filter-owner",
            email="contact-filter-owner@example.com",
            password="testpass123",
        )
        tenant.name = "contact-filter-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
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
