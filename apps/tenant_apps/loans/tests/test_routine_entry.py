"""Shared routine editor and reviewed, atomic current-photo attachment."""
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import recorded_entry_photos as media
from . import test_multi_item_paper as fixtures


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RoutineEntryTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.MultiItemPaperTests.setup_tenant.__func__)
    make_snapshot = fixtures.MultiItemPaperTests.make_snapshot
    prepare_history = fixtures.MultiItemPaperTests.prepare_history
    row = fixtures.MultiItemPaperTests.row
    configure = fixtures.MultiItemPaperTests.configure
    _entry_client = fixtures.MultiItemPaperTests._entry_client
    _direct_entry_facts = fixtures.MultiItemPaperTests._direct_entry_facts

    @classmethod
    def setUpTestData(cls):
        from .recovery_fixtures import lock_recovery_fixture_tables
        lock_recovery_fixture_tables()
        super().setUpTestData()

    def setUp(self):
        fixtures.MultiItemPaperTests.setUp(self)

    @classmethod
    def get_test_schema_name(cls):
        return "routine-entry-lo02"

    def photo(self, name="chain.png", contents=b"one"):
        return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n" + contents, content_type="image/png")

    def paper_facts(self, page):
        data = dict(self.data, routine_entry="on", entry_mode="paper", action="preview",
            intent_token=page.context["intent_token"], **{
                "collateral-TOTAL_FORMS": "2", "collateral-INITIAL_FORMS": "0",
                "events-TOTAL_FORMS": "1", "events-INITIAL_FORMS": "0"})
        for index, item in enumerate(data.pop("collateral")):
            for key, value in item.items():
                key = {"purity": "purity_percentage", "principal": "allocated_principal",
                       "rate": "interest_rate_override"}.get(key, key)
                data[f"collateral-{index}-{key}"] = value
        data.pop("events")
        return data

    def test_both_purposes_share_editor_search_items_camera_and_summary(self):
        client, path = self._entry_client()
        for purpose in ("direct", "paper"):
            page = client.get(path + "?entry=" + purpose)
            if purpose == "direct":
                self.assertNotContains(page, "data-paper-additional-details")
            self.assertTemplateUsed(page, "loans/pawn/routine_entry.html")
            self.assertContains(page, "data-routine-loan-editor")
            self.assertContains(page, 'id="loan-details"')
            self.assertContains(page, 'id="add-collateral"')
            self.assertContains(page, 'id="draft-loan-summary"')
            self.assertContains(page, "collateral-0-photograph")
            from django.urls import reverse
            self.assertContains(page, reverse("workspace_party:party_autocomplete", args=[self.tenant.slug]))
            self.assertContains(page, "+ Add customer")
            self.assertContains(page, "loans/collateral_camera.js", count=1)
        paper = client.get(path + "?entry=paper")
        self.assertEqual(paper.context["form"]["tenure"].value(), 12)
        self.assertEqual(str(paper.context["formset"][0]["interest_rate_override"].value()), "2.000000")
        self.assertContains(paper, 'name="tenure"', count=1)
        self.assertContains(paper, "Supplied from the selected series and original loan date")
        self.assertNotContains(paper, "data-rate-readiness-panel")

    def test_multiple_series_wait_for_selection_before_reporting_missing_setup(self):
        client, path = self._entry_client()
        m.LoanSeries.objects.create(workspace=self.tenant, license=self.series.license,
            code="SECOND", name="Second paper register")
        counts = (m.PawnLoan.objects.count(), m.LoanMonitoringPolicy.objects.count())
        page = client.get(path + "?entry=paper")
        self.assertIsNone(page.context["form"].terms)
        self.assertContains(page, "Choose the series and original date")
        self.assertNotContains(page, "data-paper-monitoring-attention")
        self.assertNotContains(page, "data-paper-calculation-attention")
        selected = client.get(path + f"?entry=paper&series={self.series.pk}")
        self.assertIsNotNone(selected.context["form"].terms)
        self.assertNotContains(selected, "data-paper-monitoring-attention")
        self.assertContains(selected, 'name="monitoring_method"')
        self.assertNotContains(selected, '<h2 class="h5">Standing agreement</h2>')
        self.assertContains(selected, 'data-paper-additional-details >')
        self.assertEqual(counts, (m.PawnLoan.objects.count(), m.LoanMonitoringPolicy.objects.count()))
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)

    def test_missing_second_item_rate_prompts_setup_and_refuses_review(self):
        from datetime import timedelta
        client, path = self._entry_client()
        page = client.get(path + "?entry=paper")
        data = self.paper_facts(page)
        m.PawnMetalInterestRatePolicy.objects.filter(workspace=self.tenant, metal="SILVER").update(
            effective_from=self.today + timedelta(days=1))
        result = client.post(path, data)
        self.assertContains(result, "data-paper-agreement-attention")
        self.assertTrue(result.context["paper_additional_open"])
        self.assertIsNone(result.context["review"])
        self.assertEqual(result.context["formset"][1]["allocated_principal"].value(), "4000")

    def license_evidence(self, **overrides):
        from datetime import timedelta
        values = dict(workspace=self.tenant, license=self.series.license,
            revision_number=self.series.license.revisions.count() + 1, kind="INITIAL",
            name="Retained licence", license_number="LICENSE-PAPER",
            issued_on=self.day - timedelta(days=30), expires_on=self.today + timedelta(days=30))
        values.update(overrides)
        return m.LoanLicenseRevision.objects.create(**values)

    def test_automatic_source_evidence_is_scoped_dated_and_unambiguous(self):
        from datetime import timedelta
        from types import SimpleNamespace
        from apps.tenant_apps.loans.services.paper_entry_terms import paper_source_license_revision as resolve
        values = dict(workspace=self.tenant, series=self.series, day=self.day)
        self.assertIsNone(resolve(**values))
        legacy = m.LoanLicense.objects.create(workspace=self.tenant, name="Unknown legacy validity",
            license_number="LEGACY-TEST", is_legacy_reference=True, is_active=False)
        legacy_series = m.LoanSeries.objects.create(workspace=self.tenant, license=legacy,
            code="LEGACY-TEST", name="Legacy register")
        self.license_evidence(license=legacy, kind="LEGACY_REFERENCE", issued_on=None, expires_on=None)
        self.assertIsNone(resolve(workspace=self.tenant, series=legacy_series, day=self.day))
        self.license_evidence(expires_on=self.day - timedelta(days=1))
        revision = self.license_evidence()
        self.assertEqual(resolve(**values), revision)
        with self.assertRaisesMessage(ValueError, "Workspace"):
            resolve(workspace=self.tenant, series=SimpleNamespace(workspace_id=-1), day=self.day)
        self.license_evidence()
        self.assertIsNone(resolve(**values))

    def test_routine_evidence_defaults_and_signed_retry_preserve_frozen_mapping(self):
        client, path = self._entry_client()
        revision = self.license_evidence()
        page = client.get(path + "?entry=paper")
        self.assertEqual(page.context["form"]["license_revision_id"].value(), revision.pk)
        self.assertFalse(page.context["paper_additional_open"])
        data = self.paper_facts(page)
        data.update(source_license_from_setup="on")
        reviewed = client.post(path, data)
        self.assertIsNotNone(reviewed.context["review"], reviewed.context["form"].errors)
        self.assertEqual(reviewed.context["form"].cleaned_data["license_revision_id"], revision)
        data.update(action="confirm", confirm_review="on", review_token=reviewed.context["review_token"],
            license_revision_id=str(revision.pk))
        self.assertEqual(client.post(path, data).status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number=data["number"])
        self.assertEqual(loan.license_revision_id, revision.pk)
        self.license_evidence()  # Later setup ambiguity cannot change a signed retry.
        self.assertEqual(client.post(path, data).status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.license_revision_id, revision.pk)
        self.assertEqual(m.PawnLoan.objects.filter(loan_number=data["number"]).count(), 1)

    def test_manual_and_older_submissions_keep_their_evidence_choice(self):
        client, path = self._entry_client()
        page = client.get(path + "?entry=paper")
        data = self.paper_facts(page)  # Existing submissions have no automatic marker.
        reviewed = client.post(path, data)
        self.assertIsNotNone(reviewed.context["review"])
        revision = self.license_evidence()
        confirmed = dict(data, action="confirm", confirm_review="on", review_token=reviewed.context["review_token"])
        self.assertEqual(client.post(path, confirmed).status_code, 302)
        self.assertIsNone(m.PawnLoan.objects.get(loan_number=data["number"]).license_revision_id)
        self.assertEqual(client.post(path, confirmed).status_code, 302)
        manual = dict(data, action="terms", source_license_from_setup="false", license_revision_id=str(revision.pk))
        response = client.post(path, manual)
        self.assertEqual(response.context["form"]["license_revision_id"].value(), str(revision.pk))
        self.assertTrue(response.context["paper_additional_open"])

    def test_automatic_evidence_refresh_leaves_actual_agreement_unchanged(self):
        from datetime import timedelta
        client, path = self._entry_client()
        revision = self.license_evidence(expires_on=self.day)
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(action="terms", source_license_from_setup="on", exceptions="on",
            exception_reason="Actual book agreement", tenure="3", license_revision_id=str(revision.pk))
        result = client.post(path, data)
        self.assertEqual(result.context["form"]["license_revision_id"].value(), str(revision.pk))
        data["date"] = (self.day + timedelta(days=1)).isoformat()
        result = client.post(path, data)
        self.assertEqual(result.context["form"]["license_revision_id"].value(), "")
        self.assertEqual(result.context["form"]["tenure"].value(), "3")
        self.assertFalse(result.context["form"].fields["tenure"].widget.attrs["readonly"])

    def test_switch_preserves_common_rows_deletion_and_number_without_financial_write(self):
        client, path = self._entry_client()
        original = client.get(path + "?entry=direct")
        data = self._direct_entry_facts(original)
        data.update(**{"collateral-TOTAL_FORMS": "2", "collateral-1-DELETE": "on"})
        count = m.PawnLoan.objects.count()
        paper = client.post(path, data)
        self.assertNotContains(paper, 'id="draft-errors"')
        back = paper.context["form"].data.dict()
        back.update(entry_mode="paper", entry_selection="direct", action="entry_change",
            entry_values=paper.context["entry_values"], number="P-X", source_reference="Paper book")
        direct = client.post(path, back)
        again = direct.context["form"].data.dict()
        again.update(entry_mode="direct", entry_selection="paper", action="entry_change",
            entry_values=direct.context["entry_values"])
        result = client.post(path, again)
        self.assertEqual(result.context["formset"].total_form_count(), 2)
        self.assertEqual(result.context["formset"][1]["DELETE"].value(), True)
        self.assertEqual(result.context["formset"][0]["description"].value(), "Retained chain")
        self.assertEqual(result.context["form"]["number"].value(), "P-X")
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_invalid_item_retains_entered_facts_and_does_not_allocate_number(self):
        client, path = self._entry_client()
        page = client.get(path + "?entry=paper")
        data = self.paper_facts(page)
        data["collateral-1-net_weight"] = "999"
        data["collateral-0-photograph"] = self.photo()
        count = m.PawnLoan.objects.count()
        response = client.post(path, data)
        self.assertContains(response, "Net weight cannot exceed gross weight")
        self.assertContains(response, "select any new photographs again")
        self.assertEqual(response.context["form"]["number"].value(), self.data["number"])
        self.assertEqual(response.context["formset"][0]["description"].value(), self.data["collateral"][0]["description"])
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_actual_tenure_exception_remains_available_in_shared_details(self):
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(exceptions="on", exception_reason="Original book says three months", tenure="3")
        response = client.post(path, data)
        self.assertIsNotNone(response.context["review"], response.context["form"].errors)
        self.assertEqual(response.context["form"]["tenure"].value(), "3")
        self.assertFalse(response.context["form"].fields["tenure"].widget.attrs["readonly"])

    def capture_step(self, name, response):
        import os
        from pathlib import Path
        if folder := os.environ.get("PAPER_STEP_QA_CAPTURE"):
            target = Path(folder)
            target.mkdir(parents=True, exist_ok=True)
            (target / (name + ".html")).write_bytes(response.content)

    def test_missing_standing_tenure_has_visible_actual_terms_recovery(self):
        client, path = self._entry_client()
        m.PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).update(default_tenure_months=None)
        page = client.get(path + "?entry=paper")
        self.capture_step("missing-tenure", page)
        self.assertIsNone(page.context["form"]["tenure"].value())
        self.assertTrue(page.context["paper_terms_open"])
        self.assertContains(page, "data-paper-tenure-missing")
        self.assertContains(page, "Enter actual agreed terms")
        self.assertContains(page, 'id="id_tenure_helptext"')
        self.assertContains(page, "If setup has no tenure for that date")
        data = self.paper_facts(page)
        data.pop("tenure", None)
        refused = client.post(path, data)
        self.assertContains(refused, "Tenure is missing. Update standing setup")
        self.assertIsNone(refused.context["review"])
        data.update(exceptions="on", exception_reason="Actual book agreement", tenure="3")
        reviewed = client.post(path, data)
        self.assertIsNotNone(reviewed.context["review"], reviewed.context["form"].errors)
        self.assertEqual(reviewed.context["form"]["tenure"].value(), "3")
        self.assertFalse(reviewed.context["form"].fields["tenure"].widget.attrs["readonly"])
        self.assertNotContains(reviewed, "data-paper-tenure-missing")

    def test_paper_review_is_focused_and_edit_preserves_facts_without_posting(self):
        client, path = self._entry_client()
        page = client.get(path + "?entry=paper")
        self.capture_step("entry", page)
        data = self.paper_facts(page)
        data.update(exceptions="on", exception_reason="Original tenure in book", tenure="3")
        before = (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count())
        reviewed = client.post(path, data)
        self.capture_step("review", reviewed)
        self.assertIsNotNone(reviewed.context["review"], reviewed.context["form"].errors)
        self.assertContains(reviewed, "data-paper-entry-details hidden")
        self.assertContains(reviewed, "data-paper-review>")
        self.assertContains(reviewed, "Edit details")
        self.assertContains(reviewed, "Record completed payout")
        edited = client.post(path, dict(data, action="edit", review_token=reviewed.context["review_token"], confirm_review="on"))
        self.capture_step("edit", edited)
        self.assertIsNone(edited.context["review"])
        self.assertNotContains(edited, "data-paper-entry-details hidden")
        self.assertNotContains(edited, 'name="review_token"')
        self.assertEqual(edited.context["form"]["tenure"].value(), "3")
        self.assertEqual(edited.context["form"]["number"].value(), data["number"])
        self.assertEqual(edited.context["formset"][1]["allocated_principal"].value(), "4000")
        self.assertEqual(before, (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count()))
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)
        data["tenure"] = "6"
        fresh = client.post(path, data)
        stale = client.post(path, dict(data, action="confirm", review_token=reviewed.context["review_token"], confirm_review="on"))
        self.assertIsNone(stale.context["review"])
        self.assertEqual(before, (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count()))
        self.assertEqual(client.post(path, dict(data, action="confirm", review_token=fresh.context["review_token"], confirm_review="on")).status_code, 302)
        self.assertEqual(m.PawnLoan.objects.get(loan_number=data["number"]).tenure_months, 6)

    def test_standard_terms_allow_confirmed_payout_details_and_exact_retry(self):
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(payout_basis="CASH", cash_paid="10000")
        review = client.post(path, data)
        self.assertIsNotNone(review.context["review"], review.context["form"].errors)
        self.assertFalse(review.context["form"].cleaned_data["exceptions"])
        data.update(action="confirm", confirm_review="on", review_token=review.context["review_token"])
        self.assertEqual(client.post(path, data).status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number=self.data["number"])
        self.assertEqual(str(loan.disbursal_snapshot.evidence["recording"]["funding"]["actual_cash_paid"]), "10000.00")
        self.assertEqual(client.post(path, data).status_code, 302)
        self.assertEqual(m.PawnLoan.objects.filter(loan_number=self.data["number"]).count(), 1)

    def test_inconsistent_standard_payout_is_rejected_without_erasing_the_amount(self):
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(payout_basis="CASH", cash_paid="9999")
        count = m.PawnLoan.objects.count()
        response = client.post(path, data)
        self.assertIsNone(response.context["review"])
        self.assertContains(response, "Original proceeds must equal principal")
        self.assertEqual(response.context["form"]["cash_paid"].value(), "9999")
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)

    def test_actual_terms_keep_current_monitoring_from_setup(self):
        from decimal import Decimal
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(exceptions="on", exception_reason="Actual supported book agreement", tenure="9",
            advance_months="0", document_charge="5", cash_paid="9995",
            monitoring_method="LATEST_APPRAISAL", monitoring_ltv="0.1", monitoring_reason="Posted override",
            **{"collateral-0-interest_rate_override": "1.5", "collateral-1-interest_rate_override": "3"})
        response = client.post(path, data)
        self.assertIsNotNone(response.context["review"], response.context["form"].errors)
        self.assertEqual(response.context["form"].cleaned_data["monitoring_method"], "CALCULATED_METAL_VALUE")
        self.assertEqual(response.context["form"].cleaned_data["monitoring_ltv"], Decimal("0.8"))
        data.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        self.assertEqual(client.post(path, data).status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number=self.data["number"])
        self.assertEqual(loan.tenure_months, 9)
        self.assertEqual(loan.disbursal_snapshot.monthly_interest, Decimal("210"))
        self.assertEqual(loan.policy_snapshot.maximum_ltv_ratio, Decimal("0.8"))

    def test_missing_monitoring_prompts_separately_without_requiring_agreement_exception(self):
        from apps.tenant_apps.loans.services.paper_entry_terms import paper_entry_terms
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))

        def no_current_monitoring(**kwargs):
            terms = paper_entry_terms(**kwargs)
            for name in ("monitoring_method", "monitoring_ltv", "monitoring_reason"):
                terms["values"].pop(name, None)
            return terms

        with patch("apps.tenant_apps.loans.services.paper_entry_terms.paper_entry_terms", side_effect=no_current_monitoring):
            response = client.post(path, data)
        self.assertContains(response, "data-paper-monitoring-attention")
        self.assertContains(response, "Current collateral valuation setup needs attention")
        self.assertContains(response, "#calculation-policy")
        self.assertNotContains(response, "Complete the current monitoring policy")
        self.assertIsNotNone(response.context["review"], response.context["form"].errors)
        self.assertFalse(response.context["form"].cleaned_data["exceptions"])

    def test_monitoring_setup_change_requires_fresh_exception_review(self):
        from decimal import Decimal
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data.update(exceptions="on", exception_reason="Original book tenure", tenure="3")
        response = client.post(path, data)
        self.assertIsNotNone(response.context["review"], response.context["form"].errors)
        create_pawn_economic_configuration(workspace=self.tenant, actor=self.actor,
            gold_monthly_interest_rate=Decimal("2"), silver_monthly_interest_rate=Decimal("4"),
            valuation_method="CALCULATED_METAL_VALUE", maximum_ltv_ratio=Decimal("0.7"),
            default_tenure_months=12, advance_interest_periods=0, effective_from=self.day)
        data.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        changed = client.post(path, data)
        self.assertTrue(changed.context["form"].errors)
        self.assertFalse(m.PawnLoan.objects.filter(loan_number=self.data["number"]).exists())
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 1)

    def test_paper_photo_preview_confirm_and_retry_match_surviving_item(self):
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        for key in list(data):
            if key.startswith("collateral-1-"):
                data[key.replace("collateral-1-", "collateral-2-")] = data.pop(key)
        data.update(**{"collateral-TOTAL_FORMS": "3", "collateral-1-DELETE": "on",
                       "collateral-2-photograph": self.photo()})
        count = m.PawnLoan.objects.count()
        preview = client.post(path, data)
        self.capture_step("photo-review", preview)
        self.assertIsNotNone(preview.context["review"], preview.context["form"].errors)
        self.assertContains(preview, "data-origination-agreement")
        self.assertContains(preview, "Record completed payout")
        self.assertEqual(preview.context["agreement"]["economics"]["monthly_interest"], 280)
        self.assertEqual(preview.context["review"]["entry_photos"][0]["item"], 2)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        data.update(action="confirm", confirm_review="on", review_token=preview.context["review_token"],
                    **{"collateral-2-photograph": self.photo()})
        confirmed = client.post(path, data)
        self.assertEqual(confirmed.status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number=self.data["number"])
        photo = m.PawnCollateralPhoto.objects.get(collateral_item__loan=loan)
        self.assertEqual(photo.collateral_item.description, "Silver anklets")
        self.assertEqual(photo.workflow_source, "POST_APPROVAL")
        self.assertEqual(timezone.localdate(photo.captured_at), self.today)
        detail = client.get(confirmed.url)
        self.assertContains(detail, "Current collateral evidence")
        self.assertNotContains(detail, "Post-approval evidence")
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["entry_photos"][0]["sha256"], photo.sha256)
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        from datetime import date
        import fitz
        with fitz.open(stream=PawnLoanDocumentService.render_loan_ticket(loan).pdf, filetype="pdf") as document:
            printed = " ".join(page.get_text() for page in document)
        self.assertIn("Recorded Paper Loan Contract", printed)
        self.assertIn(date.fromisoformat(self.data["date"]).strftime("%d/%m/%Y"), printed)
        self.assertEqual(loan.approval_snapshots.count(), 0)
        data["collateral-2-photograph"] = self.photo()
        self.assertEqual(client.post(path, data).status_code, 302)
        self.assertEqual(m.PawnCollateralPhoto.objects.filter(collateral_item__loan=loan).count(), 1)

    def test_photo_changes_or_missing_file_invalidate_financial_review(self):
        count = m.PawnLoan.objects.count()
        _, token = media.preview_recorded_entry(**self.args, data=self.data, photos=[(1, self.photo())])
        for photos in ([], [(1, self.photo(contents=b"changed"))], [(2, self.photo())]):
            with self.assertRaises(ValueError):
                media.admit_recorded_entry(**self.args, data=self.data, photos=photos, review_token=token, confirmed=True)
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_second_upload_failure_rolls_back_origin_and_compensates_first_file(self):
        photos = [(1, self.photo()), (2, self.photo("silver.png"))]
        _, token = media.preview_recorded_entry(**self.args, data=self.data, photos=photos)
        count = m.PawnLoan.objects.count()
        original = media._append_collateral_photo
        stored = []
        def fail_second(*args, **kwargs):
            if stored:
                raise ValueError("Storage unavailable")
            result = original(*args, **kwargs)
            stored.append(result.file)
            return result
        with patch.object(media, "_append_collateral_photo", side_effect=fail_second):
            with self.assertRaisesMessage(ValueError, "Storage unavailable"):
                media.admit_recorded_entry(**self.args, data=self.data, photos=photos, review_token=token, confirmed=True)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.assertFalse(stored[0].storage.exists(stored[0].name))
        photos = [(1, self.photo()), (2, self.photo("silver.png"))]
        loan, created = media.admit_recorded_entry(**self.args, data=self.data, photos=photos, review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertEqual(loan.collateral_items.count(), 2)
        self.assertEqual(m.PawnCollateralPhoto.objects.filter(collateral_item__loan=loan).count(), 2)

    def test_invalid_photo_is_a_field_error_with_no_financial_write(self):
        client, path = self._entry_client()
        data = self.paper_facts(client.get(path + "?entry=paper"))
        data["collateral-0-photograph"] = SimpleUploadedFile("bad.png", b"invalid", content_type="image/png")
        count = m.PawnLoan.objects.count()
        response = client.post(path, data)
        self.assertContains(response, "valid JPEG or PNG")
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_recorded_photos_and_review_metadata_survive_exact_recovery(self):
        import hashlib
        from . import test_pawn_recovery
        from apps.tenant_apps.loans.services import pawn_recovery
        _, token = media.preview_recorded_entry(**self.args, data=self.data, photos=[(1, self.photo())])
        loan, _ = media.admit_recorded_entry(**self.args, data=self.data, photos=[(1, self.photo())],
            review_token=token, confirmed=True)
        original = loan.disbursal_snapshot.evidence["recording"]["entry_photos"]
        photo = m.PawnCollateralPhoto.objects.get(collateral_item__loan=loan)
        content = pawn_recovery.export_archive(workspace=self.tenant, actor=self.actor)
        test_pawn_recovery.PawnRecoveryTests.empty(self)
        pawn_recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
            expected_sha256=hashlib.sha256(content).hexdigest(), commit=True)
        restored = m.PawnLoan.objects.get(pk=loan.pk)
        self.assertEqual(restored.disbursal_snapshot.evidence["recording"]["entry_photos"], original)
        restored_photo = m.PawnCollateralPhoto.objects.get(pk=photo.pk)
        self.assertEqual(restored_photo.sha256, original[0]["sha256"])
        self.assertEqual(restored_photo.file.read(), b"\x89PNG\r\n\x1a\none")
