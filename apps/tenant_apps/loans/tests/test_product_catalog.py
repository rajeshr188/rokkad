import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import LoanProductVersionStatus
from apps.tenant_apps.loans.models import LoanProduct, LoanProductVersion
from apps.tenant_apps.loans.forms import PawnDraftForm
from apps.tenant_apps.loans.services import (
    activate_product_version,
    create_product_version_draft,
    retire_product_version,
    seed_default_loan_products,
)


class LoanProductCatalogTests(TenantTestCase):
    test_schema_name = f"loan_products_{uuid.uuid4().hex[:8]}"
    test_domain = f"loan-products-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loan-product-owner",
            defaults={"email": "loan-product-owner@example.com"},
        )
        tenant.name = f"Loan Products {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_seed_creates_four_draft_versions_idempotently(self):
        first = seed_default_loan_products()
        second = seed_default_loan_products()

        self.assertEqual(len(first), 4)
        self.assertEqual(tuple(item.pk for item in first), tuple(item.pk for item in second))
        self.assertEqual(LoanProduct.objects.count(), 4)
        self.assertEqual(LoanProductVersion.objects.count(), 4)
        self.assertEqual(
            set(LoanProductVersion.objects.values_list("status", flat=True)),
            {LoanProductVersionStatus.DRAFT.value},
        )
        self.assertTrue(
            all(item.product.workspace_id == self.tenant.pk for item in first)
        )

    def test_product_version_cannot_be_updated_or_deleted(self):
        version = seed_default_loan_products()[0]
        version.operational_grace_days = 4

        with self.assertRaisesMessage(ValidationError, "immutable"):
            version.save()
        with self.assertRaisesMessage(ValidationError, "immutable"):
            version.delete()

    def test_activation_and_retirement_change_availability_not_contract(self):
        version = seed_default_loan_products()[0]
        activated = activate_product_version(version.pk)
        self.assertEqual(activated.status, LoanProductVersionStatus.ACTIVE.value)
        self.assertEqual(
            LoanProductVersion.objects.filter(
                product=version.product,
                status=LoanProductVersionStatus.ACTIVE.value,
            ).count(),
            1,
        )
        retired = retire_product_version(version.pk)
        self.assertEqual(retired.status, LoanProductVersionStatus.RETIRED.value)
        self.assertFalse(
            LoanProductVersion.objects.filter(
                pk=version.pk, status=LoanProductVersionStatus.ACTIVE.value
            ).exists()
        )

    def test_retired_version_cannot_be_reactivated(self):
        version = seed_default_loan_products()[0]
        activate_product_version(version.pk)
        retire_product_version(version.pk)
        with self.assertRaisesMessage(ValueError, "Only a draft"):
            activate_product_version(version.pk)

    def test_new_terms_create_next_draft_without_changing_active_version(self):
        active = seed_default_loan_products()[0]
        activate_product_version(active.pk)
        draft = create_product_version_draft(
            active.product_id,
            available_from=None,
            available_until=None,
            repayment_structure=active.repayment_structure,
            amortisation_method=active.amortisation_method,
            payment_frequency=active.payment_frequency,
            minimum_tenor_months=active.minimum_tenor_months,
            maximum_tenor_months=6,
            operational_grace_days=active.operational_grace_days,
            extra_payment_rule=active.extra_payment_rule,
            calculation_contract_version="RBI-GOLD-V2",
        )
        active.refresh_from_db()
        self.assertEqual(active.status, LoanProductVersionStatus.ACTIVE.value)
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.status, LoanProductVersionStatus.DRAFT.value)
        self.assertEqual(draft.maximum_tenor_months, 6)

    def test_activated_product_is_available_in_pawn_draft_form(self):
        version = seed_default_loan_products()[0]
        activate_product_version(version.pk)
        form = PawnDraftForm(workspace=self.tenant)
        self.assertIn(version, form.fields["product_version"].queryset)
