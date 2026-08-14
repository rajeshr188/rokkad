from datetime import date
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import AccountingPeriod, Voucher, VoucherStatus, VoucherType
from apps.tenant_apps.dea.posting.context import PostingContext
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.posting.registry import registry
from apps.tenant_apps.dea.posting.required_rules import REQUIRED_SEEDED_VOUCHER_TYPE_RULES
from apps.tenant_apps.dea.posting.types import PostingError
from apps.tenant_apps.dea.services.post_doc import _resolve_voucher_type


User = get_user_model()


class PostingRuleRegistrationTests(TenantTestCase):
    test_schema_name = f"test_dea_rule_registration_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-rule-owner",
            defaults={"email": "dea-rule-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-rule-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def test_seeded_voucher_types_have_registered_rules(self):
        missing = sorted(
            rule_key
            for rule_key in REQUIRED_SEEDED_VOUCHER_TYPE_RULES
            if rule_key not in registry._rules
        )

        self.assertEqual(missing, [])

    def test_missing_known_seeded_voucher_type_is_restored_on_resolve(self):
        connection.set_tenant(self.tenant)
        VoucherType.objects.filter(name="GIVENLOAN_PAYMENT").delete()

        voucher_type = _resolve_voucher_type("GIVENLOAN_PAYMENT")

        self.assertEqual(voucher_type.name, "GIVENLOAN_PAYMENT")
        self.assertTrue(VoucherType.objects.filter(name="GIVENLOAN_PAYMENT").exists())

    def test_unknown_voucher_type_still_fails(self):
        connection.set_tenant(self.tenant)

        with self.assertRaisesRegex(ValueError, "UNKNOWN_TYPE"):
            _resolve_voucher_type("UNKNOWN_TYPE")


class PostingEnginePeriodLockTests(TenantTestCase):
    test_schema_name = f"test_dea_period_guard_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-period-owner",
            defaults={"email": "dea-period-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-period-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-period-user",
            email="dea-period-user@example.com",
            password="testpass123",
        )

    def test_engine_rejects_posting_into_closed_period_before_rule_lookup(self):
        period = AccountingPeriod.objects.create(
            name="Closed Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            status=AccountingPeriod.PeriodStatus.CLOSED,
        )
        voucher_type = VoucherType.objects.create(
            name="NO_REGISTERED_RULE",
            description="Period guard test",
        )
        voucher = Voucher.objects.create(
            voucher_no="PERIOD-GUARD-001",
            voucher_type=voucher_type,
            voucher_date=period.end_date,
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(AccountingPeriod),
            doc_object_id=period.pk,
        )

        with self.assertRaisesRegex(PostingError, "accounting period .* is CLOSED"):
            DjangoPostingEngine().post(
                PostingContext(voucher=voucher, doc=period, user_id=self.user.id)
            )
