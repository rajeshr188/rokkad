from apps.tenancy.testing import workspace_role_permissions
import uuid

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.loans.domain import LoanProductVersionStatus
from apps.tenant_apps.loans.models import LoanProduct, LoanProductVersion
from apps.tenant_apps.loans.forms import PawnDraftForm
from apps.tenant_apps.loans.services import (
    activate_product_version,
    create_product_version_draft,
    retire_product_version,
    seed_default_loan_products,
)


class LoanProductCatalogTests(WorkspaceTestCase):
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
        self.actor = self.tenant.owner
        role, _ = Role.objects.get_or_create(name="Admin")
        Membership.objects.get_or_create(user=self.actor, company=self.tenant, defaults={"role": role})

    def test_seed_creates_four_draft_versions_idempotently(self):
        first = seed_default_loan_products(actor=self.actor)
        second = seed_default_loan_products(actor=self.actor)

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
        version = seed_default_loan_products(actor=self.actor)[0]
        version.operational_grace_days = 4

        with self.assertRaisesMessage(ValidationError, "immutable"):
            version.save()
        with self.assertRaisesMessage(ValidationError, "immutable"):
            version.delete()

    def test_activation_and_retirement_change_availability_not_contract(self):
        version = seed_default_loan_products(actor=self.actor)[0]
        activated = activate_product_version(version.pk, actor=self.actor)
        self.assertEqual(activated.status, LoanProductVersionStatus.ACTIVE.value)
        self.assertEqual(
            LoanProductVersion.objects.filter(
                product=version.product,
                status=LoanProductVersionStatus.ACTIVE.value,
            ).count(),
            1,
        )
        retired = retire_product_version(version.pk, actor=self.actor)
        self.assertEqual(retired.status, LoanProductVersionStatus.RETIRED.value)
        self.assertFalse(
            LoanProductVersion.objects.filter(
                pk=version.pk, status=LoanProductVersionStatus.ACTIVE.value
            ).exists()
        )

    def test_retired_version_cannot_be_reactivated(self):
        version = seed_default_loan_products(actor=self.actor)[0]
        activate_product_version(version.pk, actor=self.actor)
        retire_product_version(version.pk, actor=self.actor)
        with self.assertRaisesMessage(ValueError, "Only a draft"):
            activate_product_version(version.pk, actor=self.actor)

    def test_new_terms_create_next_draft_without_changing_active_version(self):
        active = seed_default_loan_products(actor=self.actor)[0]
        activate_product_version(active.pk, actor=self.actor)
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
            actor=self.actor,
        )
        active.refresh_from_db()
        self.assertEqual(active.status, LoanProductVersionStatus.ACTIVE.value)
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.status, LoanProductVersionStatus.DRAFT.value)
        self.assertEqual(draft.maximum_tenor_months, 6)

    def test_activated_product_is_available_in_pawn_draft_form(self):
        version = seed_default_loan_products(actor=self.actor)[0]
        activate_product_version(version.pk, actor=self.actor)
        form = PawnDraftForm(workspace=self.tenant)
        self.assertIn(version, form.fields["product_version"].queryset)

    def test_setup_families_reject_missing_unprivileged_and_removed_actors(self):
        from functools import partial
        from datetime import date
        from django.core.exceptions import PermissionDenied
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from apps.tenant_apps.loans.services.license_series import create_license
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        from apps.tenant_apps.loans.services.print_profiles import LoanDocumentPrintProfileService
        from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
        from apps.tenant_apps.loans.services.communication_policy import set_pawn_loan_communication_policy

        version = seed_default_loan_products(actor=self.actor)[0]
        commands = (
            seed_default_loan_products,
            partial(activate_product_version, version.pk),
            partial(retire_product_version, version.pk),
            partial(create_product_version_draft, version.product_id),
            partial(create_license, workspace=self.tenant, name="Denied", license_number="DENIED",
                    issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1)),
            partial(create_pawn_economic_configuration, workspace=self.tenant,
                    gold_monthly_interest_rate=2, silver_monthly_interest_rate=4),
            partial(LoanDocumentLayoutService.create_layout, workspace=self.tenant,
                    document_type="PAWN_TICKET", name="Denied", definition={}),
            partial(LoanDocumentPrintProfileService.create_profile, workspace=self.tenant,
                    document_type="PAWN_TICKET", name="Denied", definition={}),
            partial(create_loan_monitoring_policy, workspace=self.tenant),
            set_pawn_loan_communication_policy,
        )
        for role_name in ("Member", "Viewer", None):
            membership = Membership.objects.filter(user=self.actor, company=self.tenant)
            if role_name:
                role, _ = Role.objects.get_or_create(name=role_name)
                membership.update(role=role)
            else:
                membership.delete()
            for actor in (None, self.actor):
                for command in commands:
                    with self.subTest(role=role_name, actor=actor, command=command):
                        with CaptureQueriesContext(connection) as queries:
                            with self.assertRaises(PermissionDenied):
                                command(actor=actor)
                        writes = [q["sql"] for q in queries if q["sql"].lstrip().upper().startswith(
                            ("INSERT ", "UPDATE ", "DELETE "))]
                        self.assertEqual(writes, [])

    def test_settings_only_delegate_and_revoked_seed_replay(self):
        from io import StringIO
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.core.exceptions import PermissionDenied
        from django.core.management import call_command
        from apps.orgs.models import Company

        role = Role.objects.create(name="SetupDelegate-" + uuid.uuid4().hex[:8])
        permission, _ = Permission.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(Company), codename="workspace_settings",
            defaults={"name": "Manage workspace settings"})
        workspace_role_permissions(role, self.tenant).add(permission)
        Membership.objects.filter(user=self.actor, company=self.tenant).update(role=role)
        version = seed_default_loan_products(actor=self.actor)[0]
        activate_product_version(version.pk, actor=self.actor)
        workspace_role_permissions(role, self.tenant).clear()
        with self.assertRaises(PermissionDenied):
            seed_default_loan_products(actor=self.actor)
        with self.assertRaises(PermissionDenied):
            activate_product_version(version.pk, actor=self.actor)
        # Operator bootstrap is an explicit command, not an actor=None bypass.
        call_command("seed_default_loan_products", stdout=StringIO())
        self.assertEqual(LoanProduct.objects.count(), 4)
