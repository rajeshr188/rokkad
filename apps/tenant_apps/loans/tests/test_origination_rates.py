from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import PawnLoanApprovalSnapshot
from apps.tenant_apps.loans.selectors.origination_rates import get_origination_quote_rows
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan, reopen_pawn_loan
from apps.tenant_apps.loans.services.loan_workflow import make_review, review_and_disburse
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.services import withdraw_quote


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OriginationRateTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def get_test_schema_name(cls):
        return "origination-quotes"

    def setUp(self):
        method = "LATEST_APPRAISAL" if self._testMethodName == "test_appraisal_only_needs_no_market_quote" else "LOWER_OF_CALCULATED_AND_APPRAISAL"
        self.make_loan(method=method, age_days=0, activate=False)

    def approve(self):
        return approve_pawn_loan(self.loan.pk, actor=self.actor)

    def disburse(self):
        return disburse_pawn_loan(self.loan.pk, actor=self.actor, effective_date=self.today)

    def new_quote(self, **changes):
        values = dict(rate_source=self.source, buying_rate=3000, selling_rate=3100, recorded_by=self.actor)
        values.update(changes)
        return Rate.objects.create(**values)

    def test_approval_freezes_exact_quote_and_disbursal_preserves_it(self):
        approval = self.approve()
        evidence = deepcopy(approval.payload["origination_rates"])
        quote = evidence["quotes"]["GOLD"]
        self.assertEqual(quote["rate_id"], self.quote.pk)
        self.assertEqual(quote["workspace_id"], self.tenant.pk)
        self.assertEqual(quote["source_snapshot"]["name"], "Market")
        self.assertEqual(quote["effective_at"], self.quote.effective_at.isoformat())
        self.assertEqual(quote["unit"], "gram")
        self.disburse()
        self.new_quote(buying_rate=3200)
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            self.assertTrue(self.disburse().already_disbursed)
        with self.assertRaises(PermissionDenied):
            disburse_pawn_loan(self.loan.pk, actor=None, effective_date=self.today)
        approval.refresh_from_db()
        self.assertEqual(approval.payload["origination_rates"], evidence)

    def test_previous_day_quote_blocks_without_creating_evidence(self):
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            with self.assertRaisesMessage(ValueError, "same-day"):
                self.approve()
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertFalse(self.item.appraisals.exists())

    def test_future_effective_quote_is_not_selected_today(self):
        future = self.new_quote(effective_at=timezone.now() + timedelta(hours=1), buying_rate=9000)
        from apps.tenant_apps.loans.web.appraisal import collateral_appraisal_suggestion
        request = RequestFactory().get("/", dict(metal="GOLD", gross_weight="1", net_weight="1",
            purity="100", as_of=self.today.isoformat(), request_key=1))
        request.user, request.workspace = self.actor, self.tenant
        self.assertContains(collateral_appraisal_suggestion(request), 'data-value="3000.00"')
        approval = self.approve()
        self.assertEqual(approval.payload["origination_rates"]["quotes"]["GOLD"]["rate_id"], self.quote.pk)
        self.assertNotEqual(future.pk, self.quote.pk)

    def test_future_loan_date_and_noncurrent_disbursal_dates_are_rejected(self):
        self.loan.loan_date = self.today + timedelta(days=1)
        self.loan.save(update_fields=["loan_date"])
        with self.assertRaisesMessage(ValueError, "Loan date must be today"):
            self.approve()
        self.loan.loan_date = self.today
        self.loan.save(update_fields=["loan_date"])
        self.approve()
        for delta in (-1, 1):
            with self.assertRaisesMessage(ValueError, "Disbursal date must be today"):
                disburse_pawn_loan(self.loan.pk, actor=self.actor, effective_date=self.today + timedelta(days=delta))
        self.assertFalse(self.loan.loan_events.exists())

    def test_delayed_disbursal_does_not_accept_yesterdays_approval(self):
        self.approve()
        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
            with self.assertRaisesMessage(ValueError, "Return to draft"):
                disburse_pawn_loan(self.loan.pk, actor=self.actor, effective_date=self.today + timedelta(days=1))
        self.assertFalse(self.loan.loan_events.exists())

    def test_equal_price_replacement_requires_reapproval_before_disbursal(self):
        original = self.approve()
        replacement = self.new_quote()
        with self.assertRaisesMessage(ValueError, "Return to draft"):
            self.disburse()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")
        self.assertFalse(self.loan.loan_events.exists())
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Review updated quote")
        revised = self.approve()
        self.assertEqual(revised.version, original.version + 1)
        self.assertEqual(revised.payload["origination_rates"]["quotes"]["GOLD"]["rate_id"], replacement.pk)
        self.disburse()

    def test_withdrawal_requires_reapproval(self):
        self.approve()
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk, reason="Withdraw reference")
        with self.assertRaisesMessage(ValueError, "Return to draft"):
            self.disburse()

    def test_equal_price_correction_requires_reapproval(self):
        self.approve()
        self.new_quote(supersedes=self.quote, reason="Correct quote evidence")
        with self.assertRaisesMessage(ValueError, "Return to draft"):
            self.disburse()

    def test_missing_second_metal_is_identified(self):
        self.item.metal = "SILVER"
        self.item.interest_rate_policy = None
        self.item.save(update_fields=["metal", "interest_rate_policy"])
        with self.assertRaisesMessage(ValueError, "Silver requires"):
            self.approve()

    def test_local_midnight_expires_quote(self):
        with timezone.override("Asia/Kolkata"):
            midnight = timezone.make_aware(datetime.combine(timezone.localdate(self.quote.effective_at) + timedelta(days=1), datetime.min.time()))
            before = get_origination_quote_rows(workspace_id=self.tenant.pk,
                loan_date=timezone.localdate(midnight - timedelta(seconds=1)), metals=("GOLD",), at=midnight - timedelta(seconds=1))
            after = get_origination_quote_rows(workspace_id=self.tenant.pk,
                loan_date=timezone.localdate(midnight), metals=("GOLD",), at=midnight)
        self.assertTrue(before[0]["fresh"])
        self.assertFalse(after[0]["fresh"])

    def test_missing_legacy_evidence_requires_reapproval(self):
        self.loan.state = "APPROVED"
        self.loan.save(update_fields=["state"])
        PawnLoanApprovalSnapshot.objects.create(loan=self.loan, version=1, payload={}, fingerprint="legacy")
        with self.assertRaisesMessage(ValueError, "lacks market quote evidence"):
            self.disburse()
        self.assertFalse(self.loan.loan_events.exists())

    def test_simple_review_detects_equal_price_replacement(self):
        self.tenant.loan_workflow = "SIMPLE"
        self.tenant.save(update_fields=["loan_workflow"])
        _, token = make_review(self.loan)
        self.new_quote()
        with self.assertRaisesMessage(ValueError, "changed"):
            review_and_disburse(self.loan.pk, actor=self.actor, effective_date=self.today, token=token)
        self.assertFalse(self.loan.approval_snapshots.exists())

    def test_quote_change_during_approval_rolls_back_appraisals_and_approval(self):
        from apps.tenant_apps.loans.services import pawn_lifecycle
        original = pawn_lifecycle._freeze_approved_appraisals
        def changed(*args, **kwargs):
            self.new_quote()
            return original(*args, **kwargs)
        with patch.object(pawn_lifecycle, "_freeze_approved_appraisals", side_effect=changed):
            with self.assertRaisesMessage(ValueError, "Return to draft"):
                self.approve()
        self.assertFalse(self.item.appraisals.exists())
        self.assertFalse(self.loan.approval_snapshots.exists())

    def test_appraisal_only_needs_no_market_quote(self):
        approval = self.approve()
        self.assertEqual(approval.payload["origination_rates"]["quotes"], {})
        self.disburse()

    def test_foreign_context_and_unauthorized_actor_fail_closed(self):
        with self.assertRaisesMessage(ValueError, "active Workspace"):
            get_origination_quote_rows(workspace_id=self.tenant.pk + 1000, loan_date=self.today, metals=("GOLD",))
        with self.assertRaises(PermissionDenied):
            approve_pawn_loan(self.loan.pk, actor=None)
        self.assertFalse(self.loan.approval_snapshots.exists())

    def test_quote_change_during_disbursal_rolls_back_financial_records(self):
        from apps.tenant_apps.loans.services import pawn_disbursal
        self.approve()
        original = pawn_disbursal.persist_disbursal_repayment_schedule
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.new_quote()
            return result
        with patch.object(pawn_disbursal, "persist_disbursal_repayment_schedule", side_effect=changed):
            with self.assertRaisesMessage(ValueError, "Return to draft"):
                self.disburse()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")
        self.assertFalse(self.loan.loan_events.exists())
        self.assertFalse(self.loan.repayment_schedules.exists())

    def test_approved_loan_displays_quote_evidence_and_recovery_links(self):
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        from apps.tenant_apps.loans.web.pawn_financial_actions import pawn_loan_disburse
        self.approve()
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        self.assertContains(pawn_loan_detail(request, self.loan.pk), f"Quote #{self.quote.pk}")
        self.assertContains(pawn_loan_disburse(request, self.loan.pk), "Return to draft for a fresh approval")

    def test_renewal_rejects_replaced_review_quote_without_partial_successor(self):
        from apps.tenant_apps.loans.models import PawnLoan, PawnLoanRenewal
        from apps.tenant_apps.loans.services.pawn_renewals import (
            RetainedCollateralInput, preview_pawn_loan_renewal_plan, renew_pawn_loan,
        )
        self.approve()
        self.disburse()
        values = dict(mode="PAY_AND_RENEW", principal_paid=Decimal("0"),
            top_up_amount=Decimal("0"), successor_license_id=self.loan.license_id,
            successor_series_id=self.loan.series_id, tenure_months=12,
            retained_collateral=(RetainedCollateralInput(self.item.pk, Decimal("1000")),))
        preview = preview_pawn_loan_renewal_plan(self.loan.pk, **values)
        count = PawnLoan.objects.count()
        self.new_quote()
        with self.assertRaisesMessage(ValueError, "changed"):
            renew_pawn_loan(self.loan.pk, **values, renewal_date=self.today,
                request_key="quote-renewal-review", actor=self.actor,
                expected_preview_fingerprint=preview.fingerprint)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(PawnLoan.objects.count(), count)
        self.assertFalse(PawnLoanRenewal.objects.filter(source_loan=self.loan).exists())
        fresh = preview_pawn_loan_renewal_plan(self.loan.pk, **values)
        result = renew_pawn_loan(self.loan.pk, **values, renewal_date=self.today,
            request_key="quote-renewal-review", actor=self.actor,
            expected_preview_fingerprint=fresh.fingerprint)
        self.assertEqual(result.successor_loan.state, "ACTIVE")
