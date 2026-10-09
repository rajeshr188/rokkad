"""New lending eligibility is distinct from existing servicing and paper evidence."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.forms import PawnDraftForm
from apps.tenant_apps.loans.selectors.series import running_series, series_new_loan_status
from apps.tenant_apps.loans.services.license_series import set_series_active, LicenseSeriesError
from apps.tenant_apps.loans.services.number_allocation import (
    allocate_pawn_loan_number, allocate_release_number, SequenceExhaustedError,
)
from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
from . import test_origination_review as direct, test_routine_entry as paper


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SeriesAvailabilityTests(WorkspaceTestCase):
    setup_tenant = classmethod(direct.OriginationReviewTests.setup_tenant.__func__)
    _configured_setup = direct.OriginationReviewTests._configured_setup
    _payload = direct.OriginationReviewTests._payload
    start_review = direct.OriginationReviewTests.start_review
    confirm = direct.OriginationReviewTests.confirm

    @classmethod
    def setUpTestData(cls):
        from .recovery_fixtures import lock_recovery_fixture_tables
        lock_recovery_fixture_tables()
        super().setUpTestData()

    def setUp(self):
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        from apps.tenant_apps.loans.services.loan_workflow import set_loan_workflow
        super().setUp()
        for mock in (patch("django.utils.timezone.localdate", return_value=date(2026, 7, 18)),
                     patch("django.templatetags.static.StaticNode.handle_simple", side_effect=lambda path: f"/static/{path}")):
            mock.start(); self.addCleanup(mock.stop)
        self.owner = self.actor = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client(); self.client.force_login(self.owner)
        self.party = Party.objects.create(display_name="Series Borrower")
        self.product_version = _seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
        self.license, self.series = self._configured_setup()
        set_loan_workflow(actor=self.owner, mode="SIMPLE")

    @classmethod
    def get_test_schema_name(cls):
        return "series-availability"

    def test_picker_filters_unavailable_series_and_licences_but_saved_drafts_keep_identity(self):
        unavailable = []
        for condition in ("stopped", "exhausted", "missing", "sequence_inactive", "expired", "future", "licence_inactive"):
            license, series = self._configured_setup()
            unavailable.append(series.pk)
            sequence = series.number_sequences.get(document_kind="PAWN_LOAN")
            if condition == "stopped":
                set_series_active(series, is_active=False, actor=self.owner)
            elif condition == "exhausted":
                m.LoanNumberSequence.objects.filter(pk=sequence.pk).update(next_number=sequence.maximum_number + 1)
            elif condition == "missing":
                sequence.delete()
            elif condition == "sequence_inactive":
                m.LoanNumberSequence.objects.filter(pk=sequence.pk).update(is_active=False)
            elif condition == "expired":
                m.LoanLicense.objects.filter(pk=license.pk).update(expires_on=date(2026, 7, 17))
            elif condition == "future":
                m.LoanLicense.objects.filter(pk=license.pk).update(issued_on=date(2026, 7, 19))
            else:
                m.LoanLicense.objects.filter(pk=license.pk).update(is_active=False)
        self.assertEqual(list(running_series(self.tenant).values_list("pk", flat=True)), [self.series.pk])
        form = PawnDraftForm(workspace=self.tenant)
        self.assertEqual(list(form.fields["series"].queryset.values_list("pk", flat=True)), [self.series.pk])
        self.assertEqual(form["series"].value(), self.series.pk)
        loan, _, _, _ = self.start_review()
        set_series_active(self.series, is_active=False, actor=self.owner)
        edit = PawnDraftForm(workspace=self.tenant, instance=loan)
        self.assertTrue(edit.fields["series"].disabled)
        self.assertEqual(edit["series"].value(), self.series.pk)
        self.assertIn(self.series, edit.fields["series"].queryset)

    def test_forged_or_stale_series_cannot_save_a_new_draft(self):
        self._configured_setup()  # Keep the normal setup screen ready.
        set_series_active(self.series, is_active=False, actor=self.owner)
        data = self._payload(self.license, self.series)
        for series_id in (self.series.pk, 999999):
            data["series"] = series_id
            response = self.client.post(reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug]), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
            self.assertFalse(m.PawnLoan.objects.exists())
            self.assertEqual(self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1)

    def test_stop_reopen_is_audited_and_does_not_reset_exhaustion(self):
        sequence = self.series.number_sequences.get(document_kind="PAWN_LOAN")
        m.LoanNumberSequence.objects.filter(pk=sequence.pk).update(next_number=sequence.maximum_number + 1)
        set_series_active(self.series, is_active=False, actor=self.owner)
        set_series_active(self.series, is_active=False, actor=self.owner)
        self.assertEqual(series_new_loan_status(self.series)["label"], "Stopped for new loans")
        set_series_active(self.series, is_active=True, actor=self.owner)
        self.assertEqual(series_new_loan_status(self.series)["label"], "Numbers exhausted")
        self.assertEqual(AuditLog.objects.filter(company=self.tenant, data__entity="loan_series_availability").count(), 2)
        with self.assertRaises(SequenceExhaustedError):
            allocate_pawn_loan_number(series=self.series, actor=self.owner)
        self.assertEqual(allocate_release_number(series=self.series, actor=self.owner).counter, 1)

    def test_owner_stop_blocks_pending_confirmation_but_completed_retry_is_preserved(self):
        loan, path, _, page = self.start_review()
        set_series_active(self.series, is_active=False, actor=self.owner)
        failed = self.confirm(path, page)
        self.assertEqual(failed.status_code, 200)
        self.assertContains(failed, "stopped for new loans")
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertFalse(loan.loan_events.exists())
        set_series_active(self.series, is_active=True, actor=self.owner)
        self.assertEqual(self.confirm(path, page).status_code, 302)
        set_series_active(self.series, is_active=False, actor=self.owner)
        self.assertEqual(self.confirm(path, page).status_code, 302)
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)

    def test_stopped_series_and_expired_licence_still_allow_actual_closure(self):
        loan, path, _, page = self.start_review()
        self.confirm(path, page)
        set_series_active(self.series, is_active=False, actor=self.owner)
        m.LoanLicense.objects.filter(pk=self.license.pk).update(is_active=False, expires_on=date(2026, 7, 17))
        result = release_pawn_loan_in_full(loan.pk, settlement_amount=Decimal("10000"),
            request_key="stopped-series-closure", actor=self.owner)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(loan.releases.count(), 1)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(self.series.number_sequences.get(document_kind="PAWN_LOAN_RELEASE").next_number, 2)
        with self.assertRaises(LicenseSeriesError):
            allocate_pawn_loan_number(series=self.series, actor=self.owner)

    def test_stop_after_separate_approval_blocks_an_unpaid_disbursal(self):
        from apps.tenant_apps.loans.services.pawn_lifecycle import approve_pawn_loan
        from apps.tenant_apps.loans.services.pawn_disbursal import disburse_pawn_loan, PawnDisbursalError
        loan, _, _, _ = self.start_review()
        approve_pawn_loan(loan.pk, actor=self.owner)
        set_series_active(self.series, is_active=False, actor=self.owner)
        with self.assertRaisesRegex(PawnDisbursalError, "stopped for new loans"):
            disburse_pawn_loan(loan.pk, actor=self.owner, effective_date=date(2026, 7, 18))
        loan.refresh_from_db()
        self.assertEqual(loan.state, "APPROVED")
        self.assertFalse(loan.disbursal_snapshots.exists())
        self.assertFalse(loan.loan_events.exists())

    def test_last_numbered_draft_can_finish_when_counter_has_become_exhausted(self):
        sequence = self.series.number_sequences.get(document_kind="PAWN_LOAN")
        m.LoanNumberSequence.objects.filter(pk=sequence.pk).update(next_number=sequence.maximum_number)
        loan, path, _, page = self.start_review()
        self.assertFalse(running_series(self.tenant).exists())
        self.assertEqual(self.confirm(path, page).status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "ACTIVE")
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)

    def test_setup_explains_availability_and_never_hides_retained_series(self):
        set_series_active(self.series, is_active=False, actor=self.owner)
        page = self.client.get(reverse("workspace_loans:license_detail", args=[self.tenant.slug, self.license.pk]))
        self.assertContains(page, "Stopped for new loans")
        self.assertContains(page, self.series.code)
        page = self.client.get(reverse("workspace_loans:series_update", args=[self.tenant.slug, self.series.pk]))
        self.assertContains(page, "Open for new loans")
        self.assertContains(page, "Existing loans remain serviceable")


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OldPaperSeriesTests(WorkspaceTestCase):
    setup_tenant = classmethod(paper.RoutineEntryTests.setup_tenant.__func__)
    make_snapshot = paper.RoutineEntryTests.make_snapshot
    prepare_history = paper.RoutineEntryTests.prepare_history
    row = paper.RoutineEntryTests.row
    configure = paper.RoutineEntryTests.configure
    _entry_client = paper.RoutineEntryTests._entry_client
    setUp = paper.RoutineEntryTests.setUp
    paper_facts = paper.RoutineEntryTests.paper_facts

    @classmethod
    def get_test_schema_name(cls):
        return "old-paper-series"

    def test_old_series_is_explicit_nonfinancial_and_original_number_is_retained(self):
        client, path = self._entry_client()
        count = m.PawnLoan.objects.count()
        set_series_active(self.series, is_active=False, actor=self.actor)
        ordinary = client.get(path + "?entry=paper")
        self.assertFalse(ordinary.context["form"].fields["series_id"].queryset.exists())
        self.assertContains(ordinary, "No running series are available")
        page = client.get(path + "?entry=paper&include_old_series=1")
        self.assertContains(page, "Stopped for new loans")
        self.assertTrue(page.context["form"]["include_old_series"].value())
        data = self.paper_facts(page)
        data.update(include_old_series="on", entry_selection="auto", action="entry_change")
        response = client.post(path, data)
        self.assertEqual(response.context["entry_purpose"], "paper")
        self.assertEqual(response.context["form"]["number"].value(), data["number"])
        self.assertEqual(response.context["intent_token"], data["intent_token"])
        self.assertEqual(self.seq.next_number, 1)
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_unused_older_paper_number_can_be_recorded_after_exhaustion_with_exact_retry(self):
        client, path = self._entry_client()
        m.LoanNumberSequence.objects.filter(pk=self.seq.pk).update(next_number=self.seq.maximum_number + 1)
        set_series_active(self.series, is_active=False, actor=self.actor)
        page = client.get(path + "?entry=paper&include_old_series=1")
        data = self.paper_facts(page)
        data.update(include_old_series="on")
        review = client.post(path, data)
        self.assertIsNotNone(review.context["review"], review.context["form"].errors)
        data.update(action="confirm", confirm_review="on", review_token=review.context["review_token"])
        self.assertEqual(client.post(path, data).status_code, 302)
        data.pop("include_old_series")  # Signed older/open submissions remain repeatable.
        self.assertEqual(client.post(path, data).status_code, 302)
        loan = m.PawnLoan.objects.get(loan_number=data["number"])
        self.assertEqual(loan.state, "ACTIVE")
        self.assertEqual(loan.loan_number, data["number"])
        self.assertEqual(loan.disbursal_snapshots.count(), 1)
        self.series.refresh_from_db(); self.seq.refresh_from_db()
        self.assertFalse(self.series.is_active)
        self.assertEqual(self.seq.next_number, self.seq.maximum_number + 1)
