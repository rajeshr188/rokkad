"""Completed facts are admitted once without retroactively approving lending."""
from copy import deepcopy
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction, DatabaseError
from django.test import override_settings, TransactionTestCase
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference
from . import test_recorded_origination as origins, test_recorded_history as histories
from . import test_collateral_reappraisal as native, test_pawn_recovery as backups


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CompletedPayoutTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row

    @classmethod
    def get_test_schema_name(cls):
        return "completed-payout-ld03"

    def setUp(self):
        self.prepare_history()
        self.make_draft()

    def make_draft(self):
        self.draft = m.PawnLoan.objects.create(workspace=self.tenant, license=self.series.license,
            series=self.series, borrower_id=self.data["borrower_id"],
            product_version_id=self.data["product_version_id"], loan_number="P-0001", loan_date=self.day,
            principal_amount=10000, monthly_interest_rate=2, tenure_months=3,
            creation_submission_id=uuid4())
        self.item = m.PawnCollateralItem.objects.create(loan=self.draft, description="Ring", metal="GOLD",
            quantity=1, gross_weight=10, net_weight=9, purity_percentage=90,
            allocated_principal=10000, monthly_interest_rate=2)
        self.seq.next_number = 2
        self.seq.save(update_fields=["next_number"])
        self.data.update(number=self.draft.loan_number, recording_mode="TRANSACTION_ENTRY", confirmed_history=False)
        self.bind()

    def bind(self):
        self.args = dict(workspace=self.tenant, actor=self.actor, draft_id=self.draft.pk,
            intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor, draft_id=self.draft.pk))

    def preview(self):
        return preview_recorded_history(**self.args, data=self.data)

    def confirm(self, token=None):
        if token is None:
            _, token = self.preview()
        return admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)

    def test_original_identity_items_submission_and_number_reservation_survive(self):
        original = (self.draft.pk, self.draft.creation_submission_id, self.item.pk)
        count = m.PawnLoan.objects.count()
        review, token = self.preview()
        self.draft.refresh_from_db()
        self.assertEqual(self.draft.state, "DRAFT")
        self.assertFalse(self.draft.loan_events.exists())
        loan, created = self.confirm(token)
        self.assertTrue(created)
        self.assertEqual((loan.pk, loan.creation_submission_id, loan.collateral_items.get().pk), original)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.seq.refresh_from_db()
        self.assertEqual(self.seq.next_number, 2)
        self.assertEqual(review["draft_source"]["loan_id"], loan.pk)
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["draft_source"], review["draft_source"])
        self.assertEqual(loan.disbursal_snapshot.loan_event.effective_date, self.day)
        self.assertEqual(loan.disbursal_snapshot.basis, "RECORDED")
        self.assertIsNone(loan.disbursal_snapshot.approval_snapshot_id)
        self.assertIsNone(loan.disbursal_snapshot.evidence["recording"]["original_actor"])
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(collection_balance(loan, self.today).principal_outstanding, 10000)

    def test_retry_is_idempotent_and_changed_facts_or_other_intent_are_rejected(self):
        _, token = self.preview()
        loan, _ = self.confirm(token)
        self.assertEqual(self.confirm(token), (loan, False))
        events = loan.loan_events.count()
        self.data["source_reference"] = "Different book"
        with self.assertRaisesMessage(ValueError, "different facts"):
            self.confirm(token)
        self.data["source_reference"] = "Book A / loan 10"
        self.bind()
        with self.assertRaisesMessage(ValueError, "Another payout"):
            self.confirm(token)
        self.assertEqual(loan.loan_events.count(), events)

    def test_stale_item_review_rolls_back_all_financial_writes(self):
        _, token = self.preview()
        m.PawnCollateralItem.objects.filter(pk=self.item.pk).update(description="Changed saved fact")
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.confirm(token)
        self.draft.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual((self.draft.state, self.item.description), ("DRAFT", "Changed saved fact"))
        self.assertFalse(self.draft.loan_events.exists())
        self.assertFalse(self.draft.disbursal_snapshots.exists())

    def test_actual_supported_terms_can_correct_unapproved_draft_without_old_quotes(self):
        from apps.tenant_apps.rates.models import Rate
        self.assertFalse(Rate.objects.exists())
        self.data.update(principal="12000", rate="3", cash_paid="12000", entry_note="Original signed book differs")
        loan, _ = self.confirm()
        self.assertEqual(loan.principal_amount, 12000)
        self.assertEqual(loan.collateral_items.get().allocated_principal, 12000)
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["entry_note"], self.data["entry_note"])

    def test_missing_complete_book_attestation_is_provisional_not_admission_blocker(self):
        from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
        loan, _ = self.confirm()
        self.assertFalse(transaction_completeness(loan, self.today).complete)
        self.assertFalse(loan.transaction_reviews.exists())

    def test_multiple_saved_items_keep_actual_rates_and_ids(self):
        from apps.tenant_apps.loans.services.recorded_items import contract_items
        first = contract_items(self.data)[0]
        first["principal"] = "6000"
        second = dict(first, description="Anklets", metal="SILVER", principal="4000", rate="4")
        self.item.allocated_principal = 6000
        self.item.save()
        other = m.PawnCollateralItem.objects.create(loan=self.draft, description="Anklets", metal="SILVER",
            quantity=1, gross_weight=10, net_weight=9, purity_percentage=90, allocated_principal=4000,
            monthly_interest_rate=4)
        self.data.update(collateral=[first, second], rate="2.8")
        ids = [self.item.pk, other.pk]
        loan, _ = self.confirm()
        self.assertEqual(list(loan.collateral_items.order_by("pk").values_list("pk", flat=True)), ids)
        self.assertEqual(loan.disbursal_snapshot.monthly_interest, 280)
        self.assertEqual(collection_balance(loan, self.today).interest_outstanding, 280)

    def test_known_receipt_and_closure_reconcile_on_the_same_draft(self):
        self.data.update(final_state="CLOSED", confirmed_history=True,
            events=[self.row("CLOSE", "10200", number="R-0001", recipient="Borrower")])
        loan, _ = self.confirm()
        self.assertEqual((loan.pk, loan.state), (self.draft.pk, "CLOSED"))
        self.assertEqual(collection_balance(loan, self.today).total_due, 0)

    def test_source_identity_cannot_be_replaced_or_new_form_used_for_existing_draft(self):
        self.data["number"] = "P-0002"
        with self.assertRaisesMessage(ValueError, "draft's customer"):
            self.preview()
        self.data["number"] = self.draft.loan_number
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        with self.assertRaisesMessage(ValueError, "submission reference is invalid"):
            self.preview()

    def test_same_source_cannot_be_admitted_as_fresh_loan(self):
        args = dict(workspace=self.tenant, actor=self.actor,
            intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor))
        with self.assertRaises(ValueError):
            preview_recorded_history(**args, data=self.data)

    def test_any_financial_origin_blocks_draft_readmission(self):
        source = self.make_snapshot(save=False).loan
        self.args["draft_id"] = source.pk
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor, draft_id=source.pk)
        with self.assertRaisesMessage(ValueError, "no financial origin"):
            self.preview()

    def test_collateral_photo_is_retained(self):
        from apps.tenant_apps.loans.services import append_collateral_photo
        photo = append_collateral_photo(self.item.pk,
            upload=SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"), actor=self.actor)
        photo_ids = list(self.item.photos.values_list("pk", "sha256"))
        self.confirm()
        self.assertEqual(list(self.item.photos.values_list("pk", "sha256")), photo_ids)

    def approved_source(self):
        native.CollateralReappraisalTests.make_loan(self, age_days=8, activate=False)
        from apps.tenant_apps.loans.services import approve_pawn_loan
        with patch("django.utils.timezone.now", return_value=self.quote.effective_at):
            approval = approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.loan.refresh_from_db()
        self.draft = self.loan
        self.series = self.loan.series
        self.data.update(borrower_id=self.loan.borrower_id, series_id=self.series.pk,
            product_version_id=self.loan.product_version_id, number=self.loan.loan_number,
            date=self.loan.loan_date.isoformat(), principal="1000", cash_paid="1000", tenure=12,
            description="Gold ring", gross_weight="1", net_weight="1", purity="100")
        before = deepcopy(m.PawnLoanApprovalSnapshot.objects.get(pk=approval.pk).payload)
        old_policy = self.loan.policy_snapshot_id
        self.bind()
        return approval, before, old_policy

    def test_native_approval_and_policy_are_retained_as_genuine_evidence(self):
        approval, before, old_policy = self.approved_source()
        loan, _ = self.confirm()
        approval.refresh_from_db()
        self.assertEqual(approval.payload, before)
        self.assertEqual(loan.approval_snapshots.count(), 1)
        self.assertIsNone(old_policy)  # Native approval precedes disbursal-policy capture.
        self.assertEqual(loan.policy_snapshot.basis, "RECORDED_CONTRACT")
        self.assertIsNone(loan.disbursal_snapshot.approval_snapshot_id)
        self.assertEqual(loan.disbursal_snapshot.evidence["recording"]["draft_source"]["retained_approvals"][0]["id"], approval.pk)

    def test_different_actual_terms_cannot_silently_change_retained_approval(self):
        approval, before, _ = self.approved_source()
        self.data.update(principal="1100", cash_paid="1100")
        with self.assertRaisesMessage(ValueError, "retained approval evidence"):
            self.preview()
        approval.refresh_from_db()
        self.assertEqual(approval.payload, before)
        self.assertFalse(self.draft.loan_events.exists())

    def test_existing_policy_snapshot_and_issued_document_are_retained(self):
        from django.core.files.base import ContentFile
        policy = m.LoanPolicySnapshot.objects.create(loan=self.draft, basis="ORIGINATION",
            interest_method="SIMPLE", partial_month_method="FULL_MONTH", valuation_method="CALCULATED_METAL_VALUE",
            maximum_ltv_ratio=Decimal("0.8"), rounding_method="PER_ACCRUAL_PERIOD", currency_quantum=Decimal("1"))
        document = m.LoanDocumentIssue(workspace=self.tenant, document_type="loan_ticket", source_type="PawnLoan",
            source_id=str(self.draft.pk), source_fingerprint="original-draft", payload_schema_version=1,
            payload_hash="original-payload", pdf_hash="original-pdf", issued_by=self.actor)
        document.artifact.save("draft.pdf", ContentFile(b"%PDF-original-evidence"), save=True)
        old_artifact = document.artifact.name
        loan, _ = self.confirm()
        self.assertTrue(m.LoanPolicySnapshot.objects.filter(pk=policy.pk, currency_quantum=1).exists())
        self.assertNotEqual(loan.policy_snapshot_id, policy.pk)
        document.refresh_from_db()
        self.assertEqual((document.source_fingerprint, document.artifact.name), ("original-draft", old_artifact))

    def test_missing_original_valuation_does_not_prevent_current_risk_monitoring(self):
        from apps.tenant_apps.rates.models import Rate, RateSource
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        loan, _ = self.confirm()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, effective_from=self.today, version=1,
            compliance_profile="Current coverage", ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"),
            ltv_critical_ratio=Decimal("0.9"), eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"],
            severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        self.assertIsNone(get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today).eligible_collateral_value)
        source = RateSource.objects.create(name="Current market", location="Local")
        Rate.objects.create(rate_source=source, buying_rate=2000, selling_rate=2100)
        self.assertEqual(get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today).eligible_collateral_value, Decimal("16200"))
        self.assertEqual(loan.disbursal_snapshot.gross_principal, 10000)

    def test_current_lending_still_requires_price_evidence(self):
        from apps.tenant_apps.loans.services.loan_workflow import make_review
        with self.assertRaises(ValueError):
            make_review(self.draft)
        self.assertFalse(self.draft.loan_events.exists())
        self.confirm()

    def test_missing_edit_authority_and_foreign_workspace_cannot_admit_draft(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Membership, Role
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from apps.tenancy.testing import workspace_role_permissions
        staff = get_user_model().objects.create_user(username="completed-staff")
        role = Role.objects.create(name="Completed limited staff")
        Membership.objects.create(user=staff, company=self.tenant, role=role)
        grants = workspace_role_permissions(role, self.tenant)
        grants.set([Permission.objects.get_or_create(content_type=ContentType.objects.get_for_model(Company),
            codename=name, defaults={"name": name})[0] for name in ("data_view", "data_create", "loan_disburse")])
        args = dict(self.args, actor=staff, intent_token=new_recording_intent(workspace=self.tenant,
            actor=staff, draft_id=self.draft.pk))
        with self.assertRaises(PermissionDenied):
            preview_recorded_history(**args, data=self.data)
        other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(PermissionDenied):
            self.preview()
        self.assertFalse(self.draft.loan_events.exists())

    def legacy(self):
        license = create_legacy_license_reference(workspace=self.tenant, actor=self.actor,
            name="Original paper book", source_label="Old licence", evidence_reference="Register page 1")
        series = m.LoanSeries.objects.create(license=license, name="Original register", code="OLD")
        m.LoanNumberSequence.objects.create(series=series, document_kind="PAWN_LOAN", prefix="OLD-", width=4,
            next_number=1, maximum_number=9999)
        return license, series

    def use_legacy_draft(self):
        license, series = self.legacy()
        self.draft.license = license
        self.draft.license_revision = license.revisions.get()
        self.draft.series = series
        self.draft.loan_number = "OLD-0001"
        self.draft.save()
        self.series = series
        self.data.update(series_id=series.pk, number=self.draft.loan_number)
        self.bind()
        return license

    def test_legacy_reference_admits_actual_payout_without_authorizing_new_lending(self):
        license = self.use_legacy_draft()
        loan, _ = self.confirm()
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete IMMEDIATE")
            cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete DEFERRED")
        license.refresh_from_db()
        self.assertTrue(license.is_legacy_reference)
        self.assertFalse(license.is_active)
        self.assertIsNone(license.issued_on)
        self.assertEqual(loan.disbursal_snapshot.basis, "RECORDED")
        from apps.tenant_apps.loans.services import approve_pawn_loan
        with self.assertRaises(ValueError):
            approve_pawn_loan(loan.pk, actor=self.actor)

    def test_never_entered_paper_loan_can_use_legacy_reference(self):
        license, series = self.legacy()
        data = dict(self.data, series_id=series.pk, number="OLD-0002")
        args = dict(workspace=self.tenant, actor=self.actor,
            intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor))
        _, token = preview_recorded_history(**args, data=data)
        loan, created = admit_recorded_history(**args, data=data, review_token=token, confirmed=True)
        self.assertTrue(created)
        self.assertEqual(loan.license_id, license.pk)
        self.assertIsNone(loan.disbursal_snapshot.approval_snapshot_id)
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete IMMEDIATE")
            cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete DEFERRED")

    def test_legacy_guard_rejects_native_and_snapshotless_forgery_under_restricted_role(self):
        from apps.tenant_apps.loans.integrations import disbursal_payload
        from apps.tenant_apps.loans.services.event_recording import record_loan_event
        self.use_legacy_draft()
        policy = m.LoanPolicySnapshot.objects.create(loan=self.draft, basis="RECORDED_CONTRACT",
            interest_method="SIMPLE", partial_month_method="FULL_MONTH", valuation_method="CALCULATED_METAL_VALUE",
            maximum_ltv_ratio=Decimal("0.8"), rounding_method="PER_ACCRUAL_PERIOD", currency_quantum=Decimal("0.01"))
        payload = disbursal_payload(self.draft, effective_date=self.day, principal_amount=10000,
            net_cash_amount=10000, advance_interest_amount=0, deducted_fee_amount=0).to_dict()
        payload.update(disbursal=dict(basis="RECORDED", policy_snapshot_id=policy.pk, approval_snapshot_id=None),
            recording=dict(schema="recorded-origination/1", payout_already_occurred=True,
                date_precision="DAY", occurred_on=self.day.isoformat(), source_reference="Register 1"))
        role = connection.ops.quote_name("completed_test_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            for path, value in (("disbursal.basis", "APPROVED"), ("disbursal.basis", None),
                    ("disbursal.approval_snapshot_id", 123), ("disbursal.policy_snapshot_id", -1),
                    ("recording.schema", "invented"), ("recording.payout_already_occurred", False),
                    ("recording.source_reference", " "), ("recording.occurred_on", self.today.isoformat())):
                bad = deepcopy(payload)
                part, field = path.split(".")
                bad[part][field] = value
                with self.subTest(path=path), self.assertRaises(DatabaseError), transaction.atomic():
                    record_loan_event(self.draft.pk, event_kind="DISBURSAL", effective_date=self.day,
                        payload=bad, actor=self.actor)
            with self.assertRaisesMessage(DatabaseError, "validated recorded snapshot"), transaction.atomic():
                record_loan_event(self.draft.pk, event_kind="DISBURSAL", effective_date=self.day,
                    payload=payload, actor=self.actor)
                with connection.cursor() as cursor:
                    cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete IMMEDIATE")
            loan, _ = self.confirm()
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete IMMEDIATE")
                cursor.execute("SET CONSTRAINTS loans_legacy_recorded_origin_complete DEFERRED")
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanDisbursalSnapshot.objects.filter(loan=loan).update(net_disbursed=1)
            other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnLoan.objects.filter(pk=loan.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_source_draft_and_legacy_snapshot_survive_exact_recovery(self):
        self.use_legacy_draft()
        self.confirm()
        original = backups.PawnRecoveryTests.export(self)
        backups.PawnRecoveryTests.empty(self)
        self.assertTrue(backups.PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = backups.PawnRecoveryTests.export(self)
        for name in ("tables", "files", "reconciliation", "guards_sha256"):
            self.assertEqual(original[name], restored[name], name)

    def test_shared_editor_locks_identity_and_preview_confirmation_reuses_draft(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_record_completed_payout", args=[self.tenant.slug, self.draft.pk])
        page = self.client.get(path + "?series=999999&party=999999")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["form"]["date"].value(), self.day)
        self.assertEqual(page.context["form"]["series_id"].value(), self.series.pk)
        self.assertTrue(page.context["form"].fields["number"].disabled)
        self.assertEqual(len(page.context["formset"]), 1)
        self.assertContains(page, "Existing collateral: Ring")
        self.assertNotContains(page, 'id="add-collateral"')
        values = dict(self.data, routine_entry="on", exceptions="on", exception_reason="Actual register terms",
            document_charge="0", currency_quantum="0.01", action="preview", intent_token=page.context["intent_token"],
            **{"events-TOTAL_FORMS": "0", "events-INITIAL_FORMS": "0", "collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "1"})
        values.update({"collateral-0-" + key: value for key, value in dict(description="Ring", quantity=1, metal="GOLD",
            gross_weight="10", net_weight="9", purity_percentage="90", allocated_principal="10000", interest_rate_override="2").items()})
        for name in ("borrower_id", "series_id", "product_version_id", "number", "date"):
            values.pop(name)
        preview = self.client.post(path, values)
        self.assertEqual(preview.status_code, 200)
        self.assertFalse(preview.context["form"].errors, preview.context["form"].errors)
        self.assertIsNotNone(preview.context["review"])
        values.update(action="confirm", confirm_review="on", review_token=preview.context["review_token"])
        response = self.client.post(path, values)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        self.assertIn(f"/{self.draft.pk}/", response.url)
        self.assertEqual(self.client.post(path, values).status_code, 302)


class CompletedPayoutConcurrencyTests(TransactionTestCase):
    make_snapshot = histories.RecordedHistoryConcurrencyTests.make_snapshot
    race = histories.RecordedHistoryConcurrencyTests.race

    def setUp(self):
        histories.RecordedHistoryConcurrencyTests.setUp(self)
        with workspace_context(self.tenant.pk):
            CompletedPayoutTests.make_draft(self)
            _, token = preview_recorded_history(**self.args, data=self.data)
        self.commit = dict(**self.args, data=self.data, review_token=token, confirmed=True)

    bind = CompletedPayoutTests.bind

    def test_existing_draft_race_posts_once_and_does_not_reissue_number(self):
        results = self.race([self.commit, self.commit])
        self.assertEqual(results[0][0], self.draft.pk)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [False, True])
        with workspace_context(self.tenant.pk):
            self.assertEqual(self.draft.disbursal_snapshots.count(), 1)
            self.seq.refresh_from_db()
            self.assertEqual(self.seq.next_number, 2)

    def test_distinct_reviews_of_same_draft_cannot_both_commit(self):
        with workspace_context(self.tenant.pk):
            self.bind()
            _, token = preview_recorded_history(**self.args, data=self.data)
        other = dict(**self.args, data=self.data, review_token=token, confirmed=True)
        self.assertEqual(sum(result is not None for result in self.race([self.commit, other])), 1)
