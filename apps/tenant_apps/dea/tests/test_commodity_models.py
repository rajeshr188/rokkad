import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountType,
    Commodity,
    CommodityAccount,
    CommodityMovement,
    ExposureLine,
    Ledger,
    LedgerTransaction,
    RateFixing,
    RateFixingAllocation,
)
from apps.tenant_apps.party.models import Party


User = get_user_model()


class CommodityModelTests(TenantTestCase):
    test_schema_name = f"dea_commodity_models_{uuid.uuid4().hex[:8]}"
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
            username="dea-commodity-owner",
            defaults={"email": "dea-commodity-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-commodity-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

    def test_commodity_code_is_normalized_and_defaults_to_metal_grams(self):
        commodity = Commodity.objects.create(code="gold", name="Gold")

        self.assertEqual(commodity.code, "GOLD")
        self.assertEqual(commodity.commodity_type, Commodity.CommodityType.METAL)
        self.assertEqual(commodity.default_uom, Commodity.UnitOfMeasure.GRAM)
        self.assertTrue(commodity.is_active)

    def test_commodity_rejects_monetary_currency_code(self):
        with self.assertRaises(ValidationError):
            Commodity.objects.create(code="INR", name="Indian Rupee")

    def test_commodity_rejects_invalid_code_shape(self):
        with self.assertRaises(ValidationError):
            Commodity.objects.create(code="gold metal", name="Gold")

    def test_commodity_code_is_unique(self):
        Commodity.objects.create(code="GOLD", name="Gold")

        with self.assertRaises(ValidationError):
            Commodity.objects.create(code="gold", name="Duplicate gold")

    def test_owned_stock_commodity_account_can_be_created_without_party(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")

        account = CommodityAccount.objects.create(
            code="gold_main_vault",
            name="Gold main vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.OWNED_STOCK,
            location_label="Main vault",
        )

        self.assertEqual(account.code, "GOLD_MAIN_VAULT")
        self.assertIsNone(account.party)
        self.assertEqual(account.location_label, "Main vault")

    def test_party_obligation_commodity_account_requires_party(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")

        with self.assertRaises(ValidationError):
            CommodityAccount.objects.create(
                code="GOLD_PARTY_RECEIVABLE",
                name="Gold party receivable",
                commodity=gold,
                purpose=CommodityAccount.Purpose.PARTY_RECEIVABLE,
            )

    def test_party_obligation_commodity_account_accepts_party(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier")

        account = CommodityAccount.objects.create(
            code="GOLD_SUPPLIER_PAYABLE",
            name="Gold supplier payable",
            commodity=gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=party,
        )

        self.assertEqual(account.party, party)
        self.assertEqual(account.purpose, CommodityAccount.Purpose.PARTY_PAYABLE)

    def test_commodity_account_code_is_unique(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")
        CommodityAccount.objects.create(
            code="GOLD_MAIN_VAULT",
            name="Gold main vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )

        with self.assertRaises(ValidationError):
            CommodityAccount.objects.create(
                code="gold_main_vault",
                name="Duplicate vault",
                commodity=gold,
                purpose=CommodityAccount.Purpose.VAULT,
            )

    def test_financial_control_ledger_is_reconciliation_only(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")
        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        control_ledger = Ledger.objects.create(
            AccountType=asset_type,
            name="Metal Inventory Control",
            code="1.METAL.CONTROL",
        )

        account = CommodityAccount.objects.create(
            code="GOLD_CONTROLLED_VAULT",
            name="Gold controlled vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.VAULT,
            financial_control_ledger=control_ledger,
        )

        self.assertEqual(account.financial_control_ledger, control_ledger)
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_commodity_movement_can_be_created_without_financial_rows(self):
        gold, vault, supplier = self._commodity_movement_accounts()

        movement = CommodityMovement.objects.create(
            movement_no="cm-001",
            movement_date=date(2026, 6, 24),
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=gold.pk,
            commodity=gold,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=Decimal("91.600"),
            from_account=supplier,
            to_account=vault,
            movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
            fixed_status=CommodityMovement.FixedStatus.FIXED,
            rate=Decimal("6200.0000"),
            rate_currency="INR",
            valuation_currency="INR",
            valuation_amount=Decimal("567920.00"),
            idempotency_key="commodity:test:movement:001",
        )

        self.assertEqual(movement.movement_no, "CM-001")
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def test_commodity_movement_rejects_invalid_fine_weight(self):
        gold, vault, supplier = self._commodity_movement_accounts()

        with self.assertRaises(ValidationError):
            self._create_commodity_movement(
                gold=gold,
                from_account=supplier,
                to_account=vault,
                fine_weight=Decimal("90.000"),
            )

    def test_commodity_movement_rejects_mismatched_account_commodity(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        silver = Commodity.objects.create(code="SILVER", name="Silver")
        silver_vault = CommodityAccount.objects.create(
            code="SILVER_MAIN_VAULT",
            name="Silver main vault",
            commodity=silver,
            purpose=CommodityAccount.Purpose.VAULT,
        )

        with self.assertRaises(ValidationError):
            self._create_commodity_movement(
                gold=gold,
                from_account=supplier,
                to_account=silver_vault,
            )

    def test_commodity_movement_requires_at_least_one_account_side(self):
        gold = Commodity.objects.create(code="GOLD", name="Gold")

        with self.assertRaises(ValidationError):
            self._create_commodity_movement(
                gold=gold,
                from_account=None,
                to_account=None,
            )

    def test_commodity_movement_rejects_non_monetary_rate_currency(self):
        gold, vault, supplier = self._commodity_movement_accounts()

        with self.assertRaises(ValidationError):
            self._create_commodity_movement(
                gold=gold,
                from_account=supplier,
                to_account=vault,
                rate_currency="GLD",
            )

    def test_commodity_movement_idempotency_key_is_unique(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        self._create_commodity_movement(
            gold=gold,
            from_account=supplier,
            to_account=vault,
            idempotency_key="commodity:test:duplicate",
        )

        with self.assertRaises(ValidationError):
            self._create_commodity_movement(
                gold=gold,
                movement_no="cm-duplicate",
                from_account=supplier,
                to_account=vault,
                idempotency_key="commodity:test:duplicate",
            )

    def test_commodity_movement_is_immutable_after_creation(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        movement = self._create_commodity_movement(
            gold=gold,
            from_account=supplier,
            to_account=vault,
        )

        movement.narration = "Attempted mutation"

        with self.assertRaises(ValidationError):
            movement.save()

    def test_commodity_movement_cannot_be_deleted(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        movement = self._create_commodity_movement(
            gold=gold,
            from_account=supplier,
            to_account=vault,
        )

        with self.assertRaises(ValidationError):
            movement.delete()

    def test_reversal_movement_must_invert_original(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        original = self._create_commodity_movement(
            gold=gold,
            from_account=supplier,
            to_account=vault,
        )

        reversal = CommodityMovement.objects.create(
            movement_no="cm-rev-001",
            movement_date=date(2026, 6, 25),
            source_content_type=ContentType.objects.get_for_model(CommodityMovement),
            source_object_id=original.pk,
            commodity=gold,
            gross_weight=original.gross_weight,
            purity=original.purity,
            fine_weight=original.fine_weight,
            from_account=vault,
            to_account=supplier,
            movement_type=CommodityMovement.MovementType.REVERSAL,
            fixed_status=original.fixed_status,
            is_reversal_of=original,
            idempotency_key="commodity:test:movement:reversal",
        )

        self.assertEqual(reversal.from_account, original.to_account)
        self.assertEqual(reversal.to_account, original.from_account)

    def test_reversal_movement_rejects_non_inverted_accounts(self):
        gold, vault, supplier = self._commodity_movement_accounts()
        original = self._create_commodity_movement(
            gold=gold,
            from_account=supplier,
            to_account=vault,
        )

        with self.assertRaises(ValidationError):
            CommodityMovement.objects.create(
                movement_no="cm-rev-bad",
                movement_date=date(2026, 6, 25),
                source_content_type=ContentType.objects.get_for_model(
                    CommodityMovement
                ),
                source_object_id=original.pk,
                commodity=gold,
                gross_weight=original.gross_weight,
                purity=original.purity,
                fine_weight=original.fine_weight,
                from_account=supplier,
                to_account=vault,
                movement_type=CommodityMovement.MovementType.REVERSAL,
                fixed_status=original.fixed_status,
                is_reversal_of=original,
                idempotency_key="commodity:test:movement:bad-reversal",
            )

    def test_exposure_line_can_track_unfixed_purchase_exposure(self):
        gold = Commodity.objects.create(code="GOLD_EXPOSURE", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Exposure")

        exposure = self._create_exposure(
            commodity=gold,
            party=party,
            side=ExposureLine.Side.PURCHASE,
            fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        )

        self.assertEqual(exposure.exposure_no, "EXP-001")
        self.assertEqual(exposure.open_fine_weight, Decimal("91.600"))
        self.assertEqual(exposure.valuation_currency, "INR")

    def test_exposure_line_rejects_open_weight_above_original(self):
        gold = Commodity.objects.create(code="GOLD_EXP_LIM", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Exposure Limit")

        with self.assertRaises(ValidationError):
            self._create_exposure(
                commodity=gold,
                party=party,
                original_fine_weight=Decimal("91.600"),
                open_fine_weight=Decimal("92.000"),
            )

    def test_exposure_line_fixed_status_requires_zero_open_weight(self):
        gold = Commodity.objects.create(code="GOLD_EXP_FIX", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Fixed Exposure")

        with self.assertRaises(ValidationError):
            self._create_exposure(
                commodity=gold,
                party=party,
                status=ExposureLine.Status.FIXED,
                open_fine_weight=Decimal("1.000"),
            )

    def test_exposure_line_rejects_non_monetary_valuation_currency(self):
        gold = Commodity.objects.create(code="GOLD_EXP_CUR", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Bad Currency")

        with self.assertRaises(ValidationError):
            self._create_exposure(
                commodity=gold,
                party=party,
                valuation_currency="GLD",
            )

    def test_exposure_line_idempotency_key_is_unique(self):
        gold = Commodity.objects.create(code="GOLD_EXP_DUP", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Duplicate")
        self._create_exposure(
            commodity=gold,
            party=party,
            idempotency_key="commodity:test:exposure:duplicate",
        )

        with self.assertRaises(ValidationError):
            self._create_exposure(
                commodity=gold,
                party=party,
                exposure_no="exp-duplicate",
                idempotency_key="commodity:test:exposure:duplicate",
            )

    def test_rate_fixing_can_be_created_for_open_exposure(self):
        gold = Commodity.objects.create(code="GOLD_FIXING", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Fixing")
        exposure = self._create_exposure(commodity=gold, party=party)
        fixing = self._create_rate_fixing(commodity=gold, party=party)

        allocation = RateFixingAllocation.objects.create(
            rate_fixing=fixing,
            exposure=exposure,
            fine_weight=Decimal("50.000"),
            amount=Decimal("310000.00"),
        )

        self.assertEqual(allocation.rate_fixing, fixing)
        self.assertEqual(allocation.exposure, exposure)

    def test_rate_fixing_rejects_non_monetary_currency(self):
        gold = Commodity.objects.create(code="GOLD_FIXING_CURR", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Fixing Currency")

        with self.assertRaises(ValidationError):
            self._create_rate_fixing(
                commodity=gold,
                party=party,
                currency="XAU",
            )

    def test_posted_rate_fixing_requires_idempotency_key(self):
        gold = Commodity.objects.create(code="GOLD_FIX_POST", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Posted Fixing")

        with self.assertRaises(ValidationError):
            self._create_rate_fixing(
                commodity=gold,
                party=party,
                status=RateFixing.Status.POSTED,
                idempotency_key="",
            )

    def test_posted_rate_fixing_is_immutable(self):
        gold = Commodity.objects.create(code="GOLD_FIX_IMM", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Immutable Fixing")
        fixing = self._create_rate_fixing(
            commodity=gold,
            party=party,
            status=RateFixing.Status.POSTED,
            idempotency_key="commodity:test:fixing:posted",
        )

        fixing.narration = "Attempted mutation"

        with self.assertRaises(ValidationError):
            fixing.save()

    def test_rate_fixing_allocation_rejects_mismatched_party(self):
        gold = Commodity.objects.create(code="GOLD_FIX_PARTY", name="Gold")
        exposure_party = Party.objects.create(display_name="Exposure Party")
        fixing_party = Party.objects.create(display_name="Fixing Party")
        exposure = self._create_exposure(commodity=gold, party=exposure_party)
        fixing = self._create_rate_fixing(commodity=gold, party=fixing_party)

        with self.assertRaises(ValidationError):
            RateFixingAllocation.objects.create(
                rate_fixing=fixing,
                exposure=exposure,
                fine_weight=Decimal("50.000"),
                amount=Decimal("310000.00"),
            )

    def test_rate_fixing_allocation_rejects_weight_above_open_exposure(self):
        gold = Commodity.objects.create(code="GOLD_FIX_WT", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Fixing Weight")
        exposure = self._create_exposure(commodity=gold, party=party)
        fixing = self._create_rate_fixing(commodity=gold, party=party)

        with self.assertRaises(ValidationError):
            RateFixingAllocation.objects.create(
                rate_fixing=fixing,
                exposure=exposure,
                fine_weight=Decimal("92.000"),
                amount=Decimal("570400.00"),
            )

    def test_rate_fixing_allocation_rejects_closed_exposure(self):
        gold = Commodity.objects.create(code="GOLD_FIX_CLOSED", name="Gold")
        party = Party.objects.create(display_name="Bullion Supplier Closed Exposure")
        exposure = self._create_exposure(
            commodity=gold,
            party=party,
            status=ExposureLine.Status.CLOSED,
            open_fine_weight=Decimal("0.000"),
        )
        fixing = self._create_rate_fixing(commodity=gold, party=party)

        with self.assertRaises(ValidationError):
            RateFixingAllocation.objects.create(
                rate_fixing=fixing,
                exposure=exposure,
                fine_weight=Decimal("1.000"),
                amount=Decimal("6200.00"),
            )

    def _commodity_movement_accounts(self):
        gold = Commodity.objects.create(code=f"GOLD_{uuid.uuid4().hex[:8]}", name="Gold")
        party = Party.objects.create(display_name=f"Supplier {uuid.uuid4().hex[:8]}")
        vault = CommodityAccount.objects.create(
            code=f"GOLD_MAIN_VAULT_{uuid.uuid4().hex[:8]}",
            name="Gold main vault",
            commodity=gold,
            purpose=CommodityAccount.Purpose.VAULT,
        )
        supplier = CommodityAccount.objects.create(
            code=f"GOLD_SUPPLIER_PAYABLE_{uuid.uuid4().hex[:8]}",
            name="Gold supplier payable",
            commodity=gold,
            purpose=CommodityAccount.Purpose.PARTY_PAYABLE,
            party=party,
        )
        return gold, vault, supplier

    def _create_commodity_movement(
        self,
        *,
        gold,
        from_account,
        to_account,
        movement_no=None,
        fine_weight=Decimal("91.600"),
        rate_currency="INR",
        idempotency_key=None,
    ):
        unique = uuid.uuid4().hex[:8]
        return CommodityMovement.objects.create(
            movement_no=movement_no or f"cm-{unique}",
            movement_date=date(2026, 6, 24),
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=gold.pk,
            commodity=gold,
            gross_weight=Decimal("100.000"),
            purity=Decimal("0.916000"),
            fine_weight=fine_weight,
            from_account=from_account,
            to_account=to_account,
            movement_type=CommodityMovement.MovementType.PURCHASE_RECEIPT,
            fixed_status=CommodityMovement.FixedStatus.FIXED,
            rate=Decimal("6200.0000"),
            rate_currency=rate_currency,
            valuation_currency="INR",
            valuation_amount=Decimal("567920.00"),
            idempotency_key=idempotency_key or f"commodity:test:movement:{unique}",
        )

    def _create_exposure(
        self,
        *,
        commodity,
        party,
        exposure_no="exp-001",
        side=ExposureLine.Side.PURCHASE,
        status=ExposureLine.Status.OPEN,
        fixed_status=CommodityMovement.FixedStatus.UNFIXED,
        original_fine_weight=Decimal("91.600"),
        open_fine_weight=Decimal("91.600"),
        valuation_currency="INR",
        idempotency_key=None,
    ):
        unique = uuid.uuid4().hex[:8]
        return ExposureLine.objects.create(
            exposure_no=exposure_no,
            source_content_type=ContentType.objects.get_for_model(Commodity),
            source_object_id=commodity.pk,
            party=party,
            commodity=commodity,
            side=side,
            status=status,
            fixed_status=fixed_status,
            original_fine_weight=original_fine_weight,
            open_fine_weight=open_fine_weight,
            valuation_currency=valuation_currency,
            rate_basis="Manual contract",
            idempotency_key=idempotency_key or f"commodity:test:exposure:{unique}",
        )

    def _create_rate_fixing(
        self,
        *,
        commodity,
        party,
        fixing_no="fix-001",
        side=ExposureLine.Side.PURCHASE,
        status=RateFixing.Status.DRAFT,
        currency="INR",
        idempotency_key="",
    ):
        return RateFixing.objects.create(
            fixing_no=fixing_no,
            fixing_date=date(2026, 6, 25),
            party=party,
            commodity=commodity,
            side=side,
            fine_weight=Decimal("50.000"),
            rate=Decimal("6200.0000"),
            currency=currency,
            valuation_amount=Decimal("310000.00"),
            status=status,
            idempotency_key=idempotency_key,
        )
