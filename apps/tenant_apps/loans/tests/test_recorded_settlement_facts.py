from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from dateutil.relativedelta import relativedelta
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction, connection
from django.test import override_settings
from django.urls import reverse
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_settlement_facts import preview_settlement_facts, record_settlement_facts
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
from apps.tenant_apps.loans.selectors.recorded_custody import current_custody_history
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"},
    "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RecordedSettlementFactsTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    def setUp(self):
        self.prepare_history()
        self.day = self.today-relativedelta(months=2)
        self.series.license.issued_on = self.day
        self.series.license.save()
        self.old_closing = self.day+relativedelta(months=1)+timedelta(days=2)
        self.data.update(date=self.day.isoformat(), final_state="CLOSED", events=[self.row(kind="CLOSE",
            date=self.old_closing.isoformat(), amount="10400", number="R-0008", closure_basis="PAPER_SETTLEMENT")])
        self.loan, _, _ = self.admit()
        self.release = self.loan.releases.get()
        self.facts = dict(date=(self.day+timedelta(days=3)).isoformat(), amount="10200", recipient="",
            reference="Checked original closing page", reason="Closing date copied incorrectly", request_key=uuid4().hex)

    def correct(self, facts=None):
        data = facts or self.facts
        review, token = preview_settlement_facts(self.loan.pk, actor=self.actor, data=data)
        log, created = record_settlement_facts(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertFalse(record_settlement_facts(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)[1])
        return log, review

    def test_closing_date_revisions_reconcile_business_date_money_and_custody(self):
        original = self.release.loan_event.payload_fingerprint
        log, _ = self.correct()
        self.assertEqual(collection_balance(self.loan, self.today).total_due, 0)
        earlier = self.day+timedelta(days=3)
        self.assertEqual(collection_balance(self.loan, earlier).total_due, 0)
        self.assertEqual(restated_release(self.release).effective_date, earlier)
        self.assertEqual([e.effective_date for e in current_custody_history(self.loan.collateral_items.get())], [earlier])
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.LoanChangeLog.objects.filter(pk=log.pk).delete()
        later = dict(self.facts, date=self.today.isoformat(), amount="10600", request_key=uuid4().hex)
        self.correct(later)
        self.assertEqual(collection_balance(self.loan, self.today).total_due, 0)
        self.assertEqual(collection_balance(self.loan, self.old_closing).principal_outstanding, 10000)
        self.assertEqual(restated_release(self.release).settlement_amount, 10600)
        self.assertEqual([e.effective_date for e in current_custody_history(self.loan.collateral_items.get())], [self.today])
        self.release.loan_event.refresh_from_db()
        self.assertEqual(self.release.loan_event.payload_fingerprint, original)
        self.assertEqual(self.release.effective_date, self.old_closing)
        self.assertEqual(self.release.custody_events.count(), 3)

    def test_corrected_date_allows_later_handover_before_erroneous_original_date(self):
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        self.correct()
        day = self.day+timedelta(days=5)
        data = dict(date=day.isoformat(), recipient="Borrower", reference="Signed receipt", request_key=uuid4().hex)
        _, token = preview_paper_handover(self.loan.pk, actor=self.actor, data=data)
        confirm_paper_handover(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        item = self.loan.collateral_items.get()
        self.assertEqual(item.custody_state, "WITH_CUSTOMER")
        self.assertEqual(current_custody_history(item)[-1].effective_date, day)
        with self.assertRaisesMessage(ValueError, "separately confirmed"):
            preview_settlement_facts(self.loan.pk, actor=self.actor, data=dict(self.facts,
                date=self.today.isoformat(), amount="10600", request_key=uuid4().hex))

    def test_exact_amount_authority_and_custody_basis_are_required(self):
        before = self.loan.loan_events.count()
        with self.assertRaises(PermissionDenied):
            preview_settlement_facts(self.loan.pk, actor=None, data=self.facts)
        with self.assertRaisesMessage(ValueError, "does not reconcile"):
            preview_settlement_facts(self.loan.pk, actor=self.actor, data=dict(self.facts, amount="10000"))
        with self.assertRaisesMessage(ValueError, "custody basis"):
            preview_settlement_facts(self.loan.pk, actor=self.actor, data=dict(self.facts, recipient="Assumed borrower"))
        self.assertEqual(self.loan.loan_events.count(), before)
        self.assertEqual(self.release.custody_events.count(), 1)

    def test_dated_custody_revision_requires_bound_financial_evidence_at_database_boundary(self):
        original = self.release.custody_events.get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnCollateralCustodyEvent.objects.create(workspace_id=self.tenant.pk,
                collateral_item_id=original.collateral_item_id, release=self.release, restatement_of=original,
                from_state=original.from_state, to_state=original.to_state, effective_date=self.day, actor=self.actor)
            connection.check_constraints()
        self.assertEqual(self.release.custody_events.count(), 1)

    def test_confirmed_return_recipient_and_date_are_corrected_without_another_return(self):
        # A separate numbered paper agreement with positively established return.
        self.data.update(number="P-0011", source_reference="Second paper agreement",
            events=[self.row(kind="CLOSE", date=self.old_closing.isoformat(), amount="10400", number="R-0009",
                closure_basis="RETURNED", recipient="Wrong spelling")])
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        self.loan, _, _ = self.admit()
        self.release = self.loan.releases.get()
        self.correct(dict(self.facts, recipient="Correct recipient"))
        current = restated_release(self.release)
        self.assertEqual(current.loan_event.payload["release"]["paper_closure"]["collector_name"], "Correct recipient")
        self.assertEqual(self.loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(current_custody_history(self.loan.collateral_items.get())[-1].effective_date.isoformat(), self.facts["date"])

    def test_ordinary_closing_review_and_retained_document(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_correct_paper_closing", kwargs=dict(workspace_slug=self.tenant.slug, pk=self.loan.pk))
        response = client.post(path, dict(self.facts, action="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        import os
        from pathlib import Path
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path(os.environ["PAPER_QA_CAPTURE"], "closing-correction.html").write_bytes(response.content)
        response = client.post(path, dict(self.facts, action="confirm", confirmed="on", review_token=response.context["form"]["review_token"].value()))
        self.assertEqual(response.status_code, 302)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.release_memo(self.release)
        self.assertEqual(dict(payload.details)["Effective date"].isoformat(), self.facts["date"])
