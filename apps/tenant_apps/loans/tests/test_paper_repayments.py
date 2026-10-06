from copy import deepcopy
from datetime import date, datetime
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans.services import paper_repayments as paper
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance, get_pawn_loan_exposure
from .test_opening_release import OpeningReleaseFixture


class PaperRepaymentTests(OpeningReleaseFixture):
    def setUp(self):
        super().setUp()
        self.day = date(2021, 3, 2)
        self.inputs = dict(amount="210", received_on=date(2021, 2, 2),
                           receipt_reference="Book A / 17", request_key="paper-17", actor=self.actor)

    def preview(self, **changes):
        return paper.preview_paper_repayment(self.loan.pk, **{**self.inputs, **changes})

    def record(self, review=None, **changes):
        values = {**self.inputs, **changes}
        if review is None:
            review = paper.preview_paper_repayment(self.loan.pk, **values)
        return paper.record_paper_repayment(self.loan.pk, **values,
            review_token=review.review_token, confirmed_received=True)

    def test_actual_date_drives_interest_and_future_monitoring_without_new_cash_today(self):
        review = self.preview()
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertEqual((review.preview.allocation.interest, review.preview.allocation.principal), (10, 200))
        result = self.record(review)
        event = result.loan_event
        self.assertEqual(event.effective_date, date(2021, 2, 2))
        self.assertEqual(event.created_by, self.actor)
        self.assertNotEqual(event.created_at.date(), event.effective_date)
        self.assertEqual(event.payload["repayment"]["recording"]["receipt_reference"], "Book A / 17")
        self.assertIsNone(event.payload["repayment"]["recording"]["original_receiver"])
        self.assertEqual(event.payload["repayment"]["recording"]["allocation_basis"], "DERIVED_FROM_AGREED_TERMS")
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=date(2021, 2, 1)).principal_outstanding, 1000)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=date(2021, 2, 2)).principal_outstanding, 800)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 808)
        self.assertFalse(self.loan.loan_events.filter(event_kind="REPAYMENT", effective_date=self.day).exists())
        self.item.refresh_from_db()
        self.assertEqual(self.item.custody_state, "IN_VAULT")

    def test_earlier_today_and_partial_interest(self):
        result = self.record(received_on=self.day, amount="5")
        self.assertEqual((result.allocation.interest, result.allocation.principal), (5, 0))
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.day).interest_outstanding, 15)

    def test_retry_matches_facts_and_does_not_repost(self):
        review = self.preview()
        result = self.record(review)
        again = self.record(review)
        self.assertTrue(again.already_recorded)
        self.assertEqual(again.loan_event.pk, result.loan_event.pk)
        self.assertEqual(self.loan.loan_events.count(), 3)
        for change in ({"received_on": date(2021, 2, 3)}, {"receipt_reference": "Another receipt"}, {"amount": "211"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.record(review, **change)
        with self.assertRaisesMessage(ValueError, "recording purpose"):
            record_pawn_loan_repayment(self.loan.pk, amount="210", request_key="paper-17", actor=self.actor)

    def test_duplicate_reference_with_new_request_and_after_reversal_is_rejected(self):
        result = self.record()
        with self.assertRaisesMessage(ValueError, "already recorded"):
            self.preview(request_key="new", receipt_reference="  BOOK A  / 17  ")
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Wrong receipt")
        with self.assertRaisesMessage(ValueError, "already recorded"):
            self.preview(request_key="new", received_on=self.day)

    def test_invalid_amount_dates_and_missing_reference_write_nothing(self):
        for change in (
            {"amount": "NaN"}, {"amount": "Infinity"}, {"amount": "0"}, {"amount": "-1"},
            {"amount": "1.001"}, {"amount": "1011"},
            {"received_on": date(2021, 3, 3)}, {"received_on": date(2021, 1, 20)},
            {"received_on": datetime(2021, 2, 2)}, {"receipt_reference": " "},
            {"receipt_reference": "book\n17"},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.preview(**change)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_missing_expired_or_changed_review_and_missing_confirmation_refused(self):
        review = self.preview()
        for token in ("", "tampered"):
            with self.assertRaisesMessage(ValueError, "Preview this receipt again"):
                paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=token, confirmed_received=True)
        with patch.object(paper.signing, "loads", side_effect=signing.SignatureExpired()):
            with self.assertRaises(ValueError):
                self.record(review)
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.record(review, amount="211")
        with self.assertRaisesMessage(ValueError, "Confirm"):
            paper.record_paper_repayment(self.loan.pk, **self.inputs, review_token=review.review_token)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_same_day_new_activity_invalidates_review(self):
        self.day = self.inputs["received_on"]
        review = self.preview()
        record_pawn_loan_repayment(self.loan.pk, amount="1", request_key="another", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.record(review)

    def test_later_recorded_activity_blocks_backdated_insertion(self):
        review = self.preview()
        record_pawn_loan_repayment(self.loan.pk, amount="20", request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "Later activity"):
            self.record(review)

    def test_authorization_on_preview_and_completed_retry(self):
        with self.assertRaises(PermissionDenied):
            self.preview(actor=None)
        review = self.preview()
        self.record(review)
        with self.assertRaises(PermissionDenied):
            self.record(review, actor=None)

    def test_staff_authority_actor_binding_and_cross_workspace(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.testing import workspace_role_permissions
        from apps.tenancy.context import without_workspace_context, workspace_context
        user = get_user_model().objects.create_user(username="paper-receipt-staff")
        role = Role.objects.create(name="Paper receipts")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        workspace_role_permissions(role, self.tenant).set(Permission.objects.filter(
            content_type__app_label="orgs", content_type__model="company", codename__in=["data_view", "loan_repay"]))
        review = self.preview()
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.record(review, actor=user)
        result = self.record(actor=user)
        self.assertEqual(result.loan_event.created_by, user)
        other = Company.objects.create(name="Other paper", schema_name="paper-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(ValueError):
            self.preview()

    def test_unknown_valuation_does_not_block_payment_or_hide_debt(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        self.record()
        valuation = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.day)
        self.assertIsNone(valuation.ltv.ltv_ratio)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 808)

    def test_document_marks_paper_origin_and_separates_entry_time(self):
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        result = self.record()
        projection = PawnLoanDocumentProjectionBuilder.repayment_receipt(result.loan_event)
        fields = {field.key: field.value for field in projection.fields}
        self.assertEqual(fields["event.effective_date"], date(2021, 2, 2))
        self.assertEqual(fields["repayment.recorded_at"], result.loan_event.created_at)
        self.assertEqual(fields["repayment.paper_reference"], "Book A / 17")
        self.assertIn("from paper", fields["document.status"])

    def test_native_loan_is_not_silently_backdated(self):
        from apps.tenant_apps.loans.models import PawnLoan, LoanPolicySnapshot
        native = PawnLoan.objects.create(workspace=self.tenant, borrower=self.loan.borrower,
            license=self.loan.license, license_revision=self.loan.license_revision,
            series=self.loan.series, product_version=self.loan.product_version,
            loan_number="NATIVE-1", loan_date=date(2021, 1, 1), tenure_months=3,
            principal_amount=1000, monthly_interest_rate=1, state="ACTIVE")
        LoanPolicySnapshot.objects.create(loan=native, interest_method="SIMPLE",
            partial_month_method="FULL_MONTH", valuation_method="LATEST_APPRAISAL",
            rounding_method="PER_ACCRUAL_PERIOD")
        with self.assertRaisesMessage(ValueError, "no supported financial origin"):
            paper.preview_paper_repayment(native.pk, **self.inputs)
        self.assertFalse(native.loan_events.exists())
        from apps.tenant_apps.loans.forms import PawnRepaymentForm
        form = PawnRepaymentForm(dict(recording_purpose="PAPER", amount="210", request_key="forged"))
        self.assertFalse(form.is_valid())
        self.assertIn("recording_purpose", form.errors)

    def test_rollback_includes_interest_and_receipt(self):
        review = self.preview()
        with patch("apps.tenant_apps.loans.services.pawn_repayment.allocate_event_to_obligations", side_effect=RuntimeError("failure")):
            with self.assertRaises(RuntimeError):
                self.record(review)
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(self.loan.interest_accruals.exists())

    def test_correction_restores_balance_without_mutating_paper_evidence(self):
        result = self.record()
        source = deepcopy(result.loan_event.payload)
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Receipt entered incorrectly")
        result.loan_event.refresh_from_db()
        self.assertEqual(result.loan_event.payload, source)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 1020)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_ordinary_screen_requires_review_and_displays_recorded_source(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        args = {"workspace_slug": self.tenant.slug, "pk": self.loan.pk}
        url = reverse("workspace_loans:pawn_loan_repay", kwargs=args)
        self.assertContains(client.get(url), "Record a paper receipt")
        data = dict(recording_purpose="PAPER", amount="210", received_on="2021-02-02",
                    receipt_reference="Book A / 17", request_key="paper-ui", confirmed_received="on")
        refused = client.post(url, {**data, "action": "confirm"})
        self.assertContains(refused, "Preview this receipt again")
        response = client.post(url, {**data, "action": "preview"})
        self.assertContains(response, "02/02/2021")
        self.assertContains(response, "Evidence behind these amounts")
        self.assertEqual(response.context["evidence_quality"]["calculation"]["status"], "SUPPORTED")
        self.assertFalse(response.context["evidence_quality"]["transactions"]["complete"])
        self.assertContains(response, "was not supplied as a split on paper")
        self.assertEqual(self.loan.loan_events.count(), 1)
        token = response.context["form"]["review_token"].value()
        self.assertTrue(token)
        response = client.post(url, {**data, "action": "confirm", "review_token": token})
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response.url), "Book A / 17")
        self.assertEqual(self.loan.loan_events.get(event_kind="REPAYMENT").effective_date, date(2021, 2, 2))


class PaperRepaymentFeesTests(OpeningReleaseFixture):
    def review_document(self):
        doc = super().review_document()
        doc["balances"]["fees"] = "5"
        return doc

    def test_paper_fee_allocation_refused_but_current_repayment_unchanged(self):
        with self.assertRaisesMessage(ValueError, "actual fee component"):
            paper.preview_paper_repayment(self.loan.pk, amount="215", received_on=self.day,
                receipt_reference="fees-1", request_key="fees-1", actor=self.actor)
        self.assertEqual(self.loan.loan_events.count(), 1)
        result = record_pawn_loan_repayment(self.loan.pk, amount="215", request_key="current", actor=self.actor)
        self.assertEqual((result.allocation.fees, result.allocation.interest, result.allocation.principal), (5, 10, 200))
