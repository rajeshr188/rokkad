from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release, restated_renewal
from . import test_recorded_origination as fixtures
from . import test_recorded_history as history
from . import test_recorded_corrections as receipt_tests


class RecordedSettlementCorrectionTests(fixtures.RecordedOriginationTests):
    prepare_history = history.RecordedHistoryTests.prepare_history
    row = history.RecordedHistoryTests.row
    admit = history.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "settlement-corrections"

    def setUp(self):
        super().setUp()
        self.prepare_history()
        self.day = self.today - relativedelta(months=2)
        self.later = self.day + relativedelta(months=1) + timedelta(days=2)
        self.series.license.issued_on = self.day
        self.series.license.save()
        self.data.update(date=self.day.isoformat(), events=[self.row(date=self.later.isoformat())])
        self.correction = dict(operation="ADD", target=None, date=(self.day+timedelta(days=2)).isoformat(),
            amount="2000", reference="Missing receipt", before=None, reason="Paper page omitted", request_key=uuid4().hex,
            settlement=dict(cash_received="127.28", cash_paid="3636", interest_offset="0", reference="Checked settlement page",
                            confirmed_unchanged=True))

    def renewal(self, *, method="CARRY", custody="HELD", offset=False, close=False, pay=False):
        row = self.row(kind="RENEW", date=self.today.isoformat(), number="P-0011", rate="1.5", tenure=3,
            reference="Renewal source", renewal_method=method, new_principal="10000", cash_paid="1600",
            interest_offset="0", custody=custody, recipient="Borrower" if custody != "HELD" else "")
        row["amount"] = "168"
        if method == "REPAY_REDRAW":
            row.update(amount="8568", cash_paid="10000")
            self.correction["settlement"].update(cash_received="6491.28", cash_paid="10000")
        if offset:
            row.update(amount="0", cash_paid="1432", interest_offset="168")
            self.correction["settlement"].update(cash_received="0", cash_paid="3508.72", interest_offset="127.28")
        self.data["events"].append(row)
        if pay:
            self.data["events"].append(self.row(date=self.today.isoformat(), amount="1000", reference="Successor receipt"))
        if close:
            self.data.update(final_state="CLOSED")
            self.data["events"].append(self.row(kind="CLOSE", date=self.today.isoformat(), amount="9150" if pay else "10150",
                                               number="R-0009", recipient="Borrower", reference="Successor closure"))
        self.loan, _, _ = self.admit()
        return self.loan.renewal_as_source

    def closure(self):
        self.data.update(final_state="CLOSED")
        self.data["events"].append(self.row(kind="CLOSE", date=self.today.isoformat(), amount="8568", number="R-0009",
                                           recipient="Borrower", reference="Closure source"))
        self.correction["settlement"].update(cash_received="6491.28", cash_paid="0")
        self.loan, _, _ = self.admit()
        return self.loan.releases.get()

    def correct(self):
        count = self.loan.loan_events.count()
        review, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertEqual(review["blockers"], [])
        self.assertTrue(record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True))
        self.assertFalse(record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True))
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "CLOSED")
        self.assertEqual(collection_balance(self.loan, self.today).total_due, 0)
        from apps.tenant_apps.loans.services.obligations import reconcile_loan_obligations
        self.assertEqual(reconcile_loan_obligations(self.loan).integrity_findings, ())
        return review

    def check_pdf(self, original, kind):
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        import fitz
        import os
        from pathlib import Path
        result = getattr(PawnLoanDocumentService, "render_" + kind + "_memo")(original)
        document = fitz.open(stream=result.pdf, filetype="pdf")
        text = " ".join(" ".join(page.get_text().split()) for page in document)
        self.assertIn("Historical settlement correction", text)
        self.assertIn("no new cash or collateral movement", text)
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path(f"/qa/corrected-{kind}.pdf").write_bytes(result.pdf)
            for index, page in enumerate(document):
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(f"/qa/corrected-{kind}-{index}.png")

    def test_closure_restates_cash_without_repeating_return_and_original_is_immutable(self):
        original = self.closure()
        before = deepcopy(original.loan_event.payload)
        custody = list(m.PawnCollateralCustodyEvent.objects.values_list("pk", flat=True))
        review = self.correct()
        original.refresh_from_db()
        self.assertEqual(original.settlement_amount, 8568)
        self.assertEqual(original.loan_event.payload, before)
        current = restated_release(original)
        self.assertEqual(current.settlement_amount, Decimal("6491.28"))
        self.assertEqual(current.principal_amount, 6364)
        self.assertEqual(current.interest_amount, Decimal("127.28"))
        self.assertEqual(list(m.PawnCollateralCustodyEvent.objects.values_list("pk", flat=True)), custody)
        self.assertEqual(current.pk, original.pk)
        self.assertEqual(review["rows"][-1]["terms"], "Full closure; original return date and recipient retained")
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        memo = dict(PawnLoanDocumentProjectionBuilder.release_memo(original).details)
        self.assertIn("Historical settlement correction", memo["Document status"])
        self.assertIn("6,491.28", memo["Total settlement"])
        self.check_pdf(original, "release")
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today).total_economic_exposure, 0)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day+timedelta(days=3)).total_economic_exposure, 8200)
        from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
        report = pledge_book_report(workspace=self.tenant, actor=self.actor, license_id=self.series.license_id,
            series_id=self.series.pk, start=self.day, end=self.today, cutoff=self.today)
        entry = next(row for row in report.entries if row['loan_id'] == self.loan.pk)
        self.assertIn("6,491.28", entry['payments'])
        self.assertIn("original handover retained", entry['closures'])
        self.assertNotIn("REVERSED", entry['closures'])

    def test_renewal_reconciles_new_advance_preserves_successor_and_future_collections(self):
        original = self.renewal(pay=True)
        successor = original.successor_loan
        events = list(successor.loan_events.values_list("pk", "payload_fingerprint"))
        review = self.correct()
        current = restated_renewal(original)
        self.assertEqual(current.source_principal_amount, 6364)
        self.assertEqual(current.top_up_amount, 3636)
        self.assertEqual(current.successor_principal_amount, 10000)
        self.assertEqual(list(successor.loan_events.values_list("pk", "payload_fingerprint")), events)
        self.assertEqual(collection_balance(successor, self.today).principal_outstanding, 9150)
        self.assertEqual(len(review["downstream"]), 2)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        self.assertEqual(record_pawn_loan_repayment(successor.pk, amount="100", request_key="next", actor=self.actor).allocation.principal, 100)
        original.refresh_from_db()
        self.assertEqual(original.top_up_amount, 1600)

    def test_redraw_with_returned_repledged_and_closed_successor(self):
        original = self.renewal(method="REPAY_REDRAW", custody="RETURNED_REPLEDGED", close=True, pay=True)
        count = m.PawnCollateralCustodyEvent.objects.count()
        successor_events = list(original.successor_loan.loan_events.values_list("pk", flat=True))
        self.correct()
        current = restated_renewal(original)
        self.assertEqual(current.principal_paid, 6364)
        self.assertEqual(current.top_up_amount, 10000)
        self.assertEqual(m.PawnCollateralCustodyEvent.objects.count(), count)
        self.assertEqual(list(original.successor_loan.loan_events.values_list("pk", flat=True)), successor_events)
        self.assertEqual(collection_balance(original.successor_loan, self.today).total_due, 0)

    def test_interest_offset_reconciles_without_capitalization(self):
        original = self.renewal(offset=True)
        self.correct()
        cash = restated_renewal(original).valuation_snapshot["cash_evidence"]
        self.assertEqual(Decimal(cash["interest_offset"]), Decimal("127.28"))
        self.assertEqual(Decimal(cash["cash_paid"]), Decimal("3508.72"))

    def test_wrong_actual_cash_fails_and_rolls_back_all_compensations(self):
        self.renewal()
        self.correction["settlement"].update(cash_received="168", cash_paid="1600")
        count = self.loan.loan_events.count()
        with self.assertRaisesMessage(ValueError, "actual received 168.00, required 127.28"):
            preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())

    def test_repeated_closure_correction_preserves_lineage_and_net_cash(self):
        original = self.closure()
        self.correct()
        missing = self.loan.loan_events.get(event_kind="REPAYMENT", payload__repayment__recording__receipt_reference="Missing receipt")
        self.correction.update(operation="REPLACE", target=missing.pk, amount="1000", request_key=uuid4().hex)
        self.correction["settlement"]["cash_received"] = "7531.68"
        self.correct()
        current = restated_release(original)
        self.assertEqual(current.loan_event.payload["history_correction"]["root_event_id"], original.loan_event_id)
        self.assertEqual(current.settlement_amount, Decimal("7531.68"))
        from apps.tenant_apps.loans.selectors.reports import _event_amount
        events = self.loan.loan_events.exclude(event_kind__in=("DISBURSAL", "INTEREST_ACCRUAL"))
        total = sum(((-1 if e.event_kind == "REVERSAL" else 1) * _event_amount(e) for e in events
                     if (e.payload.get("reversal") or {}).get("original_event_kind") != "INTEREST_ACCRUAL"), Decimal("0"))
        self.assertEqual(total, Decimal("10531.68"))

    def test_successor_activity_invalidates_review(self):
        original = self.renewal()
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        record_pawn_loan_repayment(original.successor_loan_id, amount="100", request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "Dependent"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())

    def test_failure_after_settlement_post_is_atomic(self):
        self.closure()
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        count = self.loan.loan_events.count()
        with patch("apps.tenant_apps.loans.services.recorded_settlement_corrections.terminate_active_repayment_schedule", side_effect=ValueError("Injected")):
            with self.assertRaisesMessage(ValueError, "Injected"):
                record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())

    def test_incorrect_custody_is_refused(self):
        original = self.renewal()
        item = self.loan.collateral_items.get()
        item.custody_state = "IN_VAULT"
        item.save(update_fields=["custody_state"])
        review, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertFalse(token)
        self.assertTrue(any("custody" in blocker for blocker in review["blockers"]))
        item.custody_state = "RENEWAL_TRANSFERRED"
        item.save(update_fields=["custody_state"])

    def test_renewal_documents_and_cash_reports_use_corrected_figures_once(self):
        original = self.renewal()
        self.correct()
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        from apps.tenant_apps.loans.selectors.recorded_settlements import opening_cash
        from apps.tenant_apps.loans.selectors.reports import _event_amount
        memo = dict(PawnLoanDocumentProjectionBuilder.renewal_memo(original).details)
        self.assertIn("Historical settlement correction", memo["Document status"])
        self.assertIn("3,636", memo["Gross new advance"])
        self.check_pdf(original, "renewal")
        cash, label = opening_cash(original.opening_event)
        self.assertEqual(Decimal(cash["gross_advance"]), 3636)
        self.assertIn("correction", label)
        events = self.loan.loan_events.filter(event_kind__in=("RENEWAL_SETTLEMENT", "REVERSAL"))
        net = sum(((-1 if e.event_kind == "REVERSAL" else 1) * _event_amount(e) for e in events
                   if e.event_kind == "RENEWAL_SETTLEMENT" or e.payload["reversal"]["original_event_kind"] == "RENEWAL_SETTLEMENT"), Decimal("0"))
        self.assertEqual(net, Decimal("3763.28"))
        from apps.tenant_apps.loans.selectors.reports import build_pawn_loan_reports
        from apps.tenant_apps.loans.services.report_exports import _releases_renewals
        report = build_pawn_loan_reports([self.loan], as_of_date=self.today)
        self.assertEqual(report.renewals[0].top_up_amount, 3636)
        self.assertIn("paid 3636", str(_releases_renewals(report).rows))
        self.assertFalse(report.issues)
        from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
        book = pledge_book_report(workspace=self.tenant, actor=self.actor, license_id=self.series.license_id,
            series_id=self.series.pk, start=self.day, end=self.today, cutoff=self.today)
        source = next(row for row in book.entries if row['loan_id'] == self.loan.pk)
        successor = next(row for row in book.entries if row['loan_id'] == original.successor_loan_id)
        self.assertEqual(source['payments'].count('Renewal receipt:'), 1)
        self.assertIn("3,636", source['payments'])
        self.assertIn("3,636", str(successor['warnings']))

    def test_restricted_role_can_correct_settlement_with_workspace_isolation(self):
        self.closure()
        receipt_tests.RecordedCorrectionTests.test_restricted_role_posts_restatements_and_hides_them_from_other_workspace(self)

    def test_void_receipt_in_closed_history_requires_larger_actual_settlement(self):
        original = self.closure()
        target = self.loan.loan_events.get(event_kind="REPAYMENT")
        self.correction.update(operation="VOID", target=target.pk, date=None, amount=None, reference="")
        self.correction["settlement"]["cash_received"] = "10600"
        self.correct()
        self.assertEqual(restated_release(original).settlement_amount, 10600)

    def test_corrected_receipt_can_precede_same_day_settlement(self):
        original = self.closure()
        self.correction.update(date=self.today.isoformat())
        self.correction["settlement"]["cash_received"] = "6568"
        self.correct()
        self.assertEqual(restated_release(original).settlement_amount, 6568)

    def test_settlement_confirmation_cannot_be_omitted_or_changed_after_review(self):
        self.closure()
        self.correction["settlement"]["confirmed_unchanged"] = False
        with self.assertRaisesMessage(ValueError, "Confirm"):
            preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.correction["settlement"]["confirmed_unchanged"] = True
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.correction["settlement"]["reference"] = "Changed evidence"
        with self.assertRaisesMessage(ValueError, "changed"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)

    def test_receipt_after_actual_closure_is_refused(self):
        self.data.update(final_state="CLOSED")
        self.data["events"].append(self.row(kind="CLOSE", date=(self.today-timedelta(days=1)).isoformat(), amount="8400",
            number="R-0009", recipient="Borrower", reference="Prior-day closure"))
        self.loan, _, _ = self.admit()
        self.correction["date"] = self.today.isoformat()
        with self.assertRaisesMessage(ValueError, "after the recorded settlement"):
            preview_correction(self.loan.pk, actor=self.actor, data=self.correction)

    def test_principal_reduction_renewal_keeps_actual_new_agreement(self):
        self.data["events"].append(self.row(kind="RENEW", date=self.today.isoformat(), amount="3568", number="P-0011", rate="1.5",
            tenure=3, reference="Reduction", renewal_method="CARRY", new_principal="5000", cash_paid="0", interest_offset="0", custody="HELD"))
        self.loan, _, _ = self.admit()
        self.correction["settlement"].update(cash_received="1491.28", cash_paid="0")
        self.correct()
        current = restated_renewal(self.loan.renewal_as_source)
        self.assertEqual(current.principal_paid, 1364)
        self.assertEqual(current.successor_principal_amount, 5000)

    def test_multiple_renewals_and_final_closure_are_locked_and_preserved(self):
        self.data["events"].extend([
            self.row(kind="RENEW", date=self.today.isoformat(), amount="168", number="P-0011", rate="1.5", tenure=3,
                reference="First renewal", renewal_method="CARRY", new_principal="10000", cash_paid="1600", interest_offset="0", custody="HELD"),
            self.row(kind="RENEW", date=self.today.isoformat(), amount="2150", number="P-0012", rate="1", tenure=3,
                reference="Second renewal", renewal_method="CARRY", new_principal="8000", cash_paid="0", interest_offset="0", custody="HELD"),
            self.row(kind="CLOSE", date=self.today.isoformat(), amount="8080", number="R-0009", recipient="Borrower", reference="Final return")])
        self.data["final_state"] = "CLOSED"
        self.loan, _, _ = self.admit()
        count = m.PawnLoanEvent.objects.exclude(loan=self.loan).count()
        review = self.correct()
        self.assertEqual(len(review["downstream"]), 3)
        self.assertEqual(m.PawnLoanEvent.objects.exclude(loan=self.loan).count(), count)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_http_settlement_review_confirmation_and_retry(self):
        self.renewal(close=True, pay=True)
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_correct_paper_history", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk})
        self.assertContains(client.get(url), "Actual cash received at renewal")
        post = {k: v if v is not None else "" for k, v in self.correction.items() if k != "settlement"}
        post.update({"settlement_" + k: v for k, v in self.correction["settlement"].items()})
        post["action"] = "preview"
        response = client.post(url, post)
        self.assertEqual(response.context["form"].errors, {})
        self.assertContains(response, "Settlement reconciliation")
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/settlement-review.html").write_bytes(response.content)
        post.update(action="confirm", confirmed=True, review_token=response.context["form"].data["review_token"])
        self.assertEqual(client.post(url, post).status_code, 302)
        self.assertEqual(client.post(url, post).status_code, 302)
        detail = client.get(reverse("workspace_loans:pawn_loan_detail", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk}))
        self.assertContains(detail, "Historical settlement correction")
        self.assertContains(detail, "3,636")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_release_detail_and_browser_show_current_settlement(self):
        original = self.closure()
        self.correct()
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        detail = client.get(reverse("workspace_loans:pawn_release_detail", kwargs={"workspace_slug": self.tenant.slug, "release_pk": original.pk}))
        self.assertContains(detail, "6,491.28")
        self.assertContains(detail, "Historical settlement correction")
        listing = client.get(reverse("workspace_loans:pawn_release_list", kwargs={"workspace_slug": self.tenant.slug}))
        self.assertContains(listing, "6,491.28 (corrected)")


class SettlementCorrectionConcurrencyTests(receipt_tests.CorrectionConcurrencyTests):
    def setUp(self):
        super().setUp()
        from apps.tenancy.context import workspace_context
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        with workspace_context(self.tenant.pk):
            release_pawn_loan_in_full(self.loan.pk, settlement_amount=collection_balance(self.loan, self.today).total_due,
                request_key="close-before-correction", actor=self.actor)
            self.submit["data"]["settlement"] = dict(cash_received="8200", cash_paid="0", interest_offset="0",
                reference="Closure book", confirmed_unchanged=True)
            _, self.submit["review_token"] = preview_correction(self.loan.pk, actor=self.actor, data=self.submit["data"])
