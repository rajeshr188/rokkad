from copy import deepcopy
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.services.recorded_closures import preview_recorded_closure, record_paper_closure
from apps.tenant_apps.loans.services.recorded_renewal_actions import preview_existing_paper_renewal, record_existing_paper_renewal
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class IndependentPaperTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "independent-paper"

    def setUp(self):
        self.prepare_history()

    def closure_data(self):
        return dict(date=self.today.isoformat(), amount="10200", number="R-0008", reference="Book / A closed",
            basis="PAPER_SETTLEMENT", recipient="", request_key=str(uuid4()))

    def renewal_data(self):
        return dict(date=self.today.isoformat(), number="P-0011", reference="Book / B", new_principal="12000",
            rate="2", tenure=3, advance_months=1, document_charge="10", amount="0", cash_paid="1550", request_key=str(uuid4()))

    def test_independent_opening_deducts_charge_and_advance_without_requiring_predecessor(self):
        self.data.update(principal="12000", advance_months=1, cash_paid="11750", document_charge="10", payout_basis="PROCEEDS")
        loan, _, _ = self.admit()
        snapshot = loan.disbursal_snapshot
        self.assertEqual(snapshot.advance_interest, 240)
        self.assertEqual(snapshot.deducted_fees, 10)
        snapshot.refresh_from_db()
        from apps.tenant_apps.loans.services.recorded_origination_evidence import validate_recorded_origination
        validate_recorded_origination(snapshot)
        self.assertIsNone(snapshot.evidence["recording"]["funding"]["actual_cash_paid"])
        self.assertFalse(hasattr(loan, "origin_renewal"))
        balance = collection_balance(loan, self.today)
        self.assertEqual((balance.principal_outstanding, balance.interest_outstanding, balance.fees_outstanding), (12000, 0, 0))
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(loan)
        self.assertIn("Unspecified", dict(payload.details)["Physical cash confirmation"])
        self.assertEqual(dict(payload.details)["Document charge deducted"], "INR 10")
        position = PawnLoanDocumentProjectionBuilder.loan_kfs_schedule(loan)
        self.assertEqual(dict(position.details)["Principal outstanding"], "INR 12,000")
        self.assertEqual(dict(position.details)["Interest outstanding"], "INR 0")
        self.assertEqual(dict(position.details)["Total due"], "INR 12,000")

    def test_initial_closed_record_does_not_invent_cash_or_customer_return(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="R-0008", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(loan.collateral_items.get().custody_state, "PAPER_CLOSED")
        self.assertFalse(hasattr(loan, "renewal_as_source"))
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.release_memo(loan.releases.get())
        self.assertIn("handover unspecified", dict(payload.details)["Entry source"])
        self.assertEqual(payload.sections[0].heading, "Collateral at paper closure")
        from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports
        issues = get_pawn_loan_reports(as_of_date=self.today).issues
        self.assertEqual([issue.severity for issue in issues if issue.code == "PAPER_CLOSURE_HANDOVER_UNCONFIRMED"], ["WARNING"])
        self.assertFalse(any(issue.code == "IMPOSSIBLE_CUSTODY" for issue in issues))
        from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
        report = pledge_book_report(workspace=self.tenant, actor=self.actor, license_id=self.series.license_id,
            series_id=self.series.pk, start=self.day, end=self.today, cutoff=self.today)
        entry = next(row for row in report.entries if row["loan_id"] == loan.pk)
        self.assertIn("customer handover unconfirmed", entry["closures"])
        self.assertIn("physical cash unconfirmed", entry["payments"])
        self.assertNotIn("Redemption", entry["closures"])

    def test_closed_receipt_correction_retains_unknown_cash_and_handover(self):
        self.data.update(final_state="CLOSED", events=[self.row(amount="200"),
            self.row(kind="CLOSE", date=self.today.isoformat(), amount="10000", number="R-0008",
                reference="Paper closing page", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        receipt = loan.loan_events.get(event_kind="REPAYMENT")
        data = dict(operation="REPLACE", target=receipt.pk, date=receipt.effective_date.isoformat(), amount="300",
            reference="Corrected receipt", before=None, reason="Receipt amount transcribed incorrectly", request_key=uuid4().hex,
            settlement=dict(cash_received="9900", cash_paid="0", interest_offset="0",
                reference="Checked paper closing amount", confirmed_unchanged=True))
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        review, token = preview_correction(loan.pk, actor=self.actor, data=data)
        self.assertEqual(review["blockers"], [])
        self.assertIn("cash method and customer handover unconfirmed", review["rows"][-1]["terms"])
        custody_count = loan.collateral_items.get().custody_history.count()
        record_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(collection_balance(loan, self.today).total_due, 0)
        self.assertEqual(loan.collateral_items.get().custody_state, "PAPER_CLOSED")
        self.assertEqual(loan.collateral_items.get().custody_history.count(), custody_count)
        from apps.tenant_apps.loans.web.recorded_corrections import CorrectionForm
        settlement = loan.loan_events.filter(event_kind="RELEASE_RECEIPT").order_by("-pk").first()
        form = CorrectionForm(receipts=[receipt], settlement=settlement)
        self.assertIn("physical cash remains unconfirmed", form.fields["settlement_cash_received"].label)

    def test_later_closure_preview_confirmation_exact_retry_and_changed_facts(self):
        loan, _, _ = self.admit()
        data = self.closure_data()
        review, token = preview_recorded_closure(loan_id=loan.pk, actor=self.actor, data=data)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "ACTIVE")
        self.assertFalse(loan.releases.exists())
        release, created = record_paper_closure(loan_id=loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertEqual(release.settlement_amount, 10200)
        again, created = record_paper_closure(loan_id=loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertFalse(created)
        self.assertEqual(again.pk, release.pk)
        with self.assertRaisesMessage(ValueError, "different closure facts"):
            record_paper_closure(loan_id=loan.pk, actor=self.actor, data=dict(data, reference="Different"), review_token=token, confirmed=True)

    def test_missing_paper_closing_number_gets_labelled_system_number(self):
        loan, _, _ = self.admit()
        data = dict(self.closure_data(), number="")
        review, token = preview_recorded_closure(loan_id=loan.pk, actor=self.actor, data=data)
        self.assertEqual(review["number_basis"], "SYSTEM_ASSIGNED")
        release, _ = record_paper_closure(loan_id=loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(release.release_number, review["closing_number"])
        paper = release.loan_event.payload["release"]["paper_closure"]
        self.assertIsNone(paper["original_release_number"])
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        value = dict(PawnLoanDocumentProjectionBuilder.release_memo(release).details)["Release number"]
        self.assertIn("system recording number", value)

    def test_initial_closure_without_number_retains_assignment_basis(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        self.assertEqual(loan.releases.get().loan_event.payload["release"]["paper_closure"]["number_basis"], "SYSTEM_ASSIGNED")

    def test_later_handover_does_not_rewrite_financial_closure(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        release = loan.releases.get()
        original = release.loan_event.payload_fingerprint
        financial_count = loan.loan_events.count()
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        data = dict(date=self.today.isoformat(), recipient="Borrower", reference="Checked closing book", request_key=uuid4().hex)
        _, token = preview_paper_handover(loan.pk, actor=self.actor, data=data)
        result, created = confirm_paper_handover(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(loan.loan_events.count(), financial_count)
        release.loan_event.refresh_from_db()
        self.assertEqual(release.loan_event.payload_fingerprint, original)
        self.assertIsNone(release.items.get().returned_at)
        from django.db import DatabaseError, transaction
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.LoanChangeLog.objects.filter(pk=result.pk).update(reason="Rewrite handover source")
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        details = dict(PawnLoanDocumentProjectionBuilder.release_memo(release).details)
        self.assertIn("Checked closing book", details["Later handover confirmation"])
        again, created = confirm_paper_handover(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertFalse(created)
        self.assertEqual(result.pk, again.pk)
        with self.assertRaisesMessage(ValueError, "different handover facts"):
            confirm_paper_handover(loan.pk, actor=self.actor, data=dict(data, recipient="Other"), review_token=token, confirmed=True)
        from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports
        self.assertFalse(any(issue.code == "PAPER_CLOSURE_HANDOVER_UNCONFIRMED" for issue in get_pawn_loan_reports(as_of_date=self.today).issues))

    def test_handover_rejects_stale_or_unauthorized_confirmation(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        data = dict(date=self.today.isoformat(), recipient="Borrower", reference="Checked closing book", request_key=uuid4().hex)
        with self.assertRaises(PermissionDenied):
            preview_paper_handover(loan.pk, actor=None, data=data)
        _, token = preview_paper_handover(loan.pk, actor=self.actor, data=data)
        with self.assertRaisesMessage(ValueError, "changed"):
            confirm_paper_handover(loan.pk, actor=self.actor, data=dict(data, recipient="Other"), review_token=token, confirmed=True)
        self.assertEqual(loan.collateral_items.get().custody_state, "PAPER_CLOSED")

    def test_ordinary_handover_review_preserves_previous_issued_release_copy(self):
        self.start_active_trial()
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="R-0008", closure_basis="PAPER_SETTLEMENT")])
        loan, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        release = loan.releases.get()
        pdf_path = reverse("workspace_loans:pawn_release_memo_pdf", kwargs=dict(workspace_slug=self.tenant.slug, release_pk=release.pk))
        previous = client.get(pdf_path)
        self.assertEqual(previous.status_code, 200)
        self.capture("handover-before.pdf", previous)
        original_id = previous["X-Rokkad-Document-Issue"]
        path = reverse("workspace_loans:pawn_loan_confirm_paper_handover", kwargs=dict(workspace_slug=self.tenant.slug, pk=loan.pk))
        data = dict(date=self.today.isoformat(), recipient="Borrower", reference="Checked signed handover", request_key=uuid4().hex)
        response = client.post(path, dict(data, action="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        self.capture("paper-handover.html", response)
        response = client.post(path, dict(data, action="confirm", confirmed="on", review_token=response.context["review_token"]))
        self.assertEqual(response.status_code, 302)
        current = client.get(pdf_path)
        self.assertEqual(current.status_code, 200)
        self.assertNotEqual(current["X-Rokkad-Document-Issue"], original_id)
        self.capture("handover-after.pdf", current)
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        self.assertEqual(LoanDocumentLayoutService.read_verified_artifact(m.LoanDocumentIssue.objects.get(pk=original_id)), previous.content)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")

    def test_closure_refuses_stale_review_and_unauthorized_actor(self):
        loan, _, _ = self.admit()
        data = self.closure_data()
        _, token = preview_recorded_closure(loan_id=loan.pk, actor=self.actor, data=data)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        record_pawn_loan_repayment(loan.pk, amount=Decimal("200"), request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            record_paper_closure(loan_id=loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        with self.assertRaises(PermissionDenied):
            preview_recorded_closure(loan_id=loan.pk, actor=None, data=data)
        self.assertFalse(loan.releases.exists())

    def test_later_actions_cannot_resolve_a_foreign_workspace_loan(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        loan, _, _ = self.admit()
        other = Company.objects.create(name="Other independent paper", schema_name="independent-paper-other",
            owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            with self.assertRaisesMessage(ValueError, "not found in the active workspace"):
                preview_recorded_closure(loan_id=loan.pk, actor=self.actor, data=self.closure_data())
            with self.assertRaisesMessage(ValueError, "not found in the active workspace"):
                preview_existing_paper_renewal(loan_id=loan.pk, actor=self.actor, data=self.renewal_data())
        self.assertFalse(loan.releases.exists())
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=loan).exists())

    def test_known_later_paper_renewal_supports_net_deductions_and_linkage(self):
        source, _, _ = self.admit()
        data = self.renewal_data()
        review, token = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data)
        self.assertEqual(Decimal(review["cash_paid"]), 1550)
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=source).exists())
        successor, created = record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        source.refresh_from_db()
        renewal = source.renewal_as_source
        self.assertEqual(source.state, "CLOSED")
        self.assertEqual(successor.principal_amount, 12000)
        self.assertEqual(renewal.successor_advance_interest, 240)
        self.assertEqual(renewal.successor_deducted_fees, 10)
        detail = renewal.settlement_event.payload["renewal"]
        self.assertEqual(Decimal(detail["successor_advance_interest"]), renewal.successor_advance_interest)
        self.assertEqual(Decimal(detail["successor_deducted_fees"]), renewal.successor_deducted_fees)
        self.assertEqual(renewal.interest_settled, 200)
        self.assertEqual(source.collateral_items.get().custody_state, "RENEWAL_TRANSFERRED")

        self.assertEqual(successor.collateral_items.get().renewed_from_id, source.collateral_items.get().pk)
        balance = collection_balance(successor, self.today)
        self.assertEqual((balance.principal_outstanding, balance.interest_outstanding, balance.fees_outstanding), (12000, 0, 0))
        again, created = record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertFalse(created)
        self.assertEqual(again.pk, successor.pk)
        with self.assertRaisesMessage(ValueError, "already has"):
            record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=dict(data, cash_paid="1560"), review_token=token, confirmed=True)

    def test_known_paper_renewal_refuses_changed_collateral_after_review(self):
        source, _, _ = self.admit()
        data = self.renewal_data()
        _, token = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data)
        item = source.collateral_items.get()
        item.net_weight = Decimal("8")
        item.save(update_fields=["net_weight"])
        with self.assertRaisesMessage(ValueError, "Collateral contract facts changed"):
            record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=source).exists())

    def test_net_renewal_rejects_inconsistent_cash_without_partial_successor(self):
        source, _, _ = self.admit()
        with self.assertRaisesMessage(ValueError, "does not match"):
            preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=dict(self.renewal_data(), cash_paid="1560"))
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=source).exists())
        self.assertFalse(source.loan_events.filter(event_kind="INTEREST_ACCRUAL").exists())

    def test_renew_now_uses_paper_source_balance_and_new_current_policy(self):
        source, _, _ = self.admit()
        result, preview = self.current_renewal(source)
        self.assertEqual(preview.source.interest_settled, 200)
        self.assertEqual(preview.net_cash_amount, -1550)
        self.assertEqual(result.successor_loan.policy_snapshot.basis, "ORIGINATION")
        self.assertEqual(result.renewal.interest_settled, 200)
        self.assertEqual(result.renewal.successor_advance_interest, 240)
        self.assertEqual(result.renewal.successor_deducted_fees, 10)
        from apps.tenant_apps.loans.services.pawn_renewals import reverse_pawn_loan_renewal
        reversal = reverse_pawn_loan_renewal(result.renewal.pk, reason="Incorrect current renewal", actor=self.actor)
        source.refresh_from_db()
        self.assertEqual(source.state, "ACTIVE")
        self.assertEqual(source.collateral_items.get().custody_state, "IN_VAULT")
        self.assertEqual(collection_balance(source, self.today).total_due, 10200)
        result.successor_loan.refresh_from_db()
        self.assertEqual(result.successor_loan.state, "CANCELLED")
        again = reverse_pawn_loan_renewal(result.renewal.pk, reason="Incorrect current renewal", actor=self.actor)
        self.assertEqual(again.reversal.pk, reversal.reversal.pk)

    def current_renewal(self, source):
        from apps.tenant_apps.loans.services import create_pawn_loan_economic_policy, create_pawn_metal_interest_rate_policy, create_pawn_loan_fee_policy
        from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan, renew_pawn_loan, RetainedCollateralInput
        from apps.tenant_apps.rates.models import Rate, RateSource
        create_pawn_loan_economic_policy(workspace=self.tenant, license=self.series.license,
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal("0.8"), advance_interest_periods=1, effective_from=self.today, actor=self.actor)
        create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=self.series.license, metal="GOLD",
            monthly_interest_rate=Decimal("2"), effective_from=self.today, actor=self.actor)
        create_pawn_loan_fee_policy(workspace=self.tenant, license=self.series.license, code="DOC", name="Document charge",
            calculation_type="FIXED", value=Decimal("10"), effective_from=self.today, actor=self.actor)
        Rate.objects.create(rate_source=RateSource.objects.create(name="Current market", location="Local"), buying_rate=5000, selling_rate=5100)
        values = dict(mode="TOP_UP_RENEW", principal_paid=Decimal("0"), top_up_amount=Decimal("2000"),
            successor_license_id=self.series.license_id, successor_series_id=self.series.pk, tenure_months=3,
            retained_collateral=(RetainedCollateralInput(source.collateral_items.get().pk, Decimal("12000")),))
        preview = preview_pawn_loan_renewal_plan(source.pk, **values)
        result = renew_pawn_loan(source.pk, **values, renewal_date=self.today, request_key="renew-now",
            expected_preview_fingerprint=preview.fingerprint, actor=self.actor)
        return result, preview

    def test_original_paper_correction_binds_native_successor_without_changing_approval(self):
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
        from apps.tenant_apps.loans.selectors.recorded_settlements import restated_renewal
        source, _, _ = self.admit()
        result, _ = self.current_renewal(source)
        successor = result.successor_loan
        approval = successor.approval_snapshots.get().fingerprint
        original_opening = result.renewal.opening_event.payload_fingerprint
        data = dict(date=self.day.isoformat(), principal="11000", rate="2", cash_paid="11000",
            reference="Corrected original page", reason="Original principal copied incorrectly", request_key=uuid4().hex,
            settlement=dict(cash_received="0", cash_paid="530", interest_offset="220",
                reference="Checked actual renewal cash", confirmed_unchanged=True))
        review, token = preview_contract_correction(source.pk, actor=self.actor, data=data)
        self.assertEqual(review["downstream"][1]["number"], successor.loan_number)
        record_contract_correction(source.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        successor.refresh_from_db()
        self.assertEqual(successor.principal_amount, 12000)
        self.assertEqual(successor.approval_snapshots.get().fingerprint, approval)
        result.renewal.opening_event.refresh_from_db()
        self.assertEqual(result.renewal.opening_event.payload_fingerprint, original_opening)
        corrected = restated_renewal(result.renewal)
        self.assertEqual(corrected.source_principal_amount, 11000)
        self.assertEqual(corrected.top_up_amount, 1000)
        self.assertEqual(Decimal(corrected.valuation_snapshot["cash_evidence"]["cash_paid"]), 530)
        self.assertEqual(collection_balance(source, self.today).total_due, 0)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_ordinary_http_later_closure_review_confirm_and_detail(self):
        self.start_active_trial()
        source, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_record_paper_closure", kwargs=dict(workspace_slug=self.tenant.slug, pk=source.pk))
        data = self.closure_data()
        response = client.post(path, dict(data, action="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Customer handover and physical cash method remain unconfirmed")
        self.capture("paper-closure.html", response)
        response = client.post(path, dict(data, action="confirm", confirmed="on", review_token=response.context["review_token"]))
        self.assertEqual(response.status_code, 302)
        source.refresh_from_db()
        self.assertEqual(source.state, "CLOSED")

    def capture(self, name, response):
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            (Path("/qa") / name).write_bytes(response.content)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_ordinary_http_known_paper_renewal_and_recorded_documents(self):
        self.start_active_trial()
        source, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_renew", kwargs=dict(workspace_slug=self.tenant.slug, pk=source.pk))
        data = self.renewal_data()
        response = client.post(path, dict(data, entry_mode="paper", action="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        self.assertContains(response, "1,550")
        self.capture("paper-renewal.html", response)
        response = client.post(path, dict(data, entry_mode="paper", action="confirm", confirmed="on", review_token=response.context["review_token"]))
        self.assertEqual(response.status_code, 302)
        successor = source.renewal_as_source.successor_loan
        self.assertContains(client.get(response.url), "Renew this loan")
        for route, name in (("pawn_loan_ticket_pdf", "paper-contract.pdf"), ("pawn_loan_kfs_schedule_pdf", "paper-position.pdf")):
            document_path = reverse("workspace_loans:" + route, kwargs=dict(workspace_slug=self.tenant.slug, pk=successor.pk))
            first = client.get(document_path)
            self.assertEqual(first.status_code, 200, first.content[:300])
            self.assertTrue(first.content.startswith(b"%PDF"))
            second = client.get(document_path)
            self.assertEqual(second.content, first.content)
            self.capture(name, first)
        previous_issue = first["X-Rokkad-Document-Issue"]
        previous_bytes = first.content
        from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
        facts = dict(through_date=self.today, confirmed_complete=False, source_reference="Another paper page is missing", request_key=uuid4().hex)
        _, token = preview_transaction_review(successor.pk, actor=self.actor, **facts)
        confirm_transaction_review(successor.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)
        updated = client.get(document_path)
        self.assertEqual(updated.status_code, 200)
        self.assertNotEqual(updated["X-Rokkad-Document-Issue"], previous_issue)
        self.assertNotEqual(updated.content, previous_bytes)
        from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
        self.assertEqual(LoanDocumentLayoutService.read_verified_artifact(m.LoanDocumentIssue.objects.get(pk=previous_issue)), previous_bytes)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_ordinary_independent_paper_entry_calculates_proceeds_and_retains_no_link(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_create", kwargs=dict(workspace_slug=self.tenant.slug))
        response = client.get(path + "?entry=paper")
        post = {key: value for key, value in self.data.items() if key != "events"}
        post.update(principal="12000", advance_months="1", document_charge="10", cash_paid="", payout_basis="PROCEEDS",
            entry_mode="paper", action="preview", intent_token=response.context["intent_token"],
            **{"events-TOTAL_FORMS":"0", "events-INITIAL_FORMS":"0"})
        response = client.post(path, post)
        self.assertFalse(response.context["form"].errors)
        self.assertTrue(response.context["review"])
        self.assertContains(response, "11,750")
        self.capture("paper-entry.html", response)
        post.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        response = client.post(path, post)
        self.assertEqual(response.status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number="P-0010", workspace=self.tenant)
        self.assertFalse(hasattr(loan, "origin_renewal"))
        self.assertEqual(loan.disbursal_snapshot.net_disbursed, 11750)

    def test_renewal_stale_review_and_earlier_date_do_not_overwrite_later_activity(self):
        source, _, _ = self.admit()
        data = self.renewal_data()
        _, token = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        record_pawn_loan_repayment(source.pk, amount=Decimal("200"), request_key="after-renewal-review", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            record_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        with self.assertRaisesMessage(ValueError, "Later activity is already recorded"):
            preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=dict(data, date=self.day.isoformat()))
        self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan=source).exists())

    def test_net_renewal_reduction_and_unchanged_principal(self):
        source, _, _ = self.admit()
        for principal, received in (("8000", "2370"), ("10000", "410")):
            with self.subTest(principal=principal):
                data = dict(self.renewal_data(), new_principal=principal, amount=received, cash_paid="0")
                review, _ = preview_existing_paper_renewal(loan_id=source.pk, actor=self.actor, data=data)
                self.assertEqual(Decimal(review["cash_received"]), Decimal(received))
                self.assertEqual(Decimal(review["new_principal"]), Decimal(principal))
