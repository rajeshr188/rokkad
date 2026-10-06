"""Real admission and terminal commands share debt, not fabricated provenance."""
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.services import pawn_auctions as auctions
from apps.tenant_apps.loans.services.collateral_media import append_collateral_photo
from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
from apps.tenant_apps.loans.services.economic_policies import create_pawn_loan_economic_policy
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_renewals import (
    RetainedCollateralInput, preview_pawn_loan_renewal_source, preview_pawn_loan_renewal_plan,
    renew_pawn_loan, reverse_pawn_loan_renewal,
)
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.services.settlement_preparation import prepare_loan_settlement
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.rates.models import Rate
from .factories import prepare_test_auction_service
from .test_continuation_admissions import AdmissionFixture
from .test_recorded_auctions import on


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SettlementContinuationTests(AdmissionFixture):
    def review(self, loan, day):
        facts = dict(through_date=day, confirmed_complete=True, source_reference="Synthetic complete book check",
            request_key=uuid4().hex)
        _, token = preview_transaction_review(loan.pk, actor=self.actor, **facts)
        confirm_transaction_review(loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)

    def test_preparation_preserves_cutover_and_restricted_workspace_boundaries(self):
        day = date(2026, 6, 6)
        with self.scoped(), on(day):
            before = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
            for operation in ("FULL_RELEASE", "RENEWAL", "AUCTION"):
                with self.assertRaisesMessage(ValueError, "strictly after cutover"):
                    prepare_loan_settlement(self.opening, operation=operation, effective_date=self.cutover)
            self.assertEqual(before, list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")))
        with self.scoped(self.b), on(day):
            self.assertFalse(m.PawnLoan.objects.filter(pk__in=[loan.pk for loan in self.loans]).exists())
            for loan in self.loans:
                with self.assertRaises(ValueError):
                    prepare_loan_settlement(loan, operation="FULL_RELEASE", effective_date=day)
                with self.assertRaises(ValueError):
                    release_pawn_loan_in_full(loan.pk, settlement_amount=1, request_key="foreign", actor=self.actor)
                with self.assertRaises(ValueError):
                    renew_pawn_loan(loan.pk, mode="TOP_UP_RENEW", renewal_date=day,
                        principal_paid=0, top_up_amount=1, successor_license_id=loan.license_id,
                        successor_series_id=loan.series_id, monthly_interest_rate=2, tenure_months=12,
                        request_key="foreign", actor=self.actor)

    def test_boundary_quotes_and_all_action_preparation_are_equal_and_read_only(self):
        with self.scoped():
            for day, months in ((date(2026, 5, 5), 0), (date(2026, 5, 6), 1), (date(2026, 6, 6), 2)):
                with on(day):
                    for loan in self.loans:
                        self.review(loan, day)
                    events = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
                    rows = list(m.PawnLoanInterestAccrual.objects.values_list("pk", flat=True))
                    for loan in self.loans:
                        with self.subTest(day=day, loan=loan.loan_number):
                            expected = self.remaining + self.monthly * months
                            self.assertEqual(preview_pawn_loan_full_release(loan.pk).minimum_settlement, expected)
                            source = preview_pawn_loan_renewal_source(loan.pk)
                            self.assertEqual(source.interest_settled, self.monthly * months)
                            for operation in ("FULL_RELEASE", "RENEWAL", "AUCTION"):
                                prepared = prepare_loan_settlement(loan, operation=operation, effective_date=day)
                                paired = prepared.catch_up_accrual.recognized_interest if prepared.catch_up_accrual else 0
                                self.assertEqual(prepared.balance_before_catch_up.total_due + paired, expected)
                    self.assertEqual(events, list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")))
                    self.assertEqual(rows, list(m.PawnLoanInterestAccrual.objects.values_list("pk", flat=True)))

    def test_full_release_recognizes_once_mismatch_rolls_back_and_coupled_reversal_restores_debt(self):
        day = date(2026, 6, 6)
        with self.scoped(), on(day):
            m.LoanNumberSequence.objects.create(series=self.direct.series, document_kind="PAWN_LOAN_RELEASE",
                prefix="LC03-R-", width=5, maximum_number=10000)
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    frozen = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                    before_rows = loan.interest_accruals.count()
                    amount = preview_pawn_loan_full_release(loan.pk).minimum_settlement
                    command = dict(settlement_amount=amount, request_key="settle-" + str(loan.pk), actor=self.actor)
                    with self.assertRaises(ValueError):
                        release_pawn_loan_in_full(loan.pk, **dict(command, settlement_amount=amount-1))
                    self.assertEqual(frozen, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
                    self.assertEqual(before_rows, loan.interest_accruals.count())
                    result = release_pawn_loan_in_full(loan.pk, **command)
                    self.assertEqual(result.release.interest_amount, self.monthly*2)
                    self.assertEqual(get_pawn_loan_balance(loan, as_of_date=day).total_due, 0)
                    self.assertEqual(set(loan.collateral_items.values_list("custody_state", flat=True)), {"WITH_CUSTOMER"})
                    count = loan.loan_events.count()
                    self.assertTrue(release_pawn_loan_in_full(loan.pk, **command).already_released)
                    self.assertEqual(loan.loan_events.count(), count)
                    with self.assertRaises(PermissionDenied):
                        release_pawn_loan_in_full(loan.pk, **dict(command, actor=None))
                    if loan.pk in (self.paper.pk, self.imported.pk):
                        # Cumulative recorded history requires its existing review,
                        # not a standalone reversal that could corrupt dependent receipts.
                        with self.assertRaisesMessage(ValueError, "Review paper history correction"):
                            reverse_pawn_loan_event(result.loan_event.pk, reason="Synthetic reversal", actor=self.actor)
                        self.assertEqual(get_pawn_loan_balance(loan, as_of_date=day).total_due, 0)
                        continue
                    reverse_pawn_loan_event(result.loan_event.pk, reason="Synthetic reversal", actor=self.actor)
                    loan.refresh_from_db()
                    self.assertEqual(loan.state, "ACTIVE")
                    self.assertEqual(set(loan.collateral_items.values_list("custody_state", flat=True)), {"IN_VAULT"})
                    # Native completed charges remain recognized; paired terminal
                    # catch-up reverses. Recorded/opening retain their own writers.
                    self.assertEqual(preview_pawn_loan_full_release(loan.pk).minimum_settlement, amount)
                    for pk, fingerprint in frozen:
                        self.assertEqual(m.PawnLoanEvent.objects.get(pk=pk).payload_fingerprint, fingerprint)

    def successor_setup(self, day):
        create_pawn_loan_economic_policy(workspace=self.a, license=self.direct.license,
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal(".8"), advance_interest_periods=1,
            currency_quantum=self.quantum, effective_from=day, actor=self.actor)
        Rate.objects.create(rate_source=self.source, buying_rate=10000, selling_rate=10100, effective_at=timezone.now())
        for loan in self.loans:
            for item in loan.collateral_items.all():
                if not item.photos.exists():
                    append_collateral_photo(item.pk, upload=SimpleUploadedFile("current.jpg", b"\xff\xd8\xff\xe0evidence",
                        content_type="image/jpeg"), actor=self.actor)
                record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor, appraised_value=10000,
                    method="PHYSICAL_INSPECTION", evidence_reference="Synthetic current appraisal", review_notes="Current renewal check",
                    expected_version=item.appraisals.count())

    def renewal_values(self, loan):
        return dict(mode="TOP_UP_RENEW", principal_paid=Decimal("0"), top_up_amount=Decimal("100"),
            successor_license_id=self.direct.license_id, successor_series_id=self.direct.series_id,
            successor_product_version_id=self.direct.product_version_id, tenure_months=12,
            retained_collateral=(RetainedCollateralInput(loan.collateral_items.get().pk, self.remaining+100),))

    def test_current_renewal_preview_commit_retry_and_reversal_use_same_source_debt(self):
        day = date(2026, 6, 6)
        with self.scoped(), on(day):
            self.successor_setup(day)
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    values = self.renewal_values(loan)
                    preview = preview_pawn_loan_renewal_plan(loan.pk, **values)
                    self.assertEqual(preview.source.interest_settled, self.monthly*2)
                    command = dict(values, renewal_date=day, request_key="renew-" + str(loan.pk),
                        expected_preview_fingerprint=preview.fingerprint, actor=self.actor)
                    before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                    with self.assertRaises(ValueError):
                        renew_pawn_loan(loan.pk, **dict(command, expected_preview_fingerprint="changed"))
                    self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
                    result = renew_pawn_loan(loan.pk, **command)
                    self.assertEqual(result.renewal.interest_settled, self.monthly*2)
                    self.assertEqual(result.successor_loan.principal_amount, self.remaining+100)
                    self.assertEqual(result.successor_loan.policy_snapshot.basis, "ORIGINATION")
                    self.assertEqual(loan.collateral_items.get().custody_state, "RENEWAL_TRANSFERRED")
                    self.assertEqual(get_pawn_loan_balance(loan, as_of_date=day).total_due, 0)
                    count = loan.loan_events.count()
                    self.assertTrue(renew_pawn_loan(loan.pk, **command).already_renewed)
                    self.assertEqual(loan.loan_events.count(), count)
                    with self.assertRaises(PermissionDenied):
                        renew_pawn_loan(loan.pk, **dict(command, actor=None))
                    reverse_pawn_loan_renewal(result.renewal.pk, reason="Synthetic renewal reversal", actor=self.actor)
                    loan.refresh_from_db()
                    self.assertEqual((loan.state, loan.collateral_items.get().custody_state), ("ACTIVE", "IN_VAULT"))
                    self.assertEqual(get_pawn_loan_balance(loan, as_of_date=day).principal_outstanding, self.remaining)
                    if loan.pk == self.direct.pk:
                        self.assertEqual(get_pawn_loan_balance(loan, as_of_date=day).interest_outstanding, self.monthly)
                        with self.assertRaisesMessage(ValueError, "reversed monthly charge"):
                            prepare_loan_settlement(loan, operation="FULL_RELEASE", effective_date=day)
                    else:
                        quoted = prepare_loan_settlement(loan, operation="FULL_RELEASE", effective_date=day)
                        extra = quoted.catch_up_accrual.recognized_interest if quoted.catch_up_accrual else 0
                        self.assertEqual(quoted.balance_before_catch_up.interest_outstanding+extra, self.monthly*2)

    def test_overdue_auction_recognizes_once_caps_schedule_and_retains_statutory_and_reversal_guards(self):
        notice_day = date(2027, 5, 1)
        sale_day = notice_day + timedelta(days=60)
        with self.scoped():
            for loan in self.loans:
                with self.subTest(loan=loan.loan_number):
                    with on(notice_day):
                        self.review(loan, notice_day)
                        auction = auctions.initiate_pawn_loan_auction(loan.pk, scheduled_date=sale_day,
                            request_key="auction-" + str(loan.pk), actor=self.actor)
                    prepare_test_auction_service(auction, self.actor, notice_day)
                    with on(sale_day):
                        self.review(loan, sale_day)
                        auctions.start_pawn_loan_auction(auction.pk, actor=self.actor)
                        prepared = prepare_loan_settlement(loan, operation="AUCTION", effective_date=sale_day)
                        amount = prepared.balance_before_catch_up.total_due + (
                            prepared.catch_up_accrual.recognized_interest if prepared.catch_up_accrual else 0)
                        before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
                        rows = loan.interest_accruals.count()
                        command = dict(recovery_amount=amount, buyer_name="Synthetic buyer", actor=self.actor)
                        with self.assertRaisesMessage(ValueError, "exactly clear"):
                            auctions.complete_pawn_loan_auction(auction.pk, **dict(command, recovery_amount=1))
                        self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
                        self.assertEqual(rows, loan.interest_accruals.count())
                        result = auctions.complete_pawn_loan_auction(auction.pk, **command)
                        self.assertEqual(result.auction.interest_amount, amount-self.remaining)
                        self.assertEqual(get_pawn_loan_balance(loan, as_of_date=sale_day).total_due, 0)
                        self.assertEqual(loan.collateral_items.get().custody_state, "AUCTION_DISPOSED")
                        count = loan.loan_events.count()
                        self.assertTrue(auctions.complete_pawn_loan_auction(auction.pk, **command).already_completed)
                        self.assertEqual(loan.loan_events.count(), count)
                        with self.assertRaises(ValueError):
                            reverse_pawn_loan_event(result.loan_event.pk, reason="Wrong standalone reversal", actor=self.actor)
                        auctions.reverse_pawn_loan_auction(auction.pk, reason="Synthetic sale reversal", actor=self.actor)
                        loan.refresh_from_db()
                        self.assertEqual((loan.state, loan.collateral_items.get().custody_state), ("ACTIVE", "IN_VAULT"))
                        self.review(loan, sale_day)
                        if loan.pk == self.direct.pk:
                            with self.assertRaisesMessage(ValueError, "reversed monthly charge"):
                                prepare_loan_settlement(loan, operation="AUCTION", effective_date=sale_day)
                        else:
                            quoted = prepare_loan_settlement(loan, operation="AUCTION", effective_date=sale_day)
                            extra = quoted.catch_up_accrual.recognized_interest if quoted.catch_up_accrual else 0
                            self.assertEqual(quoted.balance_before_catch_up.total_due+extra, amount)


class WholeRupeeSettlementTests(SettlementContinuationTests):
    quantum = Decimal("1")
    principal = Decimal("5025.26")


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MultiItemSettlementTests(AdmissionFixture):
    multiple_items = True
    principal = Decimal("5025.50")
    reduction = Decimal("100.50")
    review = SettlementContinuationTests.review
    test_boundary_quotes_and_all_action_preparation_are_equal_and_read_only = (
        SettlementContinuationTests.test_boundary_quotes_and_all_action_preparation_are_equal_and_read_only)
    test_full_release_recognizes_once_mismatch_rolls_back_and_coupled_reversal_restores_debt = (
        SettlementContinuationTests.test_full_release_recognizes_once_mismatch_rolls_back_and_coupled_reversal_restores_debt)


class MultiItemWholeRupeeSettlementTests(MultiItemSettlementTests):
    quantum = Decimal("1")
