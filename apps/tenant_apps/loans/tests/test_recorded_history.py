from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from . import test_recorded_origination as fixtures


class RecordedHistoryTests(fixtures.RecordedOriginationTests):
    @classmethod
    def get_test_schema_name(cls):
        return "recorded-history"

    def setUp(self):
        super().setUp()
        self.prepare_history()

    def prepare_history(self):
        seed = self.make_snapshot(save=False)
        self.series = seed.loan.series
        self.seq = m.LoanNumberSequence.objects.create(series=self.series, document_kind="PAWN_LOAN",
            prefix="P-", width=4, next_number=1, maximum_number=9999)
        m.LoanNumberSequence.objects.create(series=self.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="R-", width=4, next_number=1, maximum_number=9999)
        self.today = timezone.localdate()
        self.day = self.today - timedelta(days=8)
        self.data = dict(borrower_id=seed.loan.borrower_id, series_id=self.series.pk,
            product_version_id=seed.loan.product_version_id, number="P-0010", date=self.day.isoformat(),
            principal="10000", rate="2", tenure=3, advance_months=0, cash_paid="10000",
            source_reference="Book A / loan 10", description="Ring", metal="GOLD", quantity=1,
            gross_weight="10", net_weight="9", purity="90", monitoring_method="CALCULATED_METAL_VALUE",
            monitoring_ltv="0.8", monitoring_reason="Current metal coverage", complete_through=self.today.isoformat(),
            final_state="ACTIVE", confirmed_history=True, confirmed_rule=True, events=[])
        self.args = dict(workspace=self.tenant, actor=self.actor,
                         intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor))

    def row(self, kind="PAYMENT", amount="2000", **changes):
        value = dict(kind=kind, amount=amount, date=(self.day+timedelta(days=2)).isoformat(),
            reference="Receipt 10", number="", rate=None, tenure=None, recipient="")
        value.update(changes)
        return value

    def admit(self):
        review, token = preview_recorded_history(**self.args, data=self.data)
        loan, created = admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertTrue(created)
        return loan, review, token

    def test_preview_rolls_back_and_reviewed_receipt_uses_confirmed_split(self):
        self.data["events"] = [self.row()]
        count = m.PawnLoan.objects.count()
        review, token = preview_recorded_history(**self.args, data=self.data)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)
        self.assertEqual(Decimal(review["rows"][1]["interest"]), 200)
        self.assertEqual(Decimal(review["rows"][1]["principal"]), 1800)
        loan, _ = admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 8200)
        self.assertEqual(collection_balance(loan, self.today).interest_outstanding, 0)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 11)
        self.assertFalse(loan.approval_snapshots.exists())

    def test_multiple_receipts_in_month_do_not_restart_or_double_charge(self):
        self.data["events"] = [self.row(), self.row(amount="1000", reference="Receipt 11", date=self.today.isoformat())]
        loan, review, _ = self.admit()
        self.assertEqual(Decimal(review["rows"][2]["interest"]), 0)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 7200)
        from dateutil.relativedelta import relativedelta
        self.assertEqual(collection_balance(loan, self.day+relativedelta(months=1)).interest_outstanding, 144)

    def test_same_day_original_and_multiple_receipts_preserve_order(self):
        self.data.update(date=self.today.isoformat())
        self.data["events"] = [self.row(date=self.today.isoformat()),
            self.row(amount="1000", date=self.today.isoformat(), reference="second same-day receipt")]
        loan, _, _ = self.admit()
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 7200)

    def test_retry_and_changed_submission(self):
        loan, _, token = self.admit()
        same, created = admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertFalse(created)
        self.assertEqual(same.pk, loan.pk)
        self.data["source_reference"] = "different book"
        with self.assertRaisesMessage(ValueError, "different facts"):
            admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)


    def test_changed_review_and_counter_roll_back(self):
        _, token = preview_recorded_history(**self.args, data=self.data)
        m.LoanNumberSequence.objects.filter(pk=self.seq.pk).update(next_number=5)
        with self.assertRaisesMessage(ValueError, "Numbering"):
            admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 5)

    def test_closed_paper_history_has_actual_date_unknown_time_and_no_quote_requirement(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="R-0008", recipient="Paper recipient")])
        loan, _, _ = self.admit()
        self.assertEqual(loan.state, "CLOSED")
        release = loan.releases.get()
        self.assertEqual(release.effective_date.isoformat(), self.data["events"][0]["date"])
        self.assertIsNone(release.items.get().returned_at)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        memo = dict(PawnLoanDocumentProjectionBuilder.release_memo(release).details)
        self.assertIn("Recorded from paper", memo["Document status"])
        self.assertEqual(memo["Collected by"], "Paper recipient")

    def test_renewal_carries_principal_without_fake_cash_or_return(self):
        self.data["events"] = [self.row(kind="RENEW", number="P-0011", rate="1.5", tenure=3)]
        source, review, _ = self.admit()
        renewal = source.renewal_as_source
        successor = renewal.successor_loan
        self.assertEqual(source.state, "CLOSED")
        self.assertEqual(successor.state, "ACTIVE")
        self.assertEqual(renewal.successor_principal_amount, 8200)
        self.assertEqual(renewal.interest_settled, 200)
        self.assertEqual(renewal.principal_paid, 1800)
        self.assertEqual(renewal.top_up_amount, 0)
        self.assertFalse(successor.loan_events.filter(event_kind="DISBURSAL").exists())
        self.assertEqual(source.collateral_items.get().custody_state, "RENEWAL_TRANSFERRED")
        self.assertEqual(successor.collateral_items.get().custody_state, "IN_VAULT")
        self.assertEqual(collection_balance(successor, self.today).interest_outstanding, 123)
        self.assertEqual(len(review["loans"]), 2)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder, DocumentProjectionError
        memo = dict(PawnLoanDocumentProjectionBuilder.renewal_memo(renewal).details)
        self.assertIn("Recorded from paper", memo["Document status"])
        self.assertIn("Received INR 2,000", memo["Net cash handoff"])
        position = PawnLoanDocumentProjectionBuilder.loan_kfs_schedule(successor)
        self.assertIn("Recorded Paper", position.title)
        self.assertEqual(position.sections[-1].heading, "Charged anniversary interest")

    def test_renewal_then_receipt_and_full_return_admit_as_one_history(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="RENEW", number="P-0011", rate="1.5", tenure=3),
            self.row(kind="CLOSE", amount="8323", number="R-0009", recipient="Borrower", reference="Return receipt",
                     date=self.today.isoformat())])
        source, _, _ = self.admit()
        successor = source.renewal_as_source.successor_loan
        self.assertEqual(successor.state, "CLOSED")
        self.assertEqual(successor.releases.get().settlement_amount, 8323)

    def test_bad_final_row_does_not_leave_partial_loan_or_renewal(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="RENEW", number="P-0011", rate="1.5", tenure=3),
            self.row(kind="CLOSE", amount="1", number="R-0009", recipient="Borrower", reference="Return receipt")])
        before = m.PawnLoan.objects.count()
        with self.assertRaises(ValueError):
            preview_recorded_history(**self.args, data=self.data)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        self.assertFalse(m.PawnLoanRenewal.objects.exists())

    def renewal_row(self, **changes):
        return self.row(kind="RENEW", amount="200", number="P-0011", rate="1.5", tenure=3,
            **dict(dict(renewal_method="CARRY", new_principal="12000", cash_paid="2000",
                        interest_offset="0", custody="HELD"), **changes))

    def check_renewal(self, *, received, payout, offset, method="CARRY", custody="HELD", principal="12000"):
        self.data["events"] = [self.renewal_row(renewal_method=method, new_principal=principal,
            cash_paid=payout, interest_offset=offset, custody=custody)]
        self.data["events"][0].update(amount=received, recipient="Paper recipient" if custody != "HELD" else "")
        source, review, token = self.admit()
        renewal = source.renewal_as_source
        cash = renewal.valuation_snapshot["cash_evidence"]
        self.assertEqual(Decimal(cash["cash_received"]), Decimal(received))
        self.assertEqual(Decimal(cash["cash_paid"]), Decimal(payout))
        self.assertEqual(Decimal(cash["interest_offset"]), Decimal(offset))
        self.assertEqual(renewal.successor_principal_amount, Decimal(principal))
        self.assertEqual(cash, renewal.settlement_event.payload["renewal"]["cash_evidence"])
        self.assertEqual(cash, renewal.opening_event.payload["recording"]["cash_evidence"])
        self.assertEqual(renewal.opening_event.payload["recording"]["payout_already_occurred"], Decimal(payout) > 0)
        self.assertEqual(Decimal(review["rows"][1]["old_principal"]), 10000)
        self.assertEqual(Decimal(review["rows"][1]["cash_paid"]), Decimal(payout))
        self.assertFalse(renewal.successor_loan.loan_events.filter(event_kind="DISBURSAL").exists())
        self.assertEqual(collection_balance(source, self.today).total_due, 0)
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        exposure = get_pawn_loan_exposure(renewal.successor_loan_id, as_of_date=self.today)
        self.assertEqual(exposure.total_economic_exposure, Decimal(principal) * Decimal("1.015"))
        prior = get_pawn_loan_exposure(source.pk, as_of_date=self.day)
        self.assertEqual(prior.total_economic_exposure, 10200)
        from apps.tenant_apps.loans.selectors.reports import _event_amount
        self.assertEqual(_event_amount(renewal.settlement_event), Decimal(received) + Decimal(payout))
        self.assertEqual(_event_amount(renewal.opening_event), 0)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        memo = dict(PawnLoanDocumentProjectionBuilder.renewal_memo(renewal).details)
        self.assertIn("paid out", memo["Net cash handoff"])
        self.assertIn("old interest offset", memo["Net cash handoff"])
        self.assertIn("Gross new advance", memo)
        from apps.tenant_apps.loans.services.report_exports import build_pawn_loan_report_dataset
        from types import SimpleNamespace
        dataset = build_pawn_loan_report_dataset(SimpleNamespace(releases=(), renewals=(renewal,)), "releases_renewals")
        self.assertIn("old interest offset " + cash["interest_offset"], dataset.rows[0][-1])
        self.assertIn("paid " + cash["cash_paid"], dataset.rows[0][-1])
        same, created = admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertFalse(created)
        self.assertEqual(same.pk, source.pk)
        return source, renewal

    def test_topup_with_separate_cash_keeps_carried_principal_distinct(self):
        _, renewal = self.check_renewal(received="200", payout="2000", offset="0")
        self.assertEqual(renewal.principal_paid, 0)
        self.assertEqual(renewal.top_up_amount, 2000)

    def test_topup_with_interest_deducted_is_not_capitalized_or_fake_cash(self):
        _, renewal = self.check_renewal(received="0", payout="1800", offset="200")
        self.assertEqual(renewal.interest_settled, 200)
        self.assertEqual(renewal.successor_capitalized_principal_amount, 0)

    def test_part_interest_offset_and_part_cash(self):
        self.check_renewal(received="100", payout="1900", offset="100")

    def test_full_repayment_and_redraw_preserves_gross_cash_with_collateral_held(self):
        source, renewal = self.check_renewal(received="10200", payout="12000", offset="0", method="REPAY_REDRAW")
        self.assertEqual(renewal.principal_paid, 10000)
        self.assertEqual(renewal.top_up_amount, 12000)
        self.assertEqual(Decimal(renewal.valuation_snapshot["cash_evidence"]["principal_carried"]), 0)
        self.assertEqual(source.collateral_items.get().custody_state, "RENEWAL_TRANSFERRED")

    def test_return_and_repledge_is_independent_of_carry_funding(self):
        source, renewal = self.check_renewal(received="200", payout="2000", offset="0", custody="RETURNED_REPLEDGED")
        self.assertEqual(source.collateral_items.get().custody_state, "WITH_CUSTOMER")
        successor_item = renewal.successor_loan.collateral_items.get()
        self.assertEqual(successor_item.custody_state, "IN_VAULT")
        self.assertEqual(successor_item.renewed_from_id, source.collateral_items.get().pk)
        self.assertEqual(set(renewal.custody_events.values_list("from_state", "to_state")),
                         {("IN_VAULT", "WITH_CUSTOMER"), ("WITH_CUSTOMER", "IN_VAULT")})

    def test_full_repayment_redraw_and_actual_return_repledge(self):
        self.check_renewal(received="10200", payout="12000", offset="0", method="REPAY_REDRAW", custody="RETURNED_REPLEDGED")

    def test_explicit_reduction(self):
        _, renewal = self.check_renewal(received="2200", payout="0", offset="0", principal="8000")
        self.assertEqual(renewal.principal_paid, 2000)

    def test_explicit_unchanged_principal(self):
        self.check_renewal(received="200", payout="0", offset="0", principal="10000")

    def test_renewal_invalid_cash_and_missing_facts_roll_back_everything(self):
        for changes in (dict(cash_paid="1800"), dict(interest_offset="201"), dict(interest_offset="-1"),
                dict(new_principal="0"), dict(new_principal="12000.001"), dict(cash_paid=None),
                dict(custody="RETURNED_REPLEDGED"), dict(renewal_method=""), dict(interest_offset="NaN")):
            with self.subTest(changes=changes):
                self.data["events"] = [self.renewal_row(**changes)]
                with self.assertRaises(ValueError):
                    preview_recorded_history(**self.args, data=self.data)
                self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())
                self.assertFalse(m.PawnLoanRenewal.objects.exists())
                self.seq.refresh_from_db()
                self.assertEqual(self.seq.next_number, 1)

    def test_changed_cash_method_after_review_is_refused(self):
        self.data["events"] = [self.renewal_row()]
        _, token = preview_recorded_history(**self.args, data=self.data)
        self.data["events"][0].update(renewal_method="REPAY_REDRAW", amount="10200", cash_paid="12000")
        with self.assertRaisesMessage(ValueError, "changed"):
            admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)

    def test_topup_then_receipt_and_closure_reconciles(self):
        self.data.update(final_state="CLOSED", events=[self.renewal_row(),
            self.row(amount="2180", reference="Successor payment", date=self.today.isoformat()),
            self.row(kind="CLOSE", amount="10000", number="R-0009", recipient="Borrower",
                     reference="Successor return", date=self.today.isoformat())])
        source, _, _ = self.admit()
        successor = source.renewal_as_source.successor_loan
        self.assertEqual(successor.state, "CLOSED")
        self.assertEqual(successor.releases.get().settlement_amount, 10000)

    def test_two_renewals_preserve_each_contract_and_cash_history(self):
        second = self.renewal_row(renewal_method="REPAY_REDRAW", new_principal="9000", cash_paid="9000",
                                 custody="RETURNED_REPLEDGED")
        second.update(amount="12180", number="P-0012", reference="Second renewal", recipient="Borrower", date=self.today.isoformat())
        self.data["events"] = [self.renewal_row(), second]
        source, _, _ = self.admit()
        middle = source.renewal_as_source.successor_loan
        end = middle.renewal_as_source.successor_loan
        self.assertEqual(middle.state, "CLOSED")
        self.assertEqual(middle.renewal_as_source.interest_settled, 180)
        self.assertEqual(collection_balance(end, self.today).total_due, 9135)

    def test_renewal_pledge_book_preserves_cash_offset_and_physical_return(self):
        from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
        self.data["events"] = [self.renewal_row(cash_paid="1800", interest_offset="200", custody="RETURNED_REPLEDGED")]
        self.data["events"][0].update(amount="0", recipient="Actual recipient")
        source, _, _ = self.admit()
        report = pledge_book_report(workspace=self.tenant, actor=self.actor, license_id=source.license_id,
                                    start=self.day, end=self.today, cutoff=self.today)
        rows = {row["number"]: row for row in report.entries}
        self.assertIn("cash paid Rs 1,800", rows["P-0010"]["payments"])
        self.assertIn("offset Rs 200", rows["P-0010"]["payments"])
        self.assertIn("principal carried Rs 10,000", rows["P-0010"]["payments"])
        self.assertIn("Returned and repledged", str(rows["P-0010"]))
        self.assertIn("Actual recipient", str(rows["P-0010"]))
        self.assertNotIn("No fresh cash payout", str(rows["P-0011"]))
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        from apps.tenant_apps.loans.services.report_exports import build_pawn_loan_report_dataset, render_report_dataset
        from types import SimpleNamespace
        import fitz
        renewal = source.renewal_as_source
        pdf = PawnLoanDocumentService.render_renewal_memo(renewal).pdf
        document = fitz.open(stream=pdf, filetype="pdf")
        text = " ".join(" ".join(page.get_text().split()) for page in document)
        self.assertIn("paid out INR 1,800", text)
        self.assertIn("old interest offset INR 200", text)
        self.assertIn("Returned and repledged", text)
        dataset = build_pawn_loan_report_dataset(SimpleNamespace(releases=(), renewals=(renewal,)), "releases_renewals")
        export, _ = render_report_dataset(dataset, "pdf")
        report_pdf = fitz.open(stream=export, filetype="pdf")
        self.assertIn("interest offset", " ".join(" ".join(page.get_text().split()) for page in report_pdf))
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/renewal-memo.pdf").write_bytes(pdf)
            Path("/qa/renewal-report.pdf").write_bytes(export)
            for name, artifact in (("memo", document), ("report", report_pdf)):
                for index, page in enumerate(artifact):
                    page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(f"/qa/renewal-{name}-{index}.png")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_renewal_form_requires_explicit_cash_and_reviews_actual_return(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_create", kwargs={"workspace_slug": self.tenant.slug})
        intent = client.get(url + "?entry=paper").context["intent_token"]
        post = {key: value for key, value in self.data.items() if key != "events"}
        post.update(entry_mode="paper", intent_token=intent, action="preview",
                    **{"events-TOTAL_FORMS": "1", "events-INITIAL_FORMS": "0", "events-MAX_NUM_FORMS": "30"})
        row = self.renewal_row(cash_paid="1800", interest_offset="200", custody="RETURNED_REPLEDGED")
        row.update(amount="0", recipient="Paper recipient")
        post.update({"events-0-" + key: value if value is not None else "" for key, value in row.items()})
        incomplete = dict(post, **{"events-0-cash_paid": ""})
        response = client.post(url, incomplete)
        self.assertIsNone(response.context["review"])
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())
        response = client.post(url, post)
        self.assertContains(response, "Review before recording")
        self.assertContains(response, "Returned and repledged")
        self.assertContains(response, "1,800")
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/renewal-review.html").write_bytes(response.content)
        post.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response.url), "old interest offset 200")
        reports = reverse("workspace_loans:pawn_loan_reports", kwargs={"workspace_slug": self.tenant.slug})
        report = client.get(reports, {"section": "renewals"})
        self.assertContains(report, "Received 0")
        self.assertContains(report, "paid 1,800")

    def test_duplicate_number_across_new_intents_is_refused(self):
        self.admit()
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        self.data["source_reference"] = "Another claimed source"
        with self.assertRaisesMessage(ValueError, "already exists"):
            preview_recorded_history(**self.args, data=self.data)

    def test_same_source_cannot_be_reentered_with_another_number(self):
        self.admit()
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        self.data.update(number="P-0020", source_reference="  BOOK A / LOAN 10  ")
        with self.assertRaisesMessage(ValueError, "source reference is already recorded"):
            preview_recorded_history(**self.args, data=self.data)

    def test_original_number_reservation_is_case_normalized_and_native_counter_continues(self):
        from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number
        self.data["number"] = "p-0010"
        self.admit()
        allocation = allocate_pawn_loan_number(series=self.series, actor=self.actor)
        self.assertEqual(allocation.value, "P-0011")

    def test_archive_source_cannot_be_admitted_without_its_reviewed_link(self):
        from apps.tenant_apps.data_portability.tests.test_loan_archive import document
        from apps.tenant_apps.loans.services.archive import accept_evidence
        from apps.tenant_apps.loans.services.history_contract import digest
        value = document()
        value["facts"]["loan_number"] = "P-0010"
        accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=value,
                        expected_sha256=digest(value), confirmed=True)
        with self.assertRaisesMessage(ValueError, "historical evidence"):
            preview_recorded_history(**self.args, data=self.data)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())

    def test_existing_paper_origin_blocks_alternative_history_import_number(self):
        from apps.tenant_apps.loans.services.history_setup import preview_history_setup
        self.admit()
        with self.assertRaisesMessage(ValueError, "already belongs to admitted paper history"):
            preview_history_setup(workspace_id=self.tenant.pk, actor=self.actor, revision_id=None,
                series_id=self.series.pk, product_version_id=self.data["product_version_id"],
                source_namespace="491cf2e4-99eb-499c-b555-68f3a8d5caaa", source_loan_id="old-10",
                source_loan_number="p-0010", source_license_number="old", disbursed_on=self.day,
                tenure_months=3, calculation_contract_version="1", operational_grace_days=0)

    def test_pledge_book_shows_renewal_cash_separately_from_carried_principal(self):
        from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
        self.data["events"] = [self.row(kind="RENEW", number="P-0011", rate="1.5", tenure=3)]
        source, _, _ = self.admit()
        report = pledge_book_report(workspace=self.tenant, actor=self.actor, license_id=source.license_id,
                                    start=self.day, end=self.today, cutoff=self.today)
        rows = {row["number"]: row for row in report.entries}
        self.assertIn("Renewal receipt: Rs 2,000", rows["P-0010"]["payments"])
        self.assertIn("principal carried Rs 8,200", rows["P-0010"]["payments"])
        self.assertIn("Recorded paper renewal", rows["P-0011"]["source"])
        self.assertFalse(rows["P-0011"]["blockers"])

    def test_actor_workspace_and_changed_signed_facts_are_checked(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        stranger = get_user_model().objects.create_user(username="paper-stranger")
        with self.assertRaises(PermissionDenied):
            new_recording_intent(workspace=self.tenant, actor=stranger)
        other = Company.objects.create(name="Other paper", schema_name="recorded-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(PermissionDenied):
            preview_recorded_history(**self.args, data=self.data)
        _, token = preview_recorded_history(**self.args, data=self.data)
        self.data["number"] = "P-0012"
        with self.assertRaisesMessage(ValueError, "changed"):
            admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0012").exists())

    def test_foreign_borrower_cannot_enter_history(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        from apps.tenant_apps.party.models import Party
        from django.core.exceptions import ObjectDoesNotExist, ValidationError
        other = Company.objects.create(name="Other borrower", schema_name="recorded-borrower", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            party = Party.objects.create(display_name="Foreign borrower")
        self.data["borrower_id"] = party.pk
        with self.assertRaises((ObjectDoesNotExist, ValidationError, ValueError)):
            preview_recorded_history(**self.args, data=self.data)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())

    def test_advance_interest_is_not_collected_twice(self):
        self.data.update(advance_months=1, cash_paid="9800", events=[self.row(amount="1000")])
        loan, review, _ = self.admit()
        self.assertEqual(Decimal(review["rows"][1]["interest"]), 0)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 9000)

    def test_later_ordinary_repayment_and_full_release_use_agreed_interest(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        loan, _, _ = self.admit()
        receipt = record_pawn_loan_repayment(loan.pk, amount="2000", request_key="later-now", actor=self.actor)
        self.assertEqual(receipt.allocation.interest, 200)
        self.assertEqual(receipt.allocation.principal, 1800)
        release_pawn_loan_in_full(loan.pk, settlement_amount="8200", request_key="later-return", actor=self.actor)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CLOSED")

    def test_later_paper_receipt_uses_same_profile(self):
        from apps.tenant_apps.loans.services.paper_repayments import preview_paper_repayment, record_paper_repayment
        loan, _, _ = self.admit()
        values = dict(amount="2000", received_on=self.today, receipt_reference="Later paper receipt", request_key="later-paper", actor=self.actor)
        review = preview_paper_repayment(loan.pk, **values)
        result = record_paper_repayment(loan.pk, **values, review_token=review.review_token, confirmed_received=True)
        self.assertEqual(result.allocation.interest, 200)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 8200)

    def test_monitoring_maturity_and_asof_do_not_use_future_receipts(self):
        from dateutil.relativedelta import relativedelta
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        from apps.tenant_apps.loans.selectors.obligation_state import get_active_repayment_schedule_as_of, calculate_obligation_state_as_of
        self.data["events"] = [self.row()]
        loan, _, _ = self.admit()
        now = get_pawn_loan_exposure(loan.pk, as_of_date=self.today)
        self.assertEqual(now.total_economic_exposure, 8200)
        # Four charged months through the maturity anniversary; first month's 200 was paid.
        self.assertEqual(now.maturity_payoff, 8200 + 164 * 3)
        before_receipt = get_pawn_loan_exposure(loan.pk, as_of_date=self.day)
        self.assertEqual(before_receipt.total_economic_exposure, 10200)
        self.assertEqual(before_receipt.maturity_payoff, 10800)
        maturity = self.day + relativedelta(months=3)
        state = calculate_obligation_state_as_of(get_active_repayment_schedule_as_of(loan, maturity), maturity)
        self.assertEqual(state.due_now.total, 8692)
        self.assertEqual(state.overdue.total, 0)

    def test_receipt_on_anniversary_changes_only_next_month_and_month_end_clamps(self):
        from datetime import date
        from dateutil.relativedelta import relativedelta
        original = date(2026, 1, 31)
        self.data.update(date=original.isoformat(), events=[self.row(date="2026-02-28", amount="2400")])
        loan, review, _ = self.admit()
        self.assertEqual(Decimal(review["rows"][1]["interest"]), 400)
        self.assertEqual(collection_balance(loan, date(2026, 2, 28)).interest_outstanding, 0)
        self.assertEqual(collection_balance(loan, date(2026, 3, 31)).interest_outstanding, 160)

    def test_restricted_role_can_admit_complete_renewed_history_and_hides_other_workspace(self):
        import uuid
        from django.db import connection
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        other = Company.objects.create(name="Other runtime", schema_name="paper-runtime-other", owner=self.actor, creator=self.actor)
        self.data["events"] = [self.renewal_row(cash_paid="1800", interest_offset="200", custody="RETURNED_REPLEDGED")]
        self.data["events"][0].update(amount="0", recipient="Actual recipient")
        role = connection.ops.quote_name("paper_admit_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            loan, _, _ = self.admit()
            self.assertEqual(loan.renewal_as_source.successor_principal_amount, 12000)
            # Resolve this Workspace's deferred custody checks before deliberately
            # switching the test transaction to another RLS identity.
            connection.check_constraints()
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnLoan.objects.filter(pk=loan.pk).exists())
                self.assertFalse(m.PawnLoanEvent.objects.filter(loan_id=loan.pk).exists())
                self.assertFalse(m.PawnLoanRenewal.objects.filter(source_loan_id=loan.pk).exists())
                self.assertFalse(m.PawnCollateralCustodyEvent.objects.filter(renewal_id=loan.renewal_as_source.pk).exists())
                self.assertEqual(m.PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE"), 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_ordinary_interface_reviews_commits_and_opens_detail_without_prices(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_create", kwargs={"workspace_slug": self.tenant.slug})
        response = client.get(url + "?entry=paper")
        self.assertContains(response, "Record paper loan history")
        intent = response.context["intent_token"]
        post = {key: value for key, value in self.data.items() if key != "events"}
        post.update(entry_mode="paper", intent_token=intent, action="preview",
                    **{"events-TOTAL_FORMS": "1", "events-INITIAL_FORMS": "0", "events-MAX_NUM_FORMS": "30"})
        post.update({"events-0-" + key: value if value is not None else "" for key, value in self.row().items()})
        response = client.post(url, post)
        self.assertContains(response, "Review before recording")
        self.assertFalse(response.context["form"].errors)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number="P-0010").exists())
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/paper-review.html").write_bytes(response.content)
        post.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        detail = client.get(response.url)
        self.assertContains(detail, "Recorded from paper")
        self.assertContains(detail, "Collection amount today")
        self.assertContains(detail, "8,200")
        again = client.post(url, post)
        self.assertEqual(again.status_code, 302)
        self.assertEqual(m.PawnLoan.objects.filter(loan_number="P-0010").count(), 1)

    def test_missing_confirmation_duplicate_receipts_and_expired_review_are_refused(self):
        self.data["confirmed_rule"] = False
        with self.assertRaises(ValueError):
            preview_recorded_history(**self.args, data=self.data)
        self.data["confirmed_rule"] = True
        self.data["events"] = [self.row(), self.row()]
        with self.assertRaisesMessage(ValueError, "distinct"):
            preview_recorded_history(**self.args, data=self.data)
        self.data["events"] = []
        _, token = preview_recorded_history(**self.args, data=self.data)
        with patch("django.core.signing.time.time", return_value=9999999999), self.assertRaisesMessage(ValueError, "expired"):
            admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)

class RecordedHistoryConcurrencyTests(TransactionTestCase):
    make_snapshot = fixtures.RecordedOriginationTests.make_snapshot

    def setUp(self):
        import uuid
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context
        self.actor = get_user_model().objects.create_user(username="paper-race-" + uuid.uuid4().hex)
        self.tenant = Company.objects.create(name="Paper concurrency", schema_name="paper-" + uuid.uuid4().hex,
                                             owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            RecordedHistoryTests.prepare_history(self)
            _, token = preview_recorded_history(**self.args, data=self.data)
        self.commit = dict(**self.args, data=self.data, review_token=token, confirmed=True)

    def race(self, submissions):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from apps.tenancy.context import workspace_context
        ready = Barrier(2)
        def submit(values):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.tenant.pk):
                    loan, created = admit_recorded_history(**values)
                    return loan.pk, created
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(submit, submissions))

    def test_same_submission_posts_once_under_concurrency(self):
        from apps.tenancy.context import workspace_context
        results = self.race([self.commit, self.commit])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [False, True])
        with workspace_context(self.tenant.pk):
            self.assertEqual(m.PawnLoan.objects.filter(loan_number="P-0010").count(), 1)
            self.seq.refresh_from_db()
            self.assertEqual(self.seq.next_number, 11)

    def test_distinct_submissions_for_same_paper_loan_cannot_both_commit(self):
        from apps.tenancy.context import workspace_context
        with workspace_context(self.tenant.pk):
            intent = new_recording_intent(workspace=self.tenant, actor=self.actor)
            _, token = preview_recorded_history(workspace=self.tenant, actor=self.actor, data=self.data, intent_token=intent)
        other = {**self.commit, "intent_token": intent, "review_token": token}
        results = self.race([self.commit, other])
        self.assertEqual(sum(row is not None for row in results), 1)
