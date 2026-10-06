"""One retrospective action selects compatible evidence without changing origins."""
from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceTestCase, workspace_role_permissions
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import approve_pawn_loan, reopen_pawn_loan, reverse_pawn_loan_event
from apps.tenant_apps.loans.services.completed_payouts import completed_payout_adapter
from . import test_earlier_payout as earlier, test_completed_payouts as completed


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CompletedPayoutPresentationTests(WorkspaceTestCase):
    setup_tenant = classmethod(earlier.EarlierPayoutTests.setup_tenant.__func__)
    make_loan = earlier.EarlierPayoutTests.make_loan
    setUp = earlier.EarlierPayoutTests.setUp
    review = earlier.EarlierPayoutTests.review
    record = earlier.EarlierPayoutTests.record

    @classmethod
    def get_test_schema_name(cls):
        return "completed-payout-presentation-lc04"

    def paths(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        args = [self.tenant.slug, self.loan.pk]
        return tuple(reverse("workspace_loans:" + name, args=args) for name in (
            "pawn_loan_record_completed_payout", "pawn_loan_record_earlier_payout", "pawn_loan_detail"))

    def retained_approval(self):
        with patch("django.utils.timezone.now", return_value=self.next_day - timedelta(days=1)):
            approval = approve_pawn_loan(self.loan.pk, actor=self.actor)
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Review completed source")
        self.loan.refresh_from_db()
        return approval

    def post_review(self, path, token):
        return self.client.post(path, dict(review_token=token,
            reason="Confirmed original paper ticket", confirmed="on"))

    def test_unapproved_draft_old_link_redirects_to_general_completed_editor(self):
        path, old, detail = self.paths()
        self.assertEqual(completed_payout_adapter(self.loan), "RECORDED")
        self.assertRedirects(self.client.get(old), path, fetch_redirect_response=False)
        page = self.client.get(path)
        self.assertContains(page, "Record completed payout")
        self.assertIsNotNone(page.context["completed_draft"])
        self.assertNotContains(self.client.get(detail), old)
        self.assertFalse(self.loan.loan_events.exists())

    def test_retained_approval_selects_native_review_and_preserves_original_on_retry(self):
        original = self.retained_approval()
        before = deepcopy(original.payload)
        path, old, detail = self.paths()
        self.assertRedirects(self.client.get(old), path, fetch_redirect_response=False)
        page = self.client.get(path)
        self.assertEqual(page.context["basis_approval"].pk, original.pk)
        self.assertContains(page, "Record completed payout")
        self.assertContains(page, "Recording as")
        self.assertContains(page, self.actual_date.strftime("%d/%m/%Y"))
        self.assertNotContains(self.client.get(detail), old)
        self.assertFalse(self.loan.loan_events.exists())
        token = page.context["form"].initial["review_token"]
        self.assertEqual(self.post_review(path, token).status_code, 302)
        self.assertEqual(self.post_review(path, token).status_code, 302)
        self.assertEqual(self.loan.loan_events.count(), 1)
        original.refresh_from_db()
        self.assertEqual(original.payload, before)
        snapshot = self.loan.disbursal_snapshots.get()
        self.assertEqual(snapshot.basis, "APPROVED")
        self.assertEqual(snapshot.loan_event.payload["earlier_payout"]["basis_approval_id"], original.pk)

    def test_fully_reversed_native_origin_uses_correction_review_without_replacing_identity(self):
        first = self.record(self.review()[1])
        before = deepcopy(first.loan_event.payload)
        reverse_pawn_loan_event(first.loan_event.pk, actor=self.actor, reason="Incorrect original entry")
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Correct original terms")
        self.loan.refresh_from_db()
        path, old, detail = self.paths()
        page = self.client.get(path)
        self.assertContains(page, "reversed-payout evidence")
        self.assertNotContains(self.client.get(detail), old)
        token = page.context["form"].initial["review_token"]
        self.assertEqual(self.post_review(path, token).status_code, 302)
        self.assertEqual(self.post_review(path, token).status_code, 302)
        self.assertEqual(self.loan.loan_events.count(), 3)
        self.assertEqual(self.loan.repayment_schedules.count(), 2)
        self.assertEqual(self.loan.disbursal_snapshots.count(), 2)
        first.loan_event.refresh_from_db()
        self.assertEqual(first.loan_event.payload, before)

    def test_previously_issued_earlier_review_still_posts_at_old_endpoint(self):
        token = self.review()[1]
        _, old, _ = self.paths()
        self.assertEqual(self.post_review(old, token).status_code, 302)
        self.assertEqual(self.post_review(old, token).status_code, 302)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_native_stale_review_rolls_back_and_active_get_cannot_admit_again(self):
        self.retained_approval()
        path, _, detail = self.paths()
        token = self.client.get(path).context["form"].initial["review_token"]
        self.loan.tenure_months = 10
        self.loan.save(update_fields=["tenure_months"])
        page = self.post_review(path, token)
        self.assertContains(page, "changed")
        self.assertFalse(self.loan.loan_events.exists())
        self.loan.tenure_months = 12
        self.loan.save(update_fields=["tenure_months"])
        self.record(self.review()[1])
        self.assertRedirects(self.client.get(path), detail, fetch_redirect_response=False)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_native_review_does_not_fall_back_when_staff_lacks_setup_permission(self):
        self.retained_approval()
        path, _, _ = self.paths()
        staff = get_user_model().objects.create_user(username="completed-presentation-staff")
        role = Role.objects.create(name="Completed presentation staff")
        Membership.objects.create(user=staff, company=self.tenant, role=role)
        permissions = [Permission.objects.get_or_create(content_type=ContentType.objects.get_for_model(Company),
            codename=code, defaults={"name": code})[0] for code in
            ("data_view", "data_create", "data_edit", "loan_approve", "loan_disburse")]
        workspace_role_permissions(role, self.tenant).set(permissions)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(path).status_code, 403)
        self.assertFalse(self.loan.loan_events.exists())

    def test_native_review_remains_actor_bound_and_never_accepts_a_changed_quote(self):
        from apps.tenant_apps.rates.services import withdraw_quote
        self.retained_approval()
        path, _, _ = self.paths()
        token = self.client.get(path).context["form"].initial["review_token"]
        other = get_user_model().objects.create_user(username="completed-other-admin")
        Membership.objects.create(user=other, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        self.client.force_login(other)
        self.assertContains(self.post_review(path, token), "signed-in user")
        self.client.force_login(self.actor)
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk, reason="Incorrect original price")
        self.assertContains(self.post_review(path, token), "quote is missing, corrected or withdrawn")
        self.assertFalse(self.loan.loan_events.exists())

    def test_both_entry_urls_reject_a_foreign_workspace_loan(self):
        from uuid import uuid4
        from apps.tenancy.context import without_workspace_context, workspace_context
        path, old, _ = self.paths()
        original = self.loan
        other = Company.objects.create(name="Other entry workspace", schema_name=uuid4().hex,
            owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            Membership.objects.create(user=self.actor, company=other, role=Role.objects.get_or_create(name="Owner")[0])
            previous = self.tenant
            self.tenant = other
            self.make_loan(age_days=0, activate=False)
            foreign_id = self.loan.pk
            self.tenant, self.loan = previous, original
        for route in (path, old):
            foreign_path = route.replace(f"/{original.pk}/", f"/{foreign_id}/")
            self.assertEqual(self.client.get(foreign_path).status_code, 404)
        self.assertFalse(original.loan_events.exists())


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CompletedSourceMappingTests(WorkspaceTestCase):
    setup_tenant = classmethod(completed.CompletedPayoutTests.setup_tenant.__func__)
    make_snapshot = completed.CompletedPayoutTests.make_snapshot
    prepare_history = completed.CompletedPayoutTests.prepare_history
    make_draft = completed.CompletedPayoutTests.make_draft
    bind = completed.CompletedPayoutTests.bind
    preview = completed.CompletedPayoutTests.preview
    confirm = completed.CompletedPayoutTests.confirm
    setUp = completed.CompletedPayoutTests.setUp
    approved_source = completed.CompletedPayoutTests.approved_source

    @classmethod
    def get_test_schema_name(cls):
        return "completed-source-mapping-lc04"

    def revision(self, license=None):
        license = license or self.series.license
        return m.LoanLicenseRevision.objects.create(license=license, revision_number=1, kind="INITIAL",
            name=license.name, license_number=license.license_number, issued_on=license.issued_on,
            expires_on=license.expires_on, created_by=self.actor)

    def new_args(self):
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        return dict(workspace=self.tenant, actor=self.actor,
            intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor))

    def flexible_product(self):
        product = m.LoanProduct.objects.create(workspace=self.tenant, code="LC04", name="Flexible")
        return m.LoanProductVersion.objects.create(product=product, version=1, status="ACTIVE",
            repayment_structure="FLEXIBLE_PARTIAL_PAYMENT", amortisation_method="NONE", payment_frequency="FLEXIBLE",
            extra_payment_rule="REDUCE_PRINCIPAL", maximum_tenor_months=12, calculation_contract_version="TEST-V1")

    def test_explicit_mapping_supports_new_paper_history_export_without_invented_approval(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.history_contract import parse
        revision = self.revision()
        version = self.flexible_product()
        data = dict(self.data, number="P-0002", product_version_id=version.pk,
            license_revision_id=revision.pk, confirmed_history=True)
        args = self.new_args()
        _, token = preview_recorded_history(**args, data=data)
        loan, _ = admit_recorded_history(**args, data=data, review_token=token, confirmed=True)
        self.assertEqual(loan.license_revision_id, revision.pk)
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["terms"]["license_revision_id"], revision.pk)
        self.assertFalse(loan.approval_snapshots.exists())
        value = parse(export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk))
        self.assertEqual(value["manifest"]["profile"], "loan-history/4")
        self.assertEqual(value["loan"]["licence_number"], revision.license_number)
        self.assertIsNone(value["loan"]["original_actor"])

    def test_saved_draft_mapping_cannot_be_replaced_and_unknown_stays_unknown(self):
        revision = self.revision()
        self.data["license_revision_id"] = revision.pk
        with self.assertRaisesMessage(ValueError, "original licence evidence"):
            self.preview()
        self.data.pop("license_revision_id")
        loan, _ = self.confirm()
        self.assertIsNone(loan.license_revision_id)

    def test_source_mapping_must_match_series_and_original_date(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history
        revision = self.revision()
        other = self.make_snapshot(save=False).loan.license
        wrong = self.revision(other)
        args = self.new_args()
        for changes, error in ((dict(license_revision_id=wrong.pk), "selected series"),
                (dict(license_revision_id=revision.pk, date=(self.day - timedelta(days=1)).isoformat()), "actual payout date")):
            with self.subTest(changes=changes), self.assertRaisesMessage(ValueError, error):
                preview_recorded_history(**args, data=dict(self.data, number="P-0002", **changes))

    def test_approved_unpaid_draft_still_uses_general_editor_with_original_mapping_disabled(self):
        self.approved_source()
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_record_completed_payout", args=[self.tenant.slug, self.draft.pk])
        page = client.get(path)
        self.assertContains(page, "Record completed payout")
        self.assertTrue(page.context["form"].fields["license_revision_id"].disabled)
        self.assertEqual(self.draft.approval_snapshots.count(), 1)
        self.assertFalse(self.draft.loan_events.exists())

    def test_unknown_mapping_does_not_block_admission_but_still_blocks_portable_export(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.history_contract import HistoryError
        data = dict(self.data, number="P-0002", product_version_id=self.flexible_product().pk, confirmed_history=True)
        args = self.new_args()
        _, token = preview_recorded_history(**args, data=data)
        loan, _ = admit_recorded_history(**args, data=data, review_token=token, confirmed=True)
        self.assertIsNone(loan.license_revision_id)
        with self.assertRaisesMessage(HistoryError, "explicit source licence revision mapping"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)

    def test_legacy_reference_mapping_exports_unknown_original_validity_truthfully(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.history_contract import parse
        license, series = completed.CompletedPayoutTests.legacy(self)
        data = dict(self.data, series_id=series.pk, number="OLD-0001", confirmed_history=True,
            license_revision_id=license.revisions.get().pk, product_version_id=self.flexible_product().pk)
        args = self.new_args()
        _, token = preview_recorded_history(**args, data=data)
        loan, _ = admit_recorded_history(**args, data=data, review_token=token, confirmed=True)
        value = parse(export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk))
        self.assertIn("original validity unknown", value["loan"]["legacy_license_evidence"])
        license.refresh_from_db()
        self.assertFalse(license.is_active)
        self.assertIsNone(license.issued_on)

    def test_changed_mapping_after_review_cannot_post_and_preview_consumes_no_number(self):
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history, admit_recorded_history
        revision = self.revision()
        data = dict(self.data, number="P-0002", license_revision_id=revision.pk)
        args = self.new_args()
        count = m.PawnLoan.objects.count()
        _, token = preview_recorded_history(**args, data=data)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 2)
        with self.assertRaisesMessage(ValueError, "context changed"):
            admit_recorded_history(**args, data={key: value for key, value in data.items() if key != "license_revision_id"},
                review_token=token, confirmed=True)
        self.assertEqual(m.PawnLoan.objects.count(), count)

    def test_form_serializes_explicit_mapping_but_draft_forms_keep_prior_request_shape(self):
        from apps.tenant_apps.loans.web.recorded_history import PaperHistoryForm, Transactions, _data
        revision = self.revision()
        post = dict(self.data, license_revision_id=revision.pk, confirmed_history=True, payout_basis="CASH")
        form = PaperHistoryForm(post, workspace=self.tenant, routine=False)
        rows = Transactions({"events-TOTAL_FORMS": "0", "events-INITIAL_FORMS": "0"}, prefix="events")
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(rows.is_valid(), rows.errors)
        self.assertEqual(_data(form, rows)["license_revision_id"], revision.pk)
        form.saved_draft = True
        self.assertNotIn("license_revision_id", _data(form, rows))

    def test_foreign_revision_is_neither_selectable_nor_accepted_by_service(self):
        from uuid import uuid4
        from apps.tenancy.context import without_workspace_context, workspace_context
        from apps.tenant_apps.loans.web.recorded_history import PaperHistoryForm
        from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history
        other = Company.objects.create(name="Other source workspace", schema_name=uuid4().hex,
            owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk):
            license = m.LoanLicense.objects.create(workspace=other, name="Foreign licence", license_number="FOREIGN",
                issued_on=self.day, expires_on=self.today + timedelta(days=365))
            foreign = self.revision(license)
        self.assertNotIn(foreign.pk, PaperHistoryForm(workspace=self.tenant).fields["license_revision_id"].queryset.values_list("pk", flat=True))
        with self.assertRaisesMessage(ValueError, "this Workspace"):
            preview_recorded_history(**self.new_args(), data=dict(self.data, number="P-0002", license_revision_id=foreign.pk))

    def test_recorded_snapshot_cannot_use_native_reissue_even_with_a_draft_state_claim(self):
        from apps.tenant_apps.loans.services.historical_origination import require_earlier_native_draft
        loan, _ = self.confirm()
        count = loan.loan_events.count()
        # Adversarial in-memory lifecycle claim, not a persisted history change.
        loan.state = "DRAFT"
        self.assertIsNone(completed_payout_adapter(loan))
        with self.assertRaisesMessage(ValueError, "supported history correction"):
            require_earlier_native_draft(loan)
        self.assertEqual(loan.loan_events.count(), count)
