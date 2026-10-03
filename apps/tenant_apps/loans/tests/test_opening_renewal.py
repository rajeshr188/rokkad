from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import create_pawn_loan_economic_policy, create_pawn_metal_interest_rate_policy
from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan, renew_pawn_loan, reverse_pawn_loan_renewal, RetainedCollateralInput
from apps.tenant_apps.loans.services.opening_continuation import preview_opening_collection
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from .test_opening_release import OpeningReleaseFixture


class OpeningRenewalTests(OpeningReleaseFixture):
    def setUp(self):
        super().setUp()
        self.product = ensure_test_product_version(self.tenant)
        self.sequence = m.LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN",
            prefix="N-", width=4, next_number=1, maximum_number=9999)
        create_pawn_loan_economic_policy(workspace=self.tenant, license=self.loan.license, effective_from=self.day,
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal("0.8"), advance_interest_periods=1, actor=self.actor)
        create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=self.loan.license, metal="GOLD",
            monthly_interest_rate=Decimal("2"), effective_from=self.day, actor=self.actor)
        from apps.tenant_apps.rates.models import Rate, RateSource
        Rate.objects.create(rate_source=RateSource.objects.create(name="Renewal market", location="Local"), buying_rate=5000, selling_rate=5100)

    def values(self, **changes):
        data = dict(mode="TOP_UP_RENEW", principal_paid=Decimal("0"), top_up_amount=Decimal("200"),
            successor_license_id=self.loan.license_id, successor_series_id=self.loan.series_id,
            successor_product_version_id=self.product.pk, tenure_months=3,
            retained_collateral=(RetainedCollateralInput(self.item.pk, Decimal("1200")),))
        data.update(changes)
        return data

    def renew(self, **changes):
        data = self.values(**changes)
        preview = preview_pawn_loan_renewal_plan(self.loan.pk, **data)
        return renew_pawn_loan(self.loan.pk, **data, renewal_date=self.day, request_key="opening-renewal",
            expected_preview_fingerprint=preview.fingerprint, actor=self.actor), preview

    def test_opening_renewal_settles_remaining_debt_and_preserves_original_cutover(self):
        frozen = self.origin.payload_fingerprint
        result, preview = self.renew()
        self.assertEqual(preview.source.interest_settled, 10)
        self.assertEqual(result.renewal.source_principal_amount, 1000)
        self.assertEqual(result.renewal.interest_settled, 10)
        self.assertEqual(result.renewal.successor_principal_amount, 1200)
        self.assertEqual(result.successor_loan.product_version_id, self.product.pk)
        self.assertEqual(result.successor_loan.policy_snapshot.basis, "ORIGINATION")
        self.assertEqual(result.settlement_event.payload["opening_collection"]["operation"], "RENEWAL_SETTLEMENT")
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).total_due, 0)
        self.assertEqual(preview_opening_collection(self.loan, events=self.loan.loan_events.all(), as_of_date=self.day).additional_interest, 0)
        self.origin.refresh_from_db()
        self.assertEqual(self.origin.payload_fingerprint, frozen)
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "RENEWAL_TRANSFERRED")

    def test_current_opening_renewal_reversal_restores_source_and_catchup_together(self):
        result, _ = self.renew()
        reverse_pawn_loan_renewal(result.renewal.pk, reason="Wrong current renewal", actor=self.actor)
        self.loan.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(self.item.custody_state, "IN_VAULT")
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).principal_outstanding, 1000)
        self.assertEqual(preview_opening_collection(self.loan, events=self.loan.loan_events.all(), as_of_date=self.day).additional_interest, 10)
        self.assertFalse(hasattr(self.origin, "reversed_by_event"))

    def test_opening_renewal_after_receipt_uses_reduced_remaining_principal(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        record_pawn_loan_repayment(self.loan.pk, amount="110", request_key="receipt", actor=self.actor)
        result, _ = self.renew(retained_collateral=(RetainedCollateralInput(self.item.pk, Decimal("1100")),))
        self.assertEqual(result.renewal.source_principal_amount, 900)
        self.assertEqual(result.renewal.interest_settled, 0)
        self.assertEqual(result.successor_loan.principal_amount, 1100)

    def test_opening_renewal_requires_live_successor_approval_and_authorization(self):
        with self.assertRaises(PermissionDenied):
            renew_pawn_loan(self.loan.pk, **self.values(), renewal_date=self.day, request_key="unauthorized", actor=None)
        from apps.tenant_apps.rates.models import Rate
        from apps.tenant_apps.rates.services import withdraw_quote
        for quote in Rate.objects.all():
            withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=quote.pk, reason="Source withdrawn before renewal")
        with self.assertRaises(ValueError):
            self.renew()
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=self.loan).exists())

    def test_known_paper_renewal_preserves_cutover_and_actual_net_cash(self):
        from uuid import uuid4
        from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
        data = dict(date=self.day.isoformat(), number="PAPER-2", rate="2", tenure=3, new_principal="1200",
            advance_months=1, document_charge="10", amount="0", cash_paid="156",
            reference="Book 2 page 4", request_key=str(uuid4()), product_version_id=self.product.pk)
        frozen = self.origin.payload_fingerprint
        review, token = preview_existing_paper_renewal(loan_id=self.loan.pk, actor=self.actor, data=data)
        self.assertEqual(Decimal(review["interest"]), 10)
        self.assertEqual(Decimal(review["cash_paid"]), 156)
        successor, created = record_existing_paper_renewal(loan_id=self.loan.pk, actor=self.actor, data=data,
            review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertEqual(successor.policy_snapshot.basis, "RECORDED_CONTRACT")
        self.assertEqual(successor.origin_renewal.interest_settled, 10)
        self.assertEqual(successor.origin_renewal.catch_up_accrual.recognized_interest, 10)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).total_due, 0)
        self.assertEqual(preview_opening_collection(self.loan, events=self.loan.loan_events.all(), as_of_date=self.day).additional_interest, 0)
        self.origin.refresh_from_db()
        self.assertEqual(self.origin.payload_fingerprint, frozen)
        same, created = record_existing_paper_renewal(loan_id=self.loan.pk, actor=self.actor, data=data,
            review_token=token, confirmed=True)
        self.assertEqual(same.pk, successor.pk)
        self.assertFalse(created)
