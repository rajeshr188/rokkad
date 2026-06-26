import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    Account,
    AccountType,
    AccountType_Ext,
    AccountTransaction,
    AccountingPeriod,
    BusinessEventDraft,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    EntityType,
    ExposureLine,
    JournalEntry,
    Ledger,
    LedgerTransaction,
    PaymentVoucher,
    RateFixing,
    RateFixingAllocation,
    TransactionType_DE,
    Voucher,
    VoucherLine,
)
from apps.tenant_apps.dea.services.business_event_posting import (
    confirm_fixed_purchase_draft,
    confirm_fixed_sale_draft,
    confirm_karigar_movement_draft,
    confirm_monetary_settlement_draft,
    confirm_purchase_rate_fixing_draft,
    confirm_sale_rate_fixing_draft,
    confirm_unfixed_purchase_draft,
    confirm_unfixed_sale_draft,
)
from apps.tenant_apps.dea.services.business_event_preview import (
    build_fixed_purchase_preview,
    build_fixed_sale_preview,
    build_karigar_movement_preview,
    build_monetary_settlement_preview,
    build_purchase_rate_fixing_preview,
    build_sale_rate_fixing_preview,
    build_unfixed_purchase_preview,
    build_unfixed_sale_preview,
    save_fixed_purchase_preview_draft,
    save_fixed_sale_preview_draft,
    save_karigar_movement_preview_draft,
    save_monetary_settlement_preview_draft,
    save_purchase_rate_fixing_preview_draft,
    save_sale_rate_fixing_preview_draft,
    save_unfixed_purchase_preview_draft,
    save_unfixed_sale_preview_draft,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class BusinessEventPostingServiceTests(TenantTestCase):
    test_schema_name = f"dea_event_posting_{uuid.uuid4().hex[:8]}"
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
            username="dea-event-posting-owner",
            defaults={"email": "dea-event-posting-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-event-posting-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-event-posting-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-event-posting-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
        )

    def test_confirm_fixed_purchase_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._preview_draft(deps)

        result = confirm_fixed_purchase_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(result.journal_entry.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.source, draft)
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("100.000"))
        self.assertEqual(result.commodity_movement.valuation_currency, "INR")

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_fixed_purchase_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._preview_draft(deps)

        first = confirm_fixed_purchase_draft(draft.pk, actor=self.user)
        second = confirm_fixed_purchase_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_confirm_fixed_purchase_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "money_amount": "621000.00",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_fixed_purchase_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_confirm_fixed_purchase_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_fixed_purchase_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_confirm_unfixed_purchase_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_preview_draft(deps)

        result = confirm_unfixed_purchase_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(result.commodity_movement.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.source, draft)
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("100.000"))
        self.assertEqual(result.commodity_movement.fixed_status, CommodityMovement.FixedStatus.UNFIXED)
        self.assertEqual(result.exposure.voucher, result.voucher)
        self.assertEqual(result.exposure.source, draft)
        self.assertEqual(result.exposure.open_fine_weight, Decimal("100.000"))
        self.assertEqual(result.exposure.side, ExposureLine.Side.PURCHASE)
        self.assertEqual(result.exposure.valuation_currency, "INR")

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_unfixed_purchase_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_preview_draft(deps)

        first = confirm_unfixed_purchase_draft(draft.pk, actor=self.user)
        second = confirm_unfixed_purchase_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(first.exposure.pk, second.exposure.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)

    def test_confirm_unfixed_purchase_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "fine_weight": "101.000",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_unfixed_purchase_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_confirm_unfixed_purchase_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._unfixed_preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_unfixed_purchase_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_confirm_purchase_rate_fixing_draft_posts_existing_backend_payload(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_purchase_exposure(deps)
        draft = self._purchase_rate_fixing_preview_draft(deps, exposure)

        result = confirm_purchase_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.rate_fixing.status, RateFixing.Status.POSTED)
        self.assertEqual(result.rate_fixing.voucher, result.voucher)
        self.assertEqual(result.journal_entry.voucher, result.voucher)
        self.assertEqual(result.allocation.exposure_id, exposure.pk)
        self.assertEqual(result.allocation.fine_weight, Decimal("50.000"))
        self.assertEqual(result.exposure.open_fine_weight, Decimal("50.000"))
        self.assertEqual(result.exposure.status, ExposureLine.Status.PARTIALLY_FIXED)

        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)

    def test_confirm_purchase_rate_fixing_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_purchase_exposure(deps)
        draft = self._purchase_rate_fixing_preview_draft(deps, exposure)

        first = confirm_purchase_rate_fixing_draft(draft.pk, actor=self.user)
        second = confirm_purchase_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.rate_fixing.pk, second.rate_fixing.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.allocation.pk, second.allocation.pk)
        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)

    def test_confirm_purchase_rate_fixing_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_purchase_exposure(deps)
        draft = self._purchase_rate_fixing_preview_draft(deps, exposure)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "rate": "6300.0000",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_purchase_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        exposure.refresh_from_db()
        self.assertEqual(exposure.open_fine_weight, Decimal("100.000"))

    def test_confirm_sale_rate_fixing_draft_posts_existing_backend_payload(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_sale_exposure(deps)
        draft = self._sale_rate_fixing_preview_draft(deps, exposure)

        result = confirm_sale_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.rate_fixing.status, RateFixing.Status.POSTED)
        self.assertEqual(result.rate_fixing.voucher, result.voucher)
        self.assertEqual(result.journal_entry.voucher, result.voucher)
        self.assertEqual(result.allocation.exposure_id, exposure.pk)
        self.assertEqual(result.allocation.fine_weight, Decimal("50.000"))
        self.assertEqual(result.exposure.open_fine_weight, Decimal("50.000"))
        self.assertEqual(result.exposure.status, ExposureLine.Status.PARTIALLY_FIXED)
        self.assertEqual(result.exposure.side, ExposureLine.Side.SALE)

        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)

    def test_confirm_sale_rate_fixing_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_sale_exposure(deps)
        draft = self._sale_rate_fixing_preview_draft(deps, exposure)

        first = confirm_sale_rate_fixing_draft(draft.pk, actor=self.user)
        second = confirm_sale_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.rate_fixing.pk, second.rate_fixing.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.allocation.pk, second.allocation.pk)
        self.assertEqual(Voucher.objects.count(), 2)
        self.assertEqual(RateFixing.objects.count(), 1)
        self.assertEqual(RateFixingAllocation.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_confirm_sale_rate_fixing_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        exposure = self._posted_unfixed_sale_exposure(deps)
        draft = self._sale_rate_fixing_preview_draft(deps, exposure)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "rate": "7100.0000",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_sale_rate_fixing_draft(draft.pk, actor=self.user)

        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        exposure.refresh_from_db()
        self.assertEqual(exposure.open_fine_weight, Decimal("100.000"))

    def test_confirm_fixed_sale_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._fixed_sale_preview_draft(deps)

        result = confirm_fixed_sale_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(result.journal_entry.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.source, draft)
        self.assertEqual(
            result.commodity_movement.movement_type,
            CommodityMovement.MovementType.SALE_ISSUE,
        )
        self.assertEqual(result.commodity_movement.from_account, deps["vault"])
        self.assertIsNone(result.commodity_movement.to_account)
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("100.000"))
        self.assertEqual(result.commodity_movement.valuation_currency, "INR")

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_fixed_sale_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._fixed_sale_preview_draft(deps)

        first = confirm_fixed_sale_draft(draft.pk, actor=self.user)
        second = confirm_fixed_sale_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)

    def test_confirm_fixed_sale_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._fixed_sale_preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "money_amount": "701000.00",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_fixed_sale_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_confirm_fixed_sale_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._fixed_sale_preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_fixed_sale_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_confirm_unfixed_sale_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_sale_preview_draft(deps)

        result = confirm_unfixed_sale_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(result.commodity_movement.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.source, draft)
        self.assertEqual(
            result.commodity_movement.movement_type,
            CommodityMovement.MovementType.SALE_ISSUE,
        )
        self.assertEqual(result.commodity_movement.from_account, deps["vault"])
        self.assertIsNone(result.commodity_movement.to_account)
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("100.000"))
        self.assertEqual(result.commodity_movement.fixed_status, CommodityMovement.FixedStatus.UNFIXED)
        self.assertEqual(result.exposure.voucher, result.voucher)
        self.assertEqual(result.exposure.source, draft)
        self.assertEqual(result.exposure.open_fine_weight, Decimal("100.000"))
        self.assertEqual(result.exposure.side, ExposureLine.Side.SALE)
        self.assertEqual(result.exposure.valuation_currency, "INR")

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)
        self.assertEqual(RateFixingAllocation.objects.count(), 0)

    def test_confirm_unfixed_sale_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_sale_preview_draft(deps)

        first = confirm_unfixed_sale_draft(draft.pk, actor=self.user)
        second = confirm_unfixed_sale_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(first.exposure.pk, second.exposure.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 1)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_unfixed_sale_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._unfixed_sale_preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "fine_weight": "101.000",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_unfixed_sale_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_confirm_unfixed_sale_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._unfixed_sale_preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_unfixed_sale_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_confirm_customer_receipt_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._customer_receipt_preview_draft(deps)

        result = confirm_monetary_settlement_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.payment_voucher.source_document, draft)
        self.assertTrue(result.payment_voucher.posted)
        self.assertEqual(result.voucher.business_doc, result.payment_voucher)
        self.assertEqual(result.journal_entry.voucher, result.voucher)

        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_supplier_payment_draft_posts_existing_backend_service_payload(self):
        deps = self._seed_dependencies()
        draft = self._supplier_payment_preview_draft(deps)

        result = confirm_monetary_settlement_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.payment_voucher.source_document, draft)
        self.assertTrue(result.payment_voucher.posted)
        self.assertEqual(result.voucher.business_doc, result.payment_voucher)
        self.assertEqual(result.journal_entry.voucher, result.voucher)

        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 2)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(LedgerTransaction.objects.count(), 1)
        self.assertEqual(AccountTransaction.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_monetary_settlement_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._customer_receipt_preview_draft(deps)

        first = confirm_monetary_settlement_draft(draft.pk, actor=self.user)
        second = confirm_monetary_settlement_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.payment_voucher.pk, second.payment_voucher.pk)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.journal_entry.pk, second.journal_entry.pk)
        self.assertEqual(PaymentVoucher.objects.count(), 1)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_monetary_settlement_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._customer_receipt_preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "money_amount": "25001.00",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_monetary_settlement_draft(draft.pk, actor=self.user)

        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)

    def test_confirm_monetary_settlement_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._customer_receipt_preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_monetary_settlement_draft(draft.pk, actor=self.user)

        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_confirm_karigar_issue_draft_posts_commodity_only_payload(self):
        deps = self._seed_dependencies()
        draft = self._karigar_issue_preview_draft(deps)

        result = confirm_karigar_movement_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(result.commodity_movement.voucher, result.voucher)
        self.assertEqual(result.commodity_movement.source, draft)
        self.assertEqual(
            result.commodity_movement.movement_type,
            CommodityMovement.MovementType.KARIGAR_ISSUE,
        )
        self.assertEqual(result.commodity_movement.from_account, deps["vault"])
        self.assertEqual(
            result.commodity_movement.to_account,
            deps["karigar_custody"],
        )
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("25.000"))

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_karigar_receipt_draft_posts_commodity_only_payload(self):
        deps = self._seed_dependencies()
        draft = self._karigar_receipt_preview_draft(deps)

        result = confirm_karigar_movement_draft(draft.pk, actor=self.user)

        self.assertTrue(result.created)
        self.assertEqual(result.voucher.business_doc, draft)
        self.assertEqual(
            result.commodity_movement.movement_type,
            CommodityMovement.MovementType.KARIGAR_RECEIPT,
        )
        self.assertEqual(
            result.commodity_movement.from_account,
            deps["karigar_custody"],
        )
        self.assertEqual(result.commodity_movement.to_account, deps["vault"])
        self.assertEqual(result.commodity_movement.fine_weight, Decimal("20.000"))

        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(VoucherLine.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)
        self.assertEqual(PaymentVoucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(ExposureLine.objects.count(), 0)
        self.assertEqual(RateFixing.objects.count(), 0)

    def test_confirm_karigar_movement_draft_is_idempotent_for_duplicate_submit(self):
        deps = self._seed_dependencies()
        draft = self._karigar_issue_preview_draft(deps)

        first = confirm_karigar_movement_draft(draft.pk, actor=self.user)
        second = confirm_karigar_movement_draft(draft.pk, actor=self.user)

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.voucher.pk, second.voucher.pk)
        self.assertEqual(first.commodity_movement.pk, second.commodity_movement.pk)
        self.assertEqual(Voucher.objects.count(), 1)
        self.assertEqual(CommodityMovement.objects.count(), 1)
        self.assertEqual(JournalEntry.objects.count(), 0)
        self.assertEqual(ExposureLine.objects.count(), 0)

    def test_confirm_karigar_movement_draft_rejects_stale_preview(self):
        deps = self._seed_dependencies()
        draft = self._karigar_issue_preview_draft(deps)
        draft.normalized_payload = {
            **draft.normalized_payload,
            "fine_weight": "26.000",
        }
        draft.save(update_fields=["normalized_payload", "updated_at"])

        with self.assertRaises(ValidationError):
            confirm_karigar_movement_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def test_confirm_karigar_movement_draft_rejects_missing_period(self):
        deps = self._seed_dependencies(create_period=False)
        draft = self._karigar_issue_preview_draft(deps)

        with self.assertRaises(ValidationError):
            confirm_karigar_movement_draft(draft.pk, actor=self.user)

        self.assertEqual(Voucher.objects.count(), 0)
        self.assertEqual(CommodityMovement.objects.count(), 0)
        self.assertEqual(JournalEntry.objects.count(), 0)

    def _seed_dependencies(self, *, create_period=True):
        if create_period:
            AccountingPeriod.objects.create(
                name="June 2026",
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
            )
        debit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        credit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debit_code},
        )
        AccountType_Ext.objects.get_or_create(
            description="Creditor",
            defaults={"XactTypeCode": credit_code},
        )
        EntityType.objects.get_or_create(name="Organisation")
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability", "code_prefix": "2"},
        )
        revenue_type, _ = AccountType.objects.get_or_create(
            AccountType="Revenue",
            defaults={"description": "Revenue", "code_prefix": "4"},
        )
        inventory_ledger = Ledger.objects.create(
            name=f"EVENT_POSTING_INVENTORY_{uuid.uuid4().hex[:6]}",
            AccountType=asset_type,
            code=f"1.EVT.INV.{uuid.uuid4().hex[:6]}",
        )
        payable_ledger = Ledger.objects.create(
            name=f"EVENT_POSTING_AP_{uuid.uuid4().hex[:6]}",
            AccountType=liability_type,
            code=f"2.EVT.AP.{uuid.uuid4().hex[:6]}",
        )
        receivable_ledger = Ledger.objects.create(
            name=f"EVENT_POSTING_AR_{uuid.uuid4().hex[:6]}",
            AccountType=asset_type,
            code=f"1.EVT.AR.{uuid.uuid4().hex[:6]}",
        )
        cash_ledger = Ledger.objects.create(
            name=f"EVENT_POSTING_CASH_{uuid.uuid4().hex[:6]}",
            AccountType=asset_type,
            code=f"1.EVT.CASH.{uuid.uuid4().hex[:6]}",
        )
        revenue_ledger = Ledger.objects.create(
            name=f"EVENT_POSTING_REVENUE_{uuid.uuid4().hex[:6]}",
            AccountType=revenue_type,
            code=f"4.EVT.REV.{uuid.uuid4().hex[:6]}",
        )
        supplier_customer = Customer.objects.create(
            firstname="Event",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        supplier_account = Account.objects.create(
            contact=supplier_customer,
            entity=EntityType.objects.get(name="Organisation"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Creditor"),
        )
        customer = Customer.objects.create(
            firstname="Event",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        customer_account = Account.objects.create(
            contact=customer,
            entity=EntityType.objects.get(name="Organisation"),
            AccountType_Ext=AccountType_Ext.objects.get(description="Debtor"),
        )
        commodity = Commodity.objects.create(code="GOLD", name="Gold")
        party = Party.objects.create(display_name="Event Supplier Party")
        karigar_party = Party.objects.create(display_name="Event Karigar")
        supplier_commodity_account = CommodityAccount.objects.create(
            code=f"EVENT_GOLD_SUPPLIER_{uuid.uuid4().hex[:6]}",
            name="Event gold supplier",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=party,
        )
        vault = CommodityAccount.objects.create(
            code=f"EVENT_GOLD_VAULT_{uuid.uuid4().hex[:6]}",
            name="Event gold vault",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        karigar_custody = CommodityAccount.objects.create(
            code=f"EVENT_GOLD_KARIGAR_{uuid.uuid4().hex[:6]}",
            name="Event gold karigar custody",
            commodity=commodity,
            purpose=CommodityAccount.Purpose.KARIGAR_CUSTODY,
            party=karigar_party,
        )
        return {
            "supplier_account": supplier_account,
            "customer_account": customer_account,
            "inventory_ledger": inventory_ledger,
            "payable_ledger": payable_ledger,
            "receivable_ledger": receivable_ledger,
            "cash_ledger": cash_ledger,
            "revenue_ledger": revenue_ledger,
            "commodity": commodity,
            "party": party,
            "karigar_party": karigar_party,
            "supplier_commodity_account": supplier_commodity_account,
            "vault": vault,
            "karigar_custody": karigar_custody,
        }

    def _preview_draft(self, deps):
        cleaned_data = {
            "source_reference": "SUP-BILL-CONFIRM-001",
            "purchase_date": date(2026, 6, 24),
            "supplier_account": deps["supplier_account"],
            "inventory_ledger": deps["inventory_ledger"],
            "payable_ledger": deps["payable_ledger"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("100.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("100.000"),
            "from_commodity_account": deps["supplier_commodity_account"],
            "to_commodity_account": deps["vault"],
            "money_amount": Decimal("620000.00"),
            "currency": "INR",
            "narration": "Confirm fixed purchase draft",
        }
        preview = build_fixed_purchase_preview(cleaned_data)
        return save_fixed_purchase_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _unfixed_preview_draft(self, deps):
        cleaned_data = {
            "source_reference": "UNFIXED-SUP-BILL-CONFIRM-001",
            "purchase_date": date(2026, 6, 24),
            "party": deps["party"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("100.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("100.000"),
            "from_commodity_account": deps["supplier_commodity_account"],
            "to_commodity_account": deps["vault"],
            "rate_basis": "Fix at next morning market rate",
            "valuation_currency": "INR",
            "last_valuation_rate": Decimal("6200.0000"),
            "narration": "Confirm unfixed purchase draft",
        }
        preview = build_unfixed_purchase_preview(cleaned_data)
        return save_unfixed_purchase_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _posted_unfixed_purchase_exposure(self, deps):
        draft = self._unfixed_preview_draft(deps)
        confirm_unfixed_purchase_draft(draft.pk, actor=self.user)
        return ExposureLine.objects.get()

    def _posted_unfixed_sale_exposure(self, deps):
        draft = self._unfixed_sale_preview_draft(deps)
        confirm_unfixed_sale_draft(draft.pk, actor=self.user)
        return ExposureLine.objects.get()

    def _purchase_rate_fixing_preview_draft(self, deps, exposure):
        cleaned_data = {
            "source_reference": "PRF-CONFIRM-001",
            "exposure": exposure,
            "fixing_date": date(2026, 6, 24),
            "fine_weight": Decimal("50.000"),
            "rate": Decimal("6200.0000"),
            "supplier_account": deps["supplier_account"],
            "inventory_ledger": deps["inventory_ledger"],
            "payable_ledger": deps["payable_ledger"],
            "currency": "INR",
            "narration": "Confirm purchase rate fixing draft",
        }
        preview = build_purchase_rate_fixing_preview(cleaned_data)
        return save_purchase_rate_fixing_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _sale_rate_fixing_preview_draft(self, deps, exposure):
        cleaned_data = {
            "source_reference": "SRF-CONFIRM-001",
            "exposure": exposure,
            "fixing_date": date(2026, 6, 24),
            "fine_weight": Decimal("50.000"),
            "rate": Decimal("7000.0000"),
            "customer_account": deps["customer_account"],
            "receivable_ledger": deps["receivable_ledger"],
            "revenue_ledger": deps["revenue_ledger"],
            "currency": "INR",
            "narration": "Confirm sale rate fixing draft",
        }
        preview = build_sale_rate_fixing_preview(cleaned_data)
        return save_sale_rate_fixing_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _fixed_sale_preview_draft(self, deps):
        cleaned_data = {
            "source_reference": "SALE-BILL-CONFIRM-001",
            "sale_date": date(2026, 6, 24),
            "customer_account": deps["customer_account"],
            "receivable_ledger": deps["receivable_ledger"],
            "revenue_ledger": deps["revenue_ledger"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("100.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("100.000"),
            "from_commodity_account": deps["vault"],
            "money_amount": Decimal("700000.00"),
            "currency": "INR",
            "narration": "Confirm fixed sale draft",
        }
        preview = build_fixed_sale_preview(cleaned_data)
        return save_fixed_sale_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _unfixed_sale_preview_draft(self, deps):
        cleaned_data = {
            "source_reference": "UNFIXED-SALE-BILL-CONFIRM-001",
            "sale_date": date(2026, 6, 24),
            "party": deps["party"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("100.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("100.000"),
            "from_commodity_account": deps["vault"],
            "rate_basis": "Fix at next evening market rate",
            "valuation_currency": "INR",
            "last_valuation_rate": Decimal("7000.0000"),
            "narration": "Confirm unfixed sale draft",
        }
        preview = build_unfixed_sale_preview(cleaned_data)
        return save_unfixed_sale_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _customer_receipt_preview_draft(self, deps):
        cleaned_data = {
            "settlement_type": "CUSTOMER_RECEIPT",
            "source_reference": "SETTLEMENT-RECEIPT-CONFIRM-001",
            "event_date": date(2026, 6, 24),
            "party_account": deps["customer_account"],
            "cash_or_bank_ledger": deps["cash_ledger"],
            "counterparty_ledger": deps["receivable_ledger"],
            "money_amount": Decimal("25000.00"),
            "reference_number": "BANK-RECEIPT-CONFIRM-001",
            "currency": "INR",
            "payment_method": "CASH",
            "narration": "Confirm customer receipt draft",
        }
        preview = build_monetary_settlement_preview(cleaned_data)
        return save_monetary_settlement_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _supplier_payment_preview_draft(self, deps):
        cleaned_data = {
            "settlement_type": "SUPPLIER_PAYMENT",
            "source_reference": "SETTLEMENT-PAYMENT-CONFIRM-001",
            "event_date": date(2026, 6, 24),
            "party_account": deps["supplier_account"],
            "cash_or_bank_ledger": deps["cash_ledger"],
            "counterparty_ledger": deps["payable_ledger"],
            "money_amount": Decimal("18000.00"),
            "reference_number": "BANK-PAYMENT-CONFIRM-001",
            "currency": "INR",
            "payment_method": "CASH",
            "narration": "Confirm supplier payment draft",
        }
        preview = build_monetary_settlement_preview(cleaned_data)
        return save_monetary_settlement_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _karigar_issue_preview_draft(self, deps):
        cleaned_data = {
            "movement_type": "KARIGAR_ISSUE",
            "source_reference": "KARIGAR-ISSUE-CONFIRM-001",
            "event_date": date(2026, 6, 24),
            "karigar": deps["karigar_party"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("25.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("25.000"),
            "from_commodity_account": deps["vault"],
            "to_commodity_account": deps["karigar_custody"],
            "narration": "Confirm karigar issue draft",
        }
        preview = build_karigar_movement_preview(cleaned_data)
        return save_karigar_movement_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )

    def _karigar_receipt_preview_draft(self, deps):
        cleaned_data = {
            "movement_type": "KARIGAR_RECEIPT",
            "source_reference": "KARIGAR-RECEIPT-CONFIRM-001",
            "event_date": date(2026, 6, 24),
            "karigar": deps["karigar_party"],
            "commodity": deps["commodity"],
            "gross_weight": Decimal("20.000"),
            "purity": Decimal("1.000000"),
            "fine_weight": Decimal("20.000"),
            "from_commodity_account": deps["karigar_custody"],
            "to_commodity_account": deps["vault"],
            "narration": "Confirm karigar receipt draft",
        }
        preview = build_karigar_movement_preview(cleaned_data)
        return save_karigar_movement_preview_draft(
            cleaned_data,
            preview,
            actor=self.user,
        )
