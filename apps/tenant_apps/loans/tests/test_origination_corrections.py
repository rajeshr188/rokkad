"""Actual-paper corrections retain mistaken native attempts without relending."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import override_settings, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_history import (
    new_recording_intent, preview_recorded_history, admit_recorded_history,
)
from apps.tenant_apps.loans.services.pawn_reversal import _reverse_pawn_loan_event_at
from apps.tenant_apps.loans.services.pawn_lifecycle import reopen_pawn_loan
from apps.tenant_apps.loans.services.origination_corrections import (
    correction_source, retained_attempt_event_ids, validate_correction_evidence,
)
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from . import test_collateral_reappraisal as native_fixtures
from . import test_pawn_recovery as backups, test_recorded_history as history_fixtures


@override_settings(ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OriginationCorrectionTests(WorkspaceTestCase):
    setup_tenant = classmethod(native_fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = native_fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def get_test_schema_name(cls):
        return "origination-correction-lo01"

    def setUp(self):
        if connection.in_atomic_block:
            from .recovery_fixtures import lock_recovery_fixture_tables
            lock_recovery_fixture_tables()
        self.make_loan(age_days=2)
        self.native = self.loan.loan_events.get(event_kind="DISBURSAL")
        self.retained = deepcopy(self.approval.payload)
        self.old_snapshot = self.loan.disbursal_snapshot_id
        _reverse_pawn_loan_event_at(self.native.pk, reason="Wrong digital attempt",
            actor=self.actor, effective_date=(self.today if self._testMethodName ==
                "test_different_day_reversal_is_explicitly_outside_this_profile" else self.native.effective_date))
        self.loan = reopen_pawn_loan(self.loan.pk, reason="Record actual paper agreement", actor=self.actor)
        self.original_day = self.today - timedelta(days=13)
        self.loan.loan_date = self.original_day
        self.loan.save(update_fields=["loan_date"])
        self.data = dict(borrower_id=self.loan.borrower_id, series_id=self.loan.series_id,
            product_version_id=self.loan.product_version_id, number=self.loan.loan_number,
            date=self.original_day.isoformat(), principal="2100", rate="4", tenure=3,
            advance_months=1, document_charge="10", payout_basis="CASH", cash_paid="2006",
            source_reference="Actual book D01623", description=self.item.description,
            metal=self.item.metal, quantity=self.item.quantity, gross_weight=str(self.item.gross_weight),
            net_weight=str(self.item.net_weight), purity=str(self.item.purity_percentage),
            monitoring_method="CALCULATED_METAL_VALUE", monitoring_ltv="0.8",
            monitoring_reason="Current coverage, not original approval",
            complete_through=self.today.isoformat(), final_state="ACTIVE",
            confirmed_history=False, confirmed_rule=True, recording_mode="TRANSACTION_ENTRY", events=[])
        self.args = dict(workspace=self.tenant, actor=self.actor, draft_id=self.loan.pk,
            correction_reason="Actual September paper payout; October digital attempt reversed",
            intent_token=new_recording_intent(workspace=self.tenant, actor=self.actor,
                draft_id=self.loan.pk, correction=True))

    def preview(self):
        return preview_recorded_history(**self.args, data=self.data)

    def confirm(self, token=None):
        if token is None:
            _, token = self.preview()
        return admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)

    def test_preview_rolls_back_and_commit_preserves_all_retained_evidence(self):
        events = list(self.loan.loan_events.values())
        items = list(self.loan.collateral_items.values_list("pk", flat=True))
        review, token = self.preview()
        self.assertEqual(list(self.loan.loan_events.values()), events)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.disbursal_snapshot_id, self.old_snapshot)
        loan, created = self.confirm(token)
        self.assertTrue(created)
        self.assertEqual(loan.pk, self.loan.pk)
        self.assertEqual(list(loan.collateral_items.values_list("pk", flat=True)), items)
        self.approval.refresh_from_db()
        self.assertEqual(self.approval.payload, self.retained)
        self.assertEqual(list(loan.loan_events.filter(pk__in=[row["id"] for row in events]).values()), events)
        self.assertNotEqual(loan.disbursal_snapshot_id, self.old_snapshot)
        self.assertEqual(loan.disbursal_snapshot.basis, "RECORDED")
        self.assertIsNone(loan.disbursal_snapshot.approval_snapshot_id)
        self.assertEqual((loan.disbursal_snapshot.gross_principal, loan.disbursal_snapshot.advance_interest,
            loan.disbursal_snapshot.deducted_fees, loan.disbursal_snapshot.net_disbursed),
            (Decimal("2100"), Decimal("84"), Decimal("10"), Decimal("2006")))
        self.assertEqual(loan.repayment_schedules.count(), 2)
        self.assertEqual(len(retained_attempt_event_ids(loan)), 2)
        self.assertEqual(review["origination_correction"],
            loan.disbursal_snapshot.evidence["recording"]["origination_correction"])
        position = get_servicing_position(loan, as_of_date=self.today)
        self.assertEqual(position.contract.profile, "recorded-anniversary/3")
        self.assertEqual(position.balance.principal_outstanding, 2100)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.recorded_contract(loan)
        self.assertIn("actual-paper origination correction", str(payload))

    def test_retry_reason_facts_and_separate_submission_do_not_duplicate(self):
        _, token = self.preview()
        loan, _ = self.confirm(token)
        self.assertEqual(self.confirm(token), (loan, False))
        self.args["correction_reason"] = "Different explanation"
        with self.assertRaisesMessage(ValueError, "different correction reason"):
            self.confirm(token)
        self.args["correction_reason"] = loan.disbursal_snapshot.evidence["recording"]["origination_correction"]["reason"]
        self.data["source_reference"] = "Changed book"
        with self.assertRaisesMessage(ValueError, "different facts"):
            self.confirm(token)
        self.data["source_reference"] = "Actual book D01623"
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor,
            draft_id=loan.pk, correction=True)
        with self.assertRaisesMessage(ValueError, "Another payout"):
            self.confirm(token)
        self.assertEqual(loan.loan_events.count(), 3)

    def test_normal_admission_and_retained_route_do_not_silently_fall_back(self):
        from apps.tenant_apps.loans.services.historical_origination import historical_basis
        self.assertIsNone(historical_basis(self.loan)["approval"])
        args = dict(self.args)
        args.pop("correction_reason")
        args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor, draft_id=self.loan.pk)
        with self.assertRaisesMessage(ValueError, "no financial origin"):
            preview_recorded_history(**args, data=self.data)
        with self.assertRaisesMessage(ValueError, "submission reference"):
            preview_recorded_history(**dict(self.args, correction_reason=None), data=self.data)
        self.assertEqual(self.loan.loan_events.count(), 2)

    def test_stale_review_or_reason_rolls_back_actual_terms_and_new_origin(self):
        _, token = self.preview()
        self.item.monthly_interest_rate = Decimal("3")
        self.item.save(update_fields=["monthly_interest_rate"])
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.confirm(token)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.principal_amount, 1000)
        self.assertEqual(self.loan.disbursal_snapshot_id, self.old_snapshot)
        self.assertEqual(self.loan.loan_events.count(), 2)
        _, token = self.preview()
        self.args["correction_reason"] = "Changed reviewed reason"
        with self.assertRaisesMessage(ValueError, "changed since review"):
            self.confirm(token)

    def test_known_receipt_before_wrong_attempt_uses_actual_monthly_contract(self):
        self.data["events"] = [dict(kind="PAYMENT", amount="100", date=(self.original_day + timedelta(days=1)).isoformat(),
            reference="Actual receipt", number="", rate=None, tenure=None, recipient="")]
        loan, _ = self.confirm()
        self.assertEqual(get_servicing_position(loan, as_of_date=self.today).balance.principal_outstanding, 2000)
        from dateutil.relativedelta import relativedelta
        boundary = self.original_day + relativedelta(months=1)
        self.assertEqual(get_servicing_position(loan, as_of_date=boundary).balance.interest_outstanding, 0)
        self.assertEqual(get_servicing_position(loan, as_of_date=boundary + timedelta(days=1)).balance.interest_outstanding, 80)

    def test_corrected_origin_requires_history_correction_and_cannot_be_reissued(self):
        from apps.tenant_apps.loans.services.pawn_disbursal import disburse_pawn_loan
        loan, _ = self.confirm()
        with self.assertRaisesMessage(ValueError, "Review paper history correction"):
            _reverse_pawn_loan_event_at(loan.disbursal_snapshot.loan_event_id, reason="Actual agreement requires another review",
                actor=self.actor, effective_date=self.today)
        with self.assertRaisesMessage(ValueError, "recorded origin"):
            disburse_pawn_loan(loan.pk, actor=self.actor, effective_date=self.today)
        self.assertEqual(loan.loan_events.count(), 3)

    def test_altered_retained_pair_is_not_valid_correction_evidence(self):
        loan, _ = self.confirm()
        snapshot = loan.disbursal_snapshot
        snapshot.evidence = deepcopy(snapshot.evidence)
        snapshot.evidence["recording"]["origination_correction"]["attempts"][0]["payout_sha256"] = "0" * 64
        with self.assertRaisesMessage(ValueError, "differs from its retained"):
            validate_correction_evidence(snapshot)

    def test_receipt_history_correction_and_monitoring_use_actual_origin(self):
        loan, _ = self.confirm()
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        data = dict(operation="ADD", target=None, before=None, date=(self.original_day + timedelta(days=1)).isoformat(),
            amount="100", reference="Missing actual receipt", reason="Register receipt entered late", request_key=uuid4().hex)
        _, token = preview_correction(loan_id=loan.pk, actor=self.actor, data=data)
        record_correction(loan_id=loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        loan.refresh_from_db()
        self.assertEqual(get_servicing_position(loan, as_of_date=self.today).balance.principal_outstanding, 2000)
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        self.assertEqual(Decimal(snapshot.source_provenance["financial"]["recorded_total_due"]), 2000)
        self.assertEqual(len(retained_attempt_event_ids(loan)), 2)

    def test_physical_collateral_facts_are_not_silently_rewritten(self):
        self.data["net_weight"] = "0.9"
        with self.assertRaisesMessage(ValueError, "physical collateral facts"):
            self.preview()
        self.item.refresh_from_db()
        self.assertEqual(self.item.net_weight, 1)

    def test_missing_reason_and_active_or_serviced_loan_cannot_enter_correction(self):
        with self.assertRaisesMessage(ValueError, "correction reason"):
            preview_recorded_history(**dict(self.args, correction_reason=""), data=self.data)
        loan, _ = self.confirm()
        with self.assertRaisesMessage(ValueError, "Reopen"):
            correction_source(loan, actor=self.actor)

    def test_correction_requires_administration_beyond_payout_permissions(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from apps.tenancy.testing import workspace_role_permissions
        staff = get_user_model().objects.create_user(username="origin-staff")
        role = Role.objects.get_or_create(name="Origin entry staff")[0]
        Membership.objects.create(company=self.tenant, user=staff, role=role)
        workspace_role_permissions(role, self.tenant).set([Permission.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(Company), codename=name,
            defaults={"name": name})[0] for name in ("data_create", "data_edit", "loan_disburse")])
        with self.assertRaises(PermissionDenied):
            correction_source(self.loan, actor=staff)
        with self.assertRaises(PermissionDenied):
            new_recording_intent(workspace=self.tenant, actor=staff, draft_id=self.loan.pk, correction=True)

    def test_different_day_reversal_is_explicitly_outside_this_profile(self):
        with self.assertRaisesMessage(ValueError, "different date"):
            correction_source(self.loan, actor=self.actor)

    def test_exact_backup_retains_attempts_bounded_export_refuses_to_drop_them(self):
        from apps.tenant_apps.loans.services.servicing_bundle import export_servicing_bundle
        loan, _ = self.confirm()
        with self.assertRaisesMessage(ValueError, "exact Workspace recovery"):
            export_servicing_bundle(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        original = backups.PawnRecoveryTests.export(self)
        backups.PawnRecoveryTests.empty(self)
        self.assertTrue(backups.PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = backups.PawnRecoveryTests.export(self)
        for field in ("tables", "files", "reconciliation", "guards_sha256"):
            self.assertEqual(original[field], restored[field], field)
        loan.refresh_from_db()
        self.assertEqual(len(retained_attempt_event_ids(loan)), 2)
        self.assertEqual(get_servicing_position(loan, as_of_date=self.today).balance.principal_outstanding, 2100)

    def test_explicit_correction_page_is_read_only_and_requires_reason(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        path = reverse("workspace_loans:pawn_loan_correct_origination",
            kwargs=dict(workspace_slug=self.tenant.slug, pk=self.loan.pk))
        page = self.client.get(path)
        self.assertContains(page, "Correct recorded origination")
        self.assertTrue(page.context["origination_correction"])
        self.assertEqual(self.loan.loan_events.count(), 2)
        detail = reverse("workspace_loans:pawn_loan_detail",
            kwargs=dict(workspace_slug=self.tenant.slug, pk=self.loan.pk))
        self.assertContains(self.client.get(detail), path)
        values = dict(self.data, routine_entry="on", exceptions="on", exception_reason="Actual register terms",
            correction_reason=self.args["correction_reason"], currency_quantum="0.01", action="preview",
            intent_token=page.context["intent_token"], **{"events-TOTAL_FORMS": "0", "events-INITIAL_FORMS": "0",
            "collateral-TOTAL_FORMS": "1", "collateral-INITIAL_FORMS": "1"})
        values.update({"collateral-0-" + key: value for key, value in dict(description=self.item.description,
            quantity=1, metal="GOLD", gross_weight="1", net_weight="1", purity_percentage="100",
            allocated_principal="2100", interest_rate_override="4").items()})
        preview = self.client.post(path, values)
        self.assertFalse(preview.context["form"].errors, preview.context["form"].errors)
        self.assertIsNotNone(preview.context["review"])
        values.update(action="confirm", confirm_review="on", review_token=preview.context["review_token"])
        self.assertEqual(self.client.post(path, values).status_code, 302)
        self.assertEqual(self.client.post(path, values).status_code, 302)
        self.assertEqual(self.loan.loan_events.count(), 3)
        page = self.client.get(detail)
        self.assertTrue(page.context["ticket_is_recorded"])
        self.assertContains(page, "Open the recorded agreement copy")

    def test_restricted_role_posts_once_and_isolation_and_immutability_hold(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        role = connection.ops.quote_name("origin_correction_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            loan, _ = self.confirm()
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.filter(pk=self.native.pk).update(payload={})
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanDisbursalSnapshot.objects.filter(pk=loan.disbursal_snapshot_id).update(evidence={})
            other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnLoan.objects.filter(pk=loan.pk).exists())
                with self.assertRaises(PermissionDenied):
                    self.preview()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class OriginationCorrectionConcurrencyTests(TransactionTestCase):
    make_loan = OriginationCorrectionTests.make_loan
    race = history_fixtures.RecordedHistoryConcurrencyTests.race

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context
        self.actor = get_user_model().objects.create_user(username="origin-race-" + uuid4().hex)
        self.tenant = Company.objects.create(name="Origin concurrency", schema_name=uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            OriginationCorrectionTests.setUp(self)
            _, token = preview_recorded_history(**self.args, data=self.data)
        self.commit = dict(**self.args, data=self.data, review_token=token, confirmed=True)

    def test_same_correction_posts_once_under_concurrency(self):
        from apps.tenancy.context import workspace_context
        results = self.race([self.commit, self.commit])
        self.assertEqual([row[0] for row in results], [self.loan.pk, self.loan.pk])
        self.assertEqual(sorted(row[1] for row in results), [False, True])
        with workspace_context(self.tenant.pk):
            self.assertEqual(self.loan.loan_events.count(), 3)

    def test_distinct_correction_reviews_cannot_both_commit(self):
        from apps.tenancy.context import workspace_context
        with workspace_context(self.tenant.pk):
            other = dict(self.args, intent_token=new_recording_intent(workspace=self.tenant,
                actor=self.actor, draft_id=self.loan.pk, correction=True))
            _, token = preview_recorded_history(**other, data=self.data)
        results = self.race([self.commit, dict(**other, data=self.data, review_token=token, confirmed=True)])
        self.assertEqual(sum(row is not None for row in results), 1)
        with workspace_context(self.tenant.pk):
            self.assertEqual(self.loan.loan_events.count(), 3)
