from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
from apps.tenant_apps.loans.services.recorded_collections import collection_balance, recording_for
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RecordedContractCorrectionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit
    from .test_independent_paper import IndependentPaperTests
    renewal_data = IndependentPaperTests.renewal_data

    @classmethod
    def get_test_schema_name(cls):
        return "recorded-contract-correction"

    def setUp(self):
        self.prepare_history()

    def data_for(self):
        return dict(date=self.day.isoformat(), principal="12000", rate="3", cash_paid="12000",
            reference="Checked original book", reason="Principal and rate transcribed incorrectly", request_key=uuid4().hex)

    def test_correct_terms_replays_receipt_and_preserves_original_snapshots(self):
        self.data["events"] = [self.row(amount="2000")]
        loan, _, _ = self.admit()
        old_snapshot = loan.disbursal_snapshot
        old_origin = old_snapshot.loan_event
        old_payload = old_origin.payload
        data = self.data_for()
        review, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        loan.refresh_from_db()
        self.assertEqual(loan.principal_amount, 10000)
        self.assertEqual(Decimal(review["after"]["balance"]), 10360)
        self.assertEqual(Decimal(review["rows"][0]["interest"]), 360)
        correction, created = record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        from django.db import DatabaseError, transaction
        from apps.tenant_apps.loans import models as m
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.LoanChangeLog.objects.filter(pk=correction.pk).delete()
        loan.refresh_from_db()
        self.assertEqual(loan.principal_amount, 12000)
        self.assertEqual(loan.monthly_interest_rate, 3)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 10360)
        self.assertEqual(loan.disbursal_snapshots.count(), 2)
        old_origin.refresh_from_db()
        self.assertEqual(old_origin.payload, old_payload)
        self.assertEqual(recording_for(loan)["terms"]["principal_amount"], "12000.00")
        self.assertEqual(transaction_completeness(loan, self.today).status, "CHANGED")
        self.assertFalse(record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)[1])
        with self.assertRaisesMessage(ValueError, "different contract facts"):
            record_contract_correction(loan.pk, actor=self.actor, data=dict(data, rate="4"), review_token=token, confirmed=True)

    def test_correct_original_date_and_advance_reconciles_proceeds(self):
        self.data.update(advance_months=1, cash_paid="9800")
        loan, _, _ = self.admit()
        data = dict(self.data_for(), date=(self.day-timedelta(days=2)).isoformat(), cash_paid="11640")
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(loan.loan_date, self.day-timedelta(days=2))
        self.assertEqual(collection_balance(loan, self.today).total_due, 12000)
        self.assertEqual(loan.disbursal_snapshot.advance_interest, 360)

    def test_closed_contract_requires_exact_reconciled_settlement_preserving_custody(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="R-0008", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        custody = list(loan.collateral_items.get().custody_history.values_list("pk", flat=True))
        settlement = dict(cash_received="12360", cash_paid="0", interest_offset="0", reference="Corrected book closing", confirmed_unchanged=True)
        data = dict(self.data_for(), settlement=settlement)
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(collection_balance(loan, self.today).total_due, 0)
        self.assertEqual(loan.collateral_items.get().custody_state, "PAPER_CLOSED")
        self.assertEqual(list(loan.collateral_items.get().custody_history.values_list("pk", flat=True)), custody)
        self.assertEqual(loan.releases.get().settlement_amount, 10200)
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
        self.assertEqual(restated_release(loan.releases.get()).settlement_amount, 12360)

    def test_failed_replay_rolls_back_contract_and_all_compensations(self):
        self.data["events"] = [self.row(amount="9000")]
        loan, _, _ = self.admit()
        before = loan.loan_events.count()
        data = dict(self.data_for(), principal="5000", cash_paid="5000")
        with self.assertRaises(ValueError):
            preview_contract_correction(loan.pk, actor=self.actor, data=data)
        loan.refresh_from_db()
        self.assertEqual(loan.principal_amount, 10000)
        self.assertEqual(loan.loan_events.count(), before)
        self.assertEqual(loan.disbursal_snapshots.count(), 1)

    def test_successor_terms_reconcile_paired_funding_and_preserve_renewal_evidence(self):
        from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_renewal
        source, _, _ = self.admit()
        facts = self.renewal_data()
        _, token = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=facts)
        loan, _ = record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        original = loan.origin_renewal
        frozen = original.opening_event.payload_fingerprint
        custody = list(loan.collateral_items.get().custody_history.values_list("pk", flat=True))
        data = dict(self.data_for(), date=self.today.isoformat(), principal="13000", rate="3", cash_paid="12600",
            predecessor=dict(cash_received="0", cash_paid="2400", interest_offset="200",
                reference="Checked corrected new agreement", confirmed_custody=True))
        review, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 13000)
        self.assertEqual(collection_balance(loan, self.today).interest_outstanding, 0)
        current = restated_renewal(original)
        self.assertEqual(current.successor_principal_amount, 13000)
        self.assertEqual(current.top_up_amount, 3000)
        self.assertEqual(current.successor_advance_interest, 390)
        self.assertEqual(current.successor_deducted_fees, 10)
        original.opening_event.refresh_from_db()
        self.assertEqual(original.opening_event.payload_fingerprint, frozen)
        self.assertEqual(list(loan.collateral_items.get().custody_history.values_list("pk", flat=True)), custody)
        # A second correction resolves the retained original pair to current evidence.
        again = dict(data, rate="2", cash_paid="12730", request_key=uuid4().hex,
            predecessor=dict(data["predecessor"], cash_paid="2530"))
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=again)
        record_contract_correction(loan.pk, actor=self.actor, data=again, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(loan.monthly_interest_rate, 2)

    def test_paired_renewal_date_correction_preserves_custody_and_reconciles_both_loans(self):
        from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_renewal
        from apps.tenant_apps.loans.selectors.recorded_custody import current_custody_history
        source, _, _ = self.admit()
        renewal = self.renewal_data()
        _, token = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=renewal)
        successor, _ = record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=renewal, review_token=token, confirmed=True)
        day = self.day+timedelta(days=3)
        data = dict(self.data_for(), date=day.isoformat(), principal="12000", rate="2", cash_paid="11750",
            predecessor=dict(cash_received="0", cash_paid="1550", interest_offset="200", reference="Correct date on paper", confirmed_custody=True))
        _, token = preview_contract_correction(successor.pk, actor=self.actor, data=data)
        record_contract_correction(successor.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        successor.refresh_from_db()
        self.assertEqual(successor.loan_date, day)
        self.assertEqual(restated_renewal(successor.origin_renewal).renewal_date, day)
        self.assertEqual(collection_balance(source, day).total_due, 0)
        self.assertEqual(collection_balance(source, self.today).total_due, 0)
        self.assertEqual(collection_balance(successor, day).total_due, 12000)
        self.assertEqual(current_custody_history(source.collateral_items.get())[-1].effective_date, day)
        self.assertEqual(source.collateral_items.get().custody_state, "RENEWAL_TRANSFERRED")

    def test_changed_source_or_unauthorized_actor_cannot_amend_contract(self):
        loan, _, _ = self.admit()
        data = self.data_for()
        with self.assertRaises(PermissionDenied):
            preview_contract_correction(loan.pk, actor=None, data=data)
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=data)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        record_pawn_loan_repayment(loan.pk, amount="200", request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            record_contract_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)

    def test_ordinary_contract_review_and_corrected_copy_preserve_prior_issued_bytes(self):
        self.start_active_trial()
        loan, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        document_path = reverse("workspace_loans:pawn_loan_ticket_pdf", kwargs=dict(workspace_slug=self.tenant.slug, pk=loan.pk))
        original = client.get(document_path)
        self.assertEqual(original.status_code, 200)
        original_id, original_bytes = original["X-Rokkad-Document-Issue"], original.content
        path = reverse("workspace_loans:pawn_loan_correct_paper_contract", kwargs=dict(workspace_slug=self.tenant.slug, pk=loan.pk))
        data = self.data_for()
        review = client.post(path, dict(data, action="preview"))
        self.assertEqual(review.status_code, 200)
        self.assertFalse(review.context["form"].errors)
        import os
        from pathlib import Path
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path(os.environ["PAPER_QA_CAPTURE"], "contract-correction.html").write_bytes(review.content)
        response = client.post(path, dict(data, action="confirm", review_token=review.context["form"]["review_token"].value(), confirmed="on"))
        self.assertEqual(response.status_code, 302)
        corrected = client.get(document_path)
        self.assertEqual(corrected.status_code, 200)
        self.assertNotEqual(corrected["X-Rokkad-Document-Issue"], original_id)
        self.assertNotEqual(corrected.content, original_bytes)
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        from apps.tenant_apps.loans import models as m
        self.assertEqual(LoanDocumentLayoutService.read_verified_artifact(m.LoanDocumentIssue.objects.get(pk=original_id)), original_bytes)
        self.assertEqual(client.get(document_path).content, corrected.content)
