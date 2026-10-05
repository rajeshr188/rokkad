from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.test import override_settings
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
from apps.tenant_apps.loans.services.recorded_collections import collection_balance, collection_state
from apps.tenant_apps.loans.services.paper_repayments import preview_paper_repayment, record_paper_repayment
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MultiItemPaperTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row

    @classmethod
    def get_test_schema_name(cls):
        return "multi-item-paper"

    def setUp(self):
        self.prepare_history()
        first = {key: self.data[key] for key in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity", "principal", "rate")}
        first["principal"] = "6000"
        second = dict(first, description="Silver anklets", metal="SILVER", principal="4000", rate="4")
        self.data.update(collateral=[first, second], rate="2.800000")

    def admit(self):
        review, token = preview_recorded_history(**self.args, data=self.data)
        loan, created = admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertTrue(created)
        return loan, review

    def receipt(self, loan, split=None, amount="2000"):
        values = dict(amount=Decimal(amount), received_on=self.today, receipt_reference="Mixed receipt 1",
            request_key=uuid4().hex, actor=self.actor, item_principal_split=split)
        review = preview_paper_repayment(loan.pk, **values)
        return record_paper_repayment(loan.pk, **values, review_token=review.review_token, confirmed_received=True)

    def test_item_origination_preserves_actual_rates_and_monitoring_basis(self):
        loan, _ = self.admit()
        self.assertEqual(loan.collateral_items.count(), 2)
        self.assertEqual(loan.disbursal_snapshot.monthly_interest, Decimal("280"))
        self.assertEqual(collection_balance(loan, self.today).interest_outstanding, Decimal("280"))
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["collection_profile"], "recorded-anniversary/2")

    def test_explicit_split_changes_only_selected_item_next_anniversary(self):
        loan, _ = self.admit()
        items = list(loan.collateral_items.order_by("pk"))
        self.receipt(loan, {str(items[0].pk): "1720", str(items[1].pk): "0"})
        bases = get_pawn_principal_tranche_balances(loan)
        self.assertEqual([row.principal_outstanding for row in bases], [Decimal("4280"), Decimal("4000")])
        self.assertEqual(collection_balance(loan, self.day + relativedelta(months=1)).interest_outstanding, Decimal("245.60"))

    def test_missing_wrong_total_foreign_or_excessive_split_rejected_atomically(self):
        loan, _ = self.admit()
        first = loan.collateral_items.order_by("pk").first()
        for split in (None, {str(first.pk): "1700"}, {"999999": "1720"}):
            with self.assertRaises(ValueError):
                self.receipt(loan, split)
        self.assertEqual(loan.loan_events.filter(event_kind="REPAYMENT").count(), 0)

    def test_interest_only_receipt_needs_no_principal_split(self):
        loan, _ = self.admit()
        self.receipt(loan, amount="200")
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, Decimal("10000"))

    def test_anniversary_payment_changes_the_following_month_only(self):
        day = self.today - relativedelta(months=2)
        self.data["date"] = day.isoformat()
        loan, _ = self.admit()
        item = loan.collateral_items.order_by("pk").first()
        values = dict(amount=Decimal("2000"), received_on=day + relativedelta(months=1),
            receipt_reference="Anniversary receipt", request_key=uuid4().hex, actor=self.actor,
            item_principal_split={str(item.pk): "1440"})
        review = preview_paper_repayment(loan.pk, **values)
        record_paper_repayment(loan.pk, **values, review_token=review.review_token, confirmed_received=True)
        state = collection_state(loan, self.today)
        self.assertEqual([Decimal(row["interest"]) for row in state["months"]],
                         [Decimal("280"), Decimal("280"), Decimal("251.20")])

    def test_other_loan_item_and_zero_interest_only_foreign_split_are_rejected(self):
        loan, _ = self.admit()
        other = self.make_snapshot(save=False).loan.collateral_items.first()
        with self.assertRaisesMessage(ValueError, "outside this loan"):
            self.receipt(loan, {str(other.pk): "1720"})
        with self.assertRaisesMessage(ValueError, "outside this loan"):
            self.receipt(loan, {str(other.pk): "0"}, amount="200")

    def test_native_recovery_preserves_item_agreements_and_staff_receipt_evidence(self):
        import hashlib
        from .test_pawn_recovery import PawnRecoveryTests
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        loan, _ = self.admit()
        ids = list(loan.collateral_items.order_by("pk").values_list("pk", flat=True))
        receipt = self.receipt(loan, {str(ids[0]): "1720"})
        content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        digest = hashlib.sha256(content).hexdigest()
        original = recovery._read(content, digest)[0]
        PawnRecoveryTests.empty(self)
        recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
            expected_sha256=digest, commit=True)
        restored = m.PawnLoan.objects.get(pk=loan.pk)
        self.assertEqual(collection_balance(restored, self.today).principal_outstanding, Decimal("8280"))
        self.assertEqual(m.PawnLoanEvent.objects.get(pk=receipt.loan_event.pk).payload["repayment"]["recording"]["item_principal_split"], {str(ids[0]): "1720.00"})
        after = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        self.assertEqual(original["tables"], recovery._read(after, hashlib.sha256(after).hexdigest())[0]["tables"])

    def test_initial_receipt_uses_row_numbers_and_exact_retry(self):
        self.data["events"] = [dict(self.row(), item_principal_split={"1": "1720", "2": "0"})]
        loan, _ = self.admit()
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, Decimal("8280"))

    def test_full_paper_closure_handles_all_collateral(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10280", number="R-0008",
            closure_basis="PAPER_SETTLEMENT")])
        loan, _ = self.admit()
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(list(loan.collateral_items.values_list("custody_state", flat=True)), ["PAPER_CLOSED", "PAPER_CLOSED"])

    def test_item_rounding_and_advance_are_summed_without_blended_rate_recalculation(self):
        self.data["collateral"][0].update(principal="0.25", rate="2")
        self.data["collateral"][1].update(principal="0.25", rate="2")
        self.data.update(principal="0.50", rate="2", advance_months=1, cash_paid="0.48")
        loan, _ = self.admit()
        self.assertEqual(loan.disbursal_snapshot.advance_interest, Decimal("0.02"))

    def test_receipt_review_binds_staff_split_and_exact_retry(self):
        loan, _ = self.admit()
        ids = list(loan.collateral_items.order_by("pk").values_list("pk", flat=True))
        values = dict(amount=Decimal("2000"), received_on=self.today, receipt_reference="Split binding",
            request_key=uuid4().hex, actor=self.actor, item_principal_split={str(ids[0]): "1720"})
        review = preview_paper_repayment(loan.pk, **values)
        changed = dict(values, item_principal_split={str(ids[1]): "1720"})
        with self.assertRaisesMessage(ValueError, "changed"):
            record_paper_repayment(loan.pk, **changed, review_token=review.review_token, confirmed_received=True)
        first = record_paper_repayment(loan.pk, **values, review_token=review.review_token, confirmed_received=True)
        same = record_paper_repayment(loan.pk, **values, review_token=review.review_token, confirmed_received=True)
        self.assertEqual(first.loan_event.pk, same.loan_event.pk)

    def test_corrected_contract_preserves_old_snapshot_and_all_item_rates(self):
        from apps.tenant_apps.loans.services.recorded_contract_corrections import preview_contract_correction, record_contract_correction
        loan, _ = self.admit()
        old = loan.disbursal_snapshot
        ids = list(loan.collateral_items.order_by("pk").values_list("pk", flat=True))
        facts = dict(date=self.data["date"], principal="11000", rate="2.727273", cash_paid="11000",
            reference="Corrected original item book", reason="Original chain amount transcribed incorrectly", request_key=uuid4().hex,
            items=[dict(item_id=ids[0], principal="7000", rate="2"), dict(item_id=ids[1], principal="4000", rate="4")])
        _, token = preview_contract_correction(loan.pk, actor=self.actor, data=facts)
        record_contract_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertNotEqual(loan.disbursal_snapshot_id, old.pk)
        old.refresh_from_db()
        self.assertEqual(old.gross_principal, Decimal("10000"))
        self.assertEqual(loan.disbursal_snapshot.monthly_interest, Decimal("300"))
        self.assertEqual(collection_balance(loan, self.today).interest_outstanding, Decimal("300"))

    def test_receipt_correction_uses_explicit_replacement_and_retained_item_splits(self):
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        loan, _ = self.admit()
        ids = list(loan.collateral_items.order_by("pk").values_list("pk", flat=True))
        receipt = self.receipt(loan, {str(ids[0]): "1720"})
        facts = dict(operation="REPLACE", target=receipt.loan_event.pk, date=self.today.isoformat(), amount="3000",
            reference="Mixed receipt 1", before=None, reason="Correct receipt amount", request_key=uuid4().hex,
            item_principal_split={str(ids[0]): "2720"})
        _, token = preview_correction(loan.pk, actor=self.actor, data=facts)
        record_correction(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, Decimal("7280"))
        self.assertTrue(m.PawnLoanEvent.objects.filter(reversal_of=receipt.loan_event).exists())

    def test_closed_multi_item_settlement_correction_preserves_custody(self):
        from apps.tenant_apps.loans.services.recorded_settlement_facts import preview_settlement_facts, record_settlement_facts
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10280", number="R-0008", closure_basis="PAPER_SETTLEMENT")])
        loan, _ = self.admit()
        release = loan.releases.get()
        custody = list(release.custody_events.values_list("pk", flat=True))
        facts = dict(date=self.data["events"][0]["date"], amount="10280", recipient="", reference="Closure checked",
            reason="Correct closure reference", request_key=uuid4().hex)
        _, token = preview_settlement_facts(loan.pk, actor=self.actor, data=facts)
        record_settlement_facts(loan.pk, actor=self.actor, data=facts, review_token=token, confirmed=True)
        self.assertEqual(list(release.custody_events.values_list("pk", flat=True)), custody)
        self.assertEqual(collection_balance(loan, self.today).total_due, Decimal("0"))

    def test_current_repayment_retains_native_highest_rate_first_rule(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        loan, _ = self.admit()
        result = record_pawn_loan_repayment(loan.pk, amount=Decimal("2000"), request_key=uuid4().hex, actor=self.actor)
        self.assertEqual(result.loan_event.payload["repayment"]["item_principal_allocation_order"], "HIGHEST_MONTHLY_RATE_FIRST")
        bases = get_pawn_principal_tranche_balances(loan)
        self.assertEqual([row.principal_outstanding for row in bases], [Decimal("6000"), Decimal("2280")])

    def test_ordinary_renew_now_accepts_multi_item_recorded_source_and_current_approval(self):
        from apps.tenant_apps.loans.services.pawn_renewals import preview_pawn_loan_renewal_plan, renew_pawn_loan, RetainedCollateralInput
        from apps.tenant_apps.rates.models import Rate, RateSource
        loan, _ = self.admit()
        self.configure(license=self.series.license)
        source = RateSource.objects.create(name="Current metal quotes", location="Local")
        Rate.objects.create(rate_source=source, buying_rate=5000, selling_rate=5100)
        Rate.objects.create(rate_source=source, metal=Rate.Metal.SILVER, buying_rate=5000, selling_rate=5100)
        ids = list(loan.collateral_items.order_by("pk").values_list("pk", flat=True))
        values = dict(mode="TOP_UP_RENEW", principal_paid=Decimal("0"), top_up_amount=Decimal("2000"),
            successor_license_id=self.series.license_id, successor_series_id=self.series.pk, tenure_months=12,
            retained_collateral=(RetainedCollateralInput(ids[0], Decimal("8000")), RetainedCollateralInput(ids[1], Decimal("4000"))))
        preview = preview_pawn_loan_renewal_plan(loan.pk, **values)
        result = renew_pawn_loan(loan.pk, **values, renewal_date=self.today, request_key="mixed-renew-now",
            expected_preview_fingerprint=preview.fingerprint, actor=self.actor)
        self.assertEqual(preview.source.interest_settled, Decimal("280"))
        self.assertEqual(result.successor_loan.collateral_items.count(), 2)
        self.assertEqual(result.successor_loan.policy_snapshot.basis, "ORIGINATION")
        self.assertTrue(result.successor_loan.approval_snapshots.exists())

    def configure(self, **changes):
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration
        return create_pawn_economic_configuration(workspace=self.tenant, actor=self.actor,
            gold_monthly_interest_rate=Decimal("2"), silver_monthly_interest_rate=Decimal("4"),
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal("0.8"),
            default_tenure_months=12, advance_interest_periods=0, effective_from=self.day, **changes)

    def test_default_precedence_inheritance_and_old_contracts_are_unchanged(self):
        from apps.tenant_apps.loans.services.entry_purpose import default_entry_purpose
        loan, _ = self.admit()
        self.configure(default_entry_purpose="PAPER")
        self.assertEqual(default_entry_purpose(workspace=self.tenant, series_id=self.series.pk), "PAPER")
        self.configure(license=self.series.license, default_entry_purpose="DIRECT")
        self.assertEqual(default_entry_purpose(workspace=self.tenant, series_id=self.series.pk), "DIRECT")
        self.configure(license=self.series.license, series=self.series, default_entry_purpose="PAPER")
        self.assertEqual(default_entry_purpose(workspace=self.tenant, series_id=self.series.pk), "PAPER")
        self.configure(license=self.series.license, series=self.series, default_entry_purpose="INHERIT")
        self.assertEqual(default_entry_purpose(workspace=self.tenant, series_id=self.series.pk), "DIRECT")
        loan.refresh_from_db()
        self.assertEqual(loan.tenure_months, 3)

    def test_shared_form_dated_defaults_add_rows_without_javascript_and_explicit_direct_override(self):
        from django.urls import reverse
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        self.configure(default_entry_purpose="PAPER")
        path = reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug])
        response = client.get(path)
        self.assertContains(response, "collateral-0-allocated_principal")
        self.assertContains(response, "Create and pay now")
        self.assertContains(client.get(path + "?entry=direct"), "submission_token")
        form = dict(self.data, routine_entry="on", entry_mode="paper", intent_token=response.context["intent_token"],
            action="add_collateral", **{"collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "0",
            "collateral-MIN_NUM_FORMS": "1", "collateral-MAX_NUM_FORMS": "100", "events-TOTAL_FORMS": "1",
            "events-INITIAL_FORMS": "0", "collateral-0-description": "Chain", "collateral-0-metal": "GOLD",
            "collateral-0-quantity": "1", "collateral-0-gross_weight": "10", "collateral-0-net_weight": "9",
            "collateral-0-purity_percentage": "90", "collateral-0-allocated_principal": "6000"})
        form.pop("collateral")
        form.pop("events")
        added = client.post(path, form)
        self.assertContains(added, "collateral-1-allocated_principal")
        self.assertEqual(m.PawnLoan.objects.filter(loan_number="P-0010").count(), 0)
        form.update(action="preview", **{"collateral-TOTAL_FORMS": "2", "collateral-1-description": "Anklets",
            "collateral-1-metal": "SILVER", "collateral-1-quantity": "2", "collateral-1-gross_weight": "100",
            "collateral-1-net_weight": "90", "collateral-1-purity_percentage": "90", "collateral-1-allocated_principal": "4000"})
        result = client.post(path, form)
        self.assertIsNotNone(result.context["review"], result.context["form"].errors)
        self.assertEqual(result.context["form"].cleaned_data["principal"], Decimal("10000"))
        form.update(action="confirm", confirm_review="on", review_token=result.context["review_token"])
        posted = client.post(path, form)
        self.assertEqual(posted.status_code, 302)
        self.assertEqual(m.PawnLoan.objects.get(loan_number="P-0010").collateral_items.count(), 2)

    def _entry_client(self):
        from django.urls import reverse
        self.configure()
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        return client, reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug])

    def _direct_entry_facts(self, response):
        return dict(entry_mode="direct", entry_selection="paper", action="entry_change",
            submission_token=response.context["submission_token"], borrower=str(self.data["borrower_id"]),
            series=str(self.series.pk), product_version=str(self.data["product_version_id"]),
            loan_date=str(self.day), tenure_months="9", **{
                "collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "0",
                "collateral-0-description": "Retained chain", "collateral-0-metal": "GOLD",
                "collateral-0-quantity": "2", "collateral-0-gross_weight": "10",
                "collateral-0-net_weight": "9", "collateral-0-purity_percentage": "90",
                "collateral-0-allocated_principal": "6000", "collateral-0-latest_appraised_value": "777",
                "collateral-0-interest_rate_override": "1.9", "collateral-0-interest_override_reason": "Agreed override"})

    def test_entry_purpose_roundtrip_preserves_facts_and_native_details_without_posting(self):
        client, path = self._entry_client()
        original = client.get(path + "?entry=direct")
        count = m.PawnLoan.objects.count()
        data = self._direct_entry_facts(original)
        paper = client.post(path, data)
        self.assertEqual(paper.status_code, 200)
        self.assertEqual(paper.context["entry_purpose"], "paper")
        self.assertEqual(str(paper.context["form"]["borrower_id"].value()), str(self.data["borrower_id"]))
        self.assertEqual(str(paper.context["form"]["date"].value()), str(self.day))
        self.assertEqual(paper.context["formset"][0]["allocated_principal"].value(), "6000")
        self.assertNotContains(paper, "Use the standing entry default for series")
        self.assertNotContains(paper, 'id="entry-default-series"')
        back = paper.context["form"].data.dict()
        back.update(entry_mode="paper", entry_selection="direct", action="entry_change",
            entry_values=paper.context["entry_values"], intent_token=paper.context["intent_token"])
        direct = client.post(path, back)
        self.assertEqual(direct.context["entry_purpose"], "direct")
        self.assertEqual(direct.context["form"]["tenure_months"].value(), "9")
        self.assertEqual(direct.context["formset"][0]["latest_appraised_value"].value(), "777")
        self.assertEqual(direct.context["formset"][0]["interest_rate_override"].value(), "1.9")
        self.assertEqual(direct.context["submission_token"], original.context["submission_token"])
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_ordinary_series_applies_default_but_explicit_override_stays_direct(self):
        client, path = self._entry_client()
        self.configure(license=self.series.license, series=self.series, default_entry_purpose="PAPER")
        original = client.get(path + "?entry=direct")
        data = self._direct_entry_facts(original)
        data["entry_selection"] = "auto"
        self.assertEqual(client.post(path, data).context["entry_purpose"], "paper")
        data["entry_selection"] = "direct"
        self.assertEqual(client.post(path, data).context["entry_purpose"], "direct")

    def test_entry_change_refuses_foreign_series_and_does_not_save(self):
        client, path = self._entry_client()
        original = client.get(path + "?entry=direct")
        data = self._direct_entry_facts(original)
        data.update(series="999999", entry_selection="auto")
        count = m.PawnLoan.objects.count()
        response = client.post(path, data)
        self.assertContains(response, "Select a series in this Workspace")
        self.assertEqual(response.context["entry_purpose"], "direct")
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_paper_fields_and_receipt_rows_survive_purpose_roundtrip(self):
        client, path = self._entry_client()
        original = client.get(path + "?entry=direct")
        paper = client.post(path, self._direct_entry_facts(original))
        data = paper.context["form"].data.dict()
        data.update(entry_mode="paper", entry_selection="direct", action="entry_change",
            entry_values=paper.context["entry_values"], intent_token=paper.context["intent_token"],
            number="P-X", source_reference="Actual paper book", exceptions="on", exception_reason="Actual agreement",
            document_charge="24", **{"events-0-kind": "PAYMENT", "events-0-date": str(self.day),
                "events-0-amount": "200", "events-0-reference": "Book receipt"})
        direct = client.post(path, data)
        back = direct.context["form"].data.dict()
        back.update(entry_mode="direct", entry_selection="paper", action="entry_change", entry_values=direct.context["entry_values"])
        result = client.post(path, back)
        self.assertEqual(result.context["form"]["source_reference"].value(), "Actual paper book")
        self.assertEqual(result.context["form"]["document_charge"].value(), "24")
        self.assertEqual(result.context["rows"][0]["reference"].value(), "Book receipt")
