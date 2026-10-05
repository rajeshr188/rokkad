from decimal import Decimal
from pathlib import Path
from uuid import uuid4
import os

from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.economic_policies import (
    create_pawn_economic_configuration, create_pawn_loan_fee_policy,
)
from apps.tenant_apps.loans.services.paper_entry_terms import paper_entry_terms, preferred_paper_product
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PaperEntrySimplificationTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row

    @classmethod
    def get_test_schema_name(cls):
        return "paper-simplification"

    def setUp(self):
        self.prepare_history()
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        self.path = reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug])
        product = m.LoanProduct.objects.create(workspace=self.tenant, code="PAPER-FLEX", name="Flexible partial payment")
        self.flex = m.LoanProductVersion.objects.create(workspace=self.tenant, product=product, version=1,
            status="ACTIVE", repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE",
            payment_frequency="AT_MATURITY", minimum_tenor_months=1, maximum_tenor_months=600,
            extra_payment_rule="REDUCE_PRINCIPAL", calculation_contract_version="TEST-V1")
        self.configure()
        create_pawn_loan_fee_policy(workspace=self.tenant, license=self.series.license, code="DOCUMENT_CHARGE",
            name="Document charge", calculation_type="FIXED", value=Decimal("10"), effective_from=self.day, actor=self.actor)

    def configure(self, **changes):
        values = dict(workspace=self.tenant, series=self.series, license=self.series.license,
            gold_monthly_interest_rate=Decimal("2"), silver_monthly_interest_rate=Decimal("4"),
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal("0.8"),
            default_tenure_months=12, advance_interest_periods=1, effective_from=self.day, actor=self.actor)
        values.update(changes)
        return create_pawn_economic_configuration(**values)

    def facts(self, **changes):
        page = self.client.get(self.path + "?entry=paper")
        fields = ("borrower_id", "series_id", "number", "date", "source_reference", "description", "metal", "quantity", "gross_weight", "net_weight", "purity")
        values = {key: self.data[key] for key in fields}
        values.update(principal="12000", routine_entry="True", entry_mode="paper", action="preview",
            final_state="ACTIVE", intent_token=page.context["intent_token"],
            **{"events-TOTAL_FORMS": "0", "events-INITIAL_FORMS": "0"})
        values.update(changes)
        return values

    def preview(self, values):
        response = self.client.post(self.path, values)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors, response.context["form"].errors)
        self.assertIsNotNone(response.context["review"])
        return response

    def admit(self, values=None):
        values = values or self.facts()
        preview = self.preview(values)
        self.capture("paper-entry-review", preview)
        response = self.client.post(self.path, dict(values, action="confirm", confirm_review="on", review_token=preview.context["review_token"]))
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        loan = m.PawnLoan.objects.get(loan_number=values["number"])
        return loan, response, preview

    def capture(self, name, response):
        if os.environ.get("PAPER_QA_CAPTURE"):
            (Path(os.environ["PAPER_QA_CAPTURE"]) / (name + ".html")).write_bytes(response.content)

    def test_defaults_twelve_month_flexible_calculated_deductions_and_no_fake_verification(self):
        loan, response, _ = self.admit()
        self.assertEqual((loan.product_version_id, loan.tenure_months, loan.monthly_interest_rate), (self.flex.pk, 12, Decimal("2")))
        self.assertEqual((loan.disbursal_snapshot.advance_interest, loan.disbursal_snapshot.deducted_fees, loan.disbursal_snapshot.net_disbursed), (240, 10, 11750))
        self.assertIsNone(loan.disbursal_snapshot.approval_snapshot_id)
        self.assertIsNone(loan.disbursal_snapshot.evidence["recording"]["funding"]["actual_cash_paid"])
        self.assertFalse(loan.transaction_reviews.exists())
        self.assertFalse(transaction_completeness(loan, self.today).complete)
        self.assertEqual(collection_balance(loan, self.today).total_due, 12000)
        detail = self.client.get(response.url)
        self.assertEqual(detail.status_code, 200)
        self.capture("paper-entry-detail", detail)

    def test_term_refresh_is_read_only_and_partial_facts_need_no_other_confirmation(self):
        before = m.PawnLoanEvent.objects.count()
        values = self.facts(action="terms")
        for field in ("borrower_id", "number", "source_reference", "gross_weight", "net_weight", "purity"):
            values.pop(field)
        response = self.client.post(self.path, values)
        self.assertFalse(response.context["form"].errors, response.context["form"].errors)
        self.assertIsNone(response.context["review"])
        self.assertContains(response, "Standing agreement")
        self.assertEqual(m.PawnLoanEvent.objects.count(), before)
        self.capture("paper-entry-terms", response)

    def test_supported_actual_exception_keeps_original_rate_and_source_reason(self):
        values = self.facts(exceptions="on", exception_reason="Actual agreement in book A",
            product_version_id=self.flex.pk, rate="1.5", tenure="9", advance_months="0", document_charge="5",
            payout_basis="PROCEEDS", monitoring_method="CALCULATED_METAL_VALUE", monitoring_ltv="0.8",
            monitoring_reason="Standing current cover")
        loan, _, _ = self.admit(values)
        self.assertEqual((loan.monthly_interest_rate, loan.tenure_months, loan.disbursal_snapshot.net_disbursed), (Decimal("1.5"), 9, 11995))
        self.assertIn("Actual agreement", loan.disbursal_snapshot.evidence["recording"]["entry_note"])

    def test_setup_change_invalidates_review_and_existing_contract_stays_frozen(self):
        values = self.facts()
        preview = self.preview(values)
        self.configure(gold_monthly_interest_rate=Decimal("3"))
        response = self.client.post(self.path, dict(values, action="confirm", confirm_review="on", review_token=preview.context["review_token"]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())
        loan, _, _ = self.admit(values)
        self.configure(gold_monthly_interest_rate=Decimal("4"), default_tenure_months=6)
        loan.refresh_from_db()
        self.assertEqual((loan.monthly_interest_rate, loan.tenure_months), (Decimal("3"), 12))

    def test_explicit_complete_book_verification_requires_date_and_is_retained(self):
        values = self.facts(confirmed_history="on")
        response = self.client.post(self.path, values)
        self.assertIn("complete_through", response.context["form"].errors)
        loan, _, _ = self.admit(dict(values, complete_through=self.today.isoformat()))
        self.assertTrue(transaction_completeness(loan, self.today).complete)

    def test_unverified_closure_does_not_create_a_complete_book_claim(self):
        from apps.tenant_apps.loans.services.recorded_closures import preview_recorded_closure, record_paper_closure
        loan, _, _ = self.admit()
        facts = dict(date=self.today.isoformat(), amount="12000", number="", reference="Book closing page",
            basis="PAPER_SETTLEMENT", recipient="", request_key=str(uuid4()))
        _, token = preview_recorded_closure(loan_id=loan.pk, actor=self.actor, data=facts)
        record_paper_closure(loan_id=loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CLOSED")
        self.assertFalse(loan.transaction_reviews.exists())

    def test_scope_and_unsupported_policies_are_explicit_and_product_choice_unambiguous(self):
        self.assertEqual(preferred_paper_product(workspace=self.tenant, day=self.day).pk, self.flex.pk)
        self.configure(partial_month_method="STARTED_WEEKS")
        terms = paper_entry_terms(workspace=self.tenant, series=self.series, day=self.day, metal="GOLD", principal=Decimal("12000"))
        self.assertNotIn("advance_months", terms["values"])
        self.assertTrue(terms["messages"])
        values = self.facts()
        response = self.client.post(self.path, values)
        self.assertTrue(response.context["form"].errors)

    def test_missing_historical_digital_setup_allows_supported_actual_agreement(self):
        from datetime import timedelta
        m.LoanLicense.objects.filter(pk=self.series.license_id).update(issued_on=self.day-timedelta(days=1))
        values = self.facts(date=(self.day-timedelta(days=1)).isoformat(), exceptions="on",
            exception_reason="Standing agreement from paper book", rate="2", tenure="12", advance_months="1",
            document_charge="10", monitoring_method="CALCULATED_METAL_VALUE", monitoring_ltv="0.8",
            monitoring_reason="Current cover policy", payout_basis="PROCEEDS")
        loan, _, _ = self.admit(values)
        self.assertEqual(loan.loan_date.isoformat(), values["date"])
        self.assertEqual(loan.disbursal_snapshot.net_disbursed, 11750)

    def test_multiple_flexible_products_require_explicit_choice(self):
        product = m.LoanProduct.objects.create(workspace=self.tenant, code="OTHER-FLEX", name="Other flexible")
        other = m.LoanProductVersion.objects.create(workspace=self.tenant, product=product, version=1,
            status="ACTIVE", repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE",
            payment_frequency="AT_MATURITY", minimum_tenor_months=1, maximum_tenor_months=600,
            extra_payment_rule="REDUCE_PRINCIPAL", calculation_contract_version="TEST-V1")
        self.assertIsNone(preferred_paper_product(workspace=self.tenant, day=self.day))
        values = self.facts()
        response = self.client.post(self.path, values)
        self.assertIn("product_version_id", response.context["form"].errors)
        loan, _, _ = self.admit(dict(values, product_version_id=other.pk))
        self.assertEqual(loan.product_version_id, other.pk)

    def test_additional_fee_is_not_silently_dropped(self):
        create_pawn_loan_fee_policy(workspace=self.tenant, license=self.series.license, code="OTHER",
            name="Other charge", calculation_type="FIXED", value=Decimal("20"), effective_from=self.day, actor=self.actor)
        response = self.client.post(self.path, self.facts())
        self.assertTrue(response.context["form"].errors)
        self.assertContains(response, "Configured fees exceed")
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())

    def test_default_resolver_rejects_foreign_workspace_and_native_uses_tenure(self):
        from apps.orgs.models import Company
        from apps.tenant_apps.loans.forms import PawnDraftForm
        other = Company(pk=self.tenant.pk+999)
        with self.assertRaisesMessage(ValueError, "Workspace"):
            paper_entry_terms(workspace=other, series=self.series, day=self.day, metal="GOLD")
        form = PawnDraftForm(workspace=self.tenant, initial={"series":self.series.pk, "loan_date":self.day})
        self.assertEqual(form["tenure_months"].value(), 12)

    def test_exact_routine_confirmation_retry_does_not_duplicate_loan_or_events(self):
        values = self.facts()
        preview = self.preview(values)
        post = dict(values, action="confirm", confirm_review="on", review_token=preview.context["review_token"])
        self.assertEqual(self.client.post(self.path, post).status_code, 302)
        before = m.PawnLoanEvent.objects.count()
        self.assertEqual(self.client.post(self.path, post).status_code, 302)
        self.assertEqual(m.PawnLoanEvent.objects.count(), before)
        self.assertEqual(m.PawnLoan.objects.filter(loan_number="P-0010").count(), 1)
