from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.test import TransactionTestCase
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase, workspace_role_permissions
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_borrower_corrections import (
    preview_borrower_correction,
    record_borrower_correction,
)
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.selectors.transaction_completeness import (
    transaction_completeness,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests import (
    test_recorded_origination as origins,
    test_recorded_history as histories,
)


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    }
)
class RecordedBorrowerCorrectionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "recorded-borrower-correction"

    def setUp(self):
        self.prepare_history()
        self.data["events"] = [self.row()]
        self.loan, _, _ = self.admit()
        self.original_borrower = self.loan.borrower
        self.target = Party.objects.create(display_name="Correct customer")
        self.facts = dict(
            borrower_id=self.target.pk,
            reference="Book A / page 10",
            reason="Wrong customer selected during entry",
            request_key=uuid4().hex,
        )

    def preview(self, **changes):
        return preview_borrower_correction(
            self.loan.pk, actor=self.actor, data=dict(self.facts, **changes)
        )

    def confirm(self, token=None, **changes):
        if token is None:
            _, token = self.preview(**changes)
        return record_borrower_correction(
            self.loan.pk,
            actor=self.actor,
            data=dict(self.facts, **changes),
            review_token=token,
            confirmed=True,
        )

    def test_preview_is_read_only_and_correction_preserves_financial_and_custody_rows(
        self,
    ):
        events = list(self.loan.loan_events.values())
        items = list(self.loan.collateral_items.values())
        schedules = list(
            m.RepaymentScheduleVersion.objects.filter(loan=self.loan).values()
        )
        balance = collection_balance(self.loan, self.today)
        old_number, old_policy, old_snapshot = (
            self.loan.loan_number,
            self.loan.policy_snapshot_id,
            self.loan.disbursal_snapshot_id,
        )
        logs = self.loan.change_log.count()
        review, token = self.preview()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.borrower_id, self.original_borrower.pk)
        self.assertEqual(self.loan.change_log.count(), logs)
        self.assertEqual(review["before"]["id"], self.original_borrower.pk)
        correction, created = self.confirm(token)
        self.assertTrue(created)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.borrower_id, self.target.pk)
        self.assertEqual(self.loan.updated_by_id, self.actor.pk)
        self.assertEqual(
            (
                self.loan.loan_number,
                self.loan.policy_snapshot_id,
                self.loan.disbursal_snapshot_id,
            ),
            (old_number, old_policy, old_snapshot),
        )
        self.assertEqual(list(self.loan.loan_events.values()), events)
        self.assertEqual(list(self.loan.collateral_items.values()), items)
        self.assertEqual(
            list(m.RepaymentScheduleVersion.objects.filter(loan=self.loan).values()),
            schedules,
        )
        self.assertEqual(collection_balance(self.loan, self.today), balance)
        self.assertEqual(
            transaction_completeness(self.loan, self.today).status, "CHANGED"
        )
        self.assertEqual(
            correction.metadata["borrower_correction"]["after"]["id"], self.target.pk
        )
        self.assertFalse(
            m.PawnLoan.objects.filter(
                pk=self.loan.pk, borrower=self.original_borrower
            ).exists()
        )
        self.assertTrue(
            m.PawnLoan.objects.filter(pk=self.loan.pk, borrower=self.target).exists()
        )

    def test_retry_is_idempotent_and_changed_retry_is_rejected(self):
        _, token = self.preview()
        correction, _ = self.confirm(token)
        self.assertEqual(self.confirm(token), (correction, False))
        self.assertEqual(
            self.loan.change_log.filter(event_kind="BORROWER_CORRECTED").count(), 1
        )
        with self.assertRaisesMessage(ValueError, "different borrower facts"):
            self.confirm(token, reason="Changed reason")

    def test_changed_customer_or_financial_facts_require_new_review(self):
        _, token = self.preview()
        self.target.display_name = "Changed target name"
        self.target.save()
        with self.assertRaisesMessage(ValueError, "facts changed"):
            self.confirm(token)
        _, token = self.preview()
        from apps.tenant_apps.loans.services.pawn_repayment import (
            record_pawn_loan_repayment,
        )

        record_pawn_loan_repayment(
            self.loan.pk, amount="100", request_key="later-payment", actor=self.actor
        )
        with self.assertRaisesMessage(ValueError, "facts changed"):
            self.confirm(token)

    def test_changed_submission_forged_expired_and_unconfirmed_reviews_are_rejected(
        self,
    ):
        _, token = self.preview()
        with self.assertRaisesMessage(ValueError, "facts changed"):
            self.confirm(token, reference="Another page")
        with self.assertRaisesMessage(ValueError, "again"):
            self.confirm("forged")
        with patch("django.core.signing.time.time", return_value=0):
            _, expired = self.preview()
        with self.assertRaisesMessage(ValueError, "again"):
            self.confirm(expired)
        with self.assertRaisesMessage(ValueError, "Confirm"):
            record_borrower_correction(
                self.loan.pk, actor=self.actor, data=self.facts, review_token=token
            )

    def test_same_inactive_blocked_and_missing_customers_are_rejected(self):
        with self.assertRaisesMessage(ValueError, "already"):
            self.preview(borrower_id=self.original_borrower.pk)
        for status in ("INACTIVE", "BLOCKED"):
            self.target.status = status
            self.target.save()
            with self.assertRaisesMessage(ValueError, "active customer"):
                self.preview()
        with self.assertRaisesMessage(ValueError, "active customer"):
            self.preview(borrower_id=99999999)

    def test_reference_reason_and_exact_fields_are_required(self):
        for key in ("reference", "reason"):
            with self.assertRaises(ValueError):
                self.preview(**{key: " "})
        with self.assertRaises(ValueError):
            self.preview(borrower_id=True)
        with self.assertRaises(ValueError):
            self.preview(principal="20000")

    def test_foreign_customer_and_loan_context_are_rejected(self):
        other = Company.objects.create(
            name="Foreign correction", owner=self.actor, creator=self.actor
        )
        with without_workspace_context(), workspace_context(other.pk):
            foreign = Party.objects.create(display_name="Foreign customer")
            with self.assertRaises(ValueError):
                self.preview()
        with self.assertRaisesMessage(ValueError, "active customer"):
            self.preview(borrower_id=foreign.pk)

    def test_service_requires_admin_and_edit_authority_at_confirmation(self):
        staff = get_user_model().objects.create_user(
            username="borrower-correction-staff"
        )
        role = Role.objects.create(name="Borrower entry staff")
        member = Membership.objects.create(user=staff, company=self.tenant, role=role)
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType

        grants = workspace_role_permissions(role, self.tenant)

        def grant(*names):
            grants.set(
                [
                    Permission.objects.get_or_create(
                        content_type=ContentType.objects.get_for_model(Company),
                        codename=name,
                        defaults={"name": name},
                    )[0]
                    for name in names
                ]
            )

        grant("data_view", "data_edit")
        with self.assertRaises(PermissionDenied):
            preview_borrower_correction(self.loan.pk, actor=staff, data=self.facts)
        grant("data_view", "workspace_settings")
        with self.assertRaises(PermissionDenied):
            preview_borrower_correction(self.loan.pk, actor=staff, data=self.facts)
        grant("data_view", "workspace_settings", "data_edit")
        _, token = preview_borrower_correction(
            self.loan.pk, actor=staff, data=self.facts
        )
        member.delete()
        with self.assertRaises(PermissionDenied):
            record_borrower_correction(
                self.loan.pk,
                actor=staff,
                data=self.facts,
                review_token=token,
                confirmed=True,
            )

    def test_closed_and_native_loans_are_rejected(self):
        self.loan.state = "CLOSED"
        self.loan.save(update_fields=["state"])
        with self.assertRaisesMessage(ValueError, "active loan"):
            self.preview()
        self.loan.state = "ACTIVE"
        self.loan.policy_snapshot = None
        self.loan.save(update_fields=["state", "policy_snapshot"])
        with self.assertRaisesMessage(ValueError, "frozen recorded policy"):
            self.preview()

    def test_linked_renewal_requires_reconciliation(self):
        from apps.tenant_apps.loans.tests.test_independent_paper import (
            IndependentPaperTests,
        )
        from apps.tenant_apps.loans.services.recorded_renewal_actions import (
            preview_existing_paper_renewal,
            record_existing_paper_renewal,
        )

        facts = IndependentPaperTests.renewal_data(self)
        facts["cash_paid"] = "3550"
        _, token = preview_existing_paper_renewal(
            loan_id=self.loan.pk, actor=self.actor, data=facts
        )
        successor, _ = record_existing_paper_renewal(
            loan_id=self.loan.pk,
            actor=self.actor,
            data=facts,
            review_token=token,
            confirmed=True,
        )
        with self.assertRaisesMessage(ValueError, "both borrowers"):
            preview_borrower_correction(successor.pk, actor=self.actor, data=self.facts)
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        page = client.get(
            reverse(
                "workspace_loans:pawn_loan_correct_borrower",
                args=[self.tenant.slug, successor.pk],
            )
        )
        self.assertContains(page, "What to review next")
        self.assertContains(page, f"Review linked agreement {self.loan.loan_number}")
        self.assertContains(
            page,
            reverse(
                "workspace_loans:pawn_loan_detail",
                args=[self.tenant.slug, self.loan.pk],
            ),
        )
        self.assertNotContains(page, 'value="preview"')

    def test_failed_projection_write_rolls_back_audit(self):
        _, token = self.preview()
        with patch.object(m.PawnLoan, "save", side_effect=ValueError("write failed")):
            with self.assertRaisesMessage(ValueError, "write failed"):
                self.confirm(token)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.borrower_id, self.original_borrower.pk)
        self.assertFalse(
            self.loan.change_log.filter(event_kind="BORROWER_CORRECTED").exists()
        )

    def test_restricted_role_posting_immutability_and_foreign_json_guards(self):
        other = Company.objects.create(
            name="Other borrower scope", owner=self.actor, creator=self.actor
        )
        with without_workspace_context(), workspace_context(other.pk):
            foreign = Party.objects.create(display_name="Foreign borrower")
        role = connection.ops.quote_name("borrower_correct_" + uuid4().hex)
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
            )
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            correction, _ = self.confirm()
            for operation in (
                lambda: m.LoanChangeLog.objects.filter(pk=correction.pk).update(
                    reason="overwrite"
                ),
                lambda: m.LoanChangeLog.objects.filter(pk=correction.pk).delete(),
            ):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    operation()
            with (
                self.assertRaisesMessage(DatabaseError, "must be retained"),
                transaction.atomic(),
                connection.cursor() as cursor,
            ):
                cursor.execute(
                    "DELETE FROM party_party WHERE id=%s", [self.original_borrower.pk]
                )
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanChangeLog.objects.create(
                    workspace=self.tenant,
                    loan=self.loan,
                    actor=self.actor,
                    event_kind="BORROWER_CORRECTED",
                    from_state="ACTIVE",
                    to_state="ACTIVE",
                    reason=correction.reason,
                    metadata=correction.metadata,
                )
            metadata = deepcopy(correction.metadata)
            metadata["borrower_correction"]["after"]["id"] = foreign.pk
            metadata["borrower_correction"]["request_key"] = "foreign-insert"
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanChangeLog.objects.create(
                    workspace=self.tenant,
                    loan=self.loan,
                    actor=self.actor,
                    event_kind="BORROWER_CORRECTED",
                    from_state="ACTIVE",
                    to_state="ACTIVE",
                    reason=correction.reason,
                    metadata=metadata,
                )
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(
                    m.LoanChangeLog.objects.filter(pk=correction.pk).exists()
                )
                self.assertFalse(m.PawnLoan.objects.filter(pk=self.loan.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_http_customer_search_review_confirmation_audit_and_preserved_documents(
        self,
    ):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        kwargs = dict(workspace_slug=self.tenant.slug, pk=self.loan.pk)
        detail = reverse("workspace_loans:pawn_loan_detail", kwargs=kwargs)
        url = reverse("workspace_loans:pawn_loan_correct_paper_borrower", kwargs=kwargs)
        ticket_url = reverse("workspace_loans:pawn_loan_ticket_pdf", kwargs=kwargs)
        original = client.get(ticket_url)
        self.assertEqual(original.status_code, 200)
        original_id = original["X-Rokkad-Document-Issue"]
        self.assertContains(client.get(detail), 'id="loan-corrections"')
        correction_menu = client.get(
            reverse("workspace_loans:pawn_loan_correction_review", kwargs=kwargs)
        )
        self.assertRedirects(
            correction_menu, detail + "#loan-corrections", fetch_redirect_response=False
        )
        self.assertContains(
            client.get(detail),
            reverse("workspace_loans:pawn_loan_correct_borrower", kwargs=kwargs),
        )
        entry = client.get(url)
        self.assertContains(entry, "Correct loan customer")
        data = dict(self.facts, borrower=self.facts["borrower_id"], action="preview")
        del data["borrower_id"]
        response = client.post(url, data)
        self.assertFalse(response.context["form"].errors)
        self.assertContains(response, self.target.party_code)
        self.assertContains(response, "Record reviewed borrower correction")
        import os
        from pathlib import Path

        if os.environ.get("PAPER_QA_CAPTURE"):
            capture = Path(os.environ["PAPER_QA_CAPTURE"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "borrower-form.html").write_bytes(entry.content)
            (capture / "borrower-review.html").write_bytes(response.content)
            (capture / "correction-menu.html").write_bytes(client.get(detail).content)
        token = response.context["form"]["review_token"].value()
        self.assertEqual(
            client.post(
                url, dict(data, action="confirm", review_token=token, confirmed="on")
            ).status_code,
            302,
        )
        self.assertContains(client.get(detail), "Wrong customer selected during entry")
        corrected = client.get(ticket_url)
        self.assertEqual(corrected.status_code, 200)
        self.assertNotEqual(corrected["X-Rokkad-Document-Issue"], original_id)
        from apps.tenant_apps.loans.services.document_layouts import (
            LoanDocumentLayoutService,
        )

        self.assertEqual(
            LoanDocumentLayoutService.read_verified_artifact(
                m.LoanDocumentIssue.objects.get(pk=original_id)
            ),
            original.content,
        )
        from apps.tenant_apps.loans.documents.payloads import (
            PawnLoanDocumentProjectionBuilder,
        )

        self.loan.refresh_from_db()
        self.assertIn(
            "borrower corrected",
            str(PawnLoanDocumentProjectionBuilder.loan_ticket(self.loan)),
        )
        self.assertIn(
            "borrower corrected",
            str(
                PawnLoanDocumentProjectionBuilder.repayment_receipt(
                    self.loan.loan_events.get(event_kind="REPAYMENT")
                )
            ),
        )

    def test_exports_do_not_silently_discard_previous_borrower(self):
        self.confirm()
        from apps.tenant_apps.loans.services.history_export import export_history
        from apps.tenant_apps.loans.services.servicing_bundle import (
            export_servicing_bundle,
        )
        from apps.tenant_apps.loans.services.history_contract import HistoryError

        for export in (export_history,):
            with self.assertRaisesMessage(HistoryError, "both Party identities"):
                export(
                    workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk
                )

    def test_exact_recovery_retains_both_borrowers_and_correction_evidence(self):
        self.confirm()
        from apps.tenant_apps.loans.tests.test_pawn_recovery import PawnRecoveryTests

        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = PawnRecoveryTests.export(self)
        self.assertEqual(original["tables"], restored["tables"])
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.borrower_id, self.target.pk)
        self.assertEqual(
            self.loan.change_log.get(event_kind="BORROWER_CORRECTED").metadata[
                "borrower_correction"
            ]["before"]["id"],
            self.original_borrower.pk,
        )

    def test_migration_preserves_existing_evidence_and_refuses_populated_downgrade(
        self,
    ):
        from importlib import import_module

        migration = import_module(
            "apps.tenant_apps.loans.migrations.0075_recorded_borrower_correction"
        ).Migration
        sql = migration.operations[-1]
        before = list(self.loan.loan_events.values())
        connection.check_constraints()
        # Confined to this test transaction; ordinary loan rows must survive
        # removing/reinstalling the empty new evidence guards.
        with connection.cursor() as cursor:
            cursor.execute(sql.reverse_sql)
            cursor.execute(sql.sql)
        self.assertEqual(list(self.loan.loan_events.values()), before)
        self.confirm()
        with (
            self.assertRaisesMessage(DatabaseError, "prevents downgrade"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(sql.reverse_sql)

    def test_old_party_identity_cannot_be_deleted_after_correction(self):
        self.confirm()
        # Use SQL to exercise the guard independently of ORM PROTECT references.
        with (
            self.assertRaisesMessage(DatabaseError, "must be retained"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "DELETE FROM party_party WHERE id=%s", [self.original_borrower.pk]
            )

    def test_monitoring_stales_and_old_reminder_review_cannot_be_reused(self):
        from apps.tenant_apps.loans.services.risk_snapshots import (
            refresh_loan_risk_snapshot,
        )
        from apps.tenant_apps.loans.selectors.transaction_completeness import (
            transaction_fingerprint,
        )
        from apps.tenant_apps.loans.services.notice_delivery_readiness import _blocker
        from types import SimpleNamespace
        from django.utils import timezone

        frozen = dict(
            review_id=transaction_completeness(self.loan, self.today).review_id,
            source_fingerprint=transaction_fingerprint(self.loan),
        )
        m.LoanMonitoringPolicy.objects.create(
            workspace=self.tenant,
            effective_from=self.day,
            version=1,
            compliance_profile="Fictional monitoring",
            ltv_warning_ratio="0.8",
            ltv_breach_ratio="0.9",
            ltv_critical_ratio="1",
            eligible_custody_states=["IN_VAULT"],
            severity_mapping={"WATCH": "LOW", "BREACH": "MEDIUM", "CRITICAL": "HIGH"},
        )
        refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        self.confirm()
        self.loan.refresh_from_db()
        self.assertEqual(m.LoanRiskSnapshot.objects.get(loan=self.loan).status, "STALE")
        # Even after a new paper check, an old recipient's intent stays stale.
        notice = SimpleNamespace(
            scheduled_for=timezone.now(),
            payload_snapshot={"transaction_review": frozen},
        )
        coverage = SimpleNamespace(complete=True, review_id=frozen["review_id"])
        self.assertIn(
            "Prepare a new reminder", _blocker(notice, self.loan, coverage, None)
        )


class RecordedBorrowerCorrectionConcurrencyTests(TransactionTestCase):
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    admit = histories.RecordedHistoryTests.admit

    def setUp(self):
        self.actor = get_user_model().objects.create_user(
            username="borrower-race-" + uuid4().hex
        )
        self.tenant = Company.objects.create(
            name="Borrower race", owner=self.actor, creator=self.actor
        )
        Membership.objects.create(
            user=self.actor,
            company=self.tenant,
            role=Role.objects.get_or_create(name="Owner")[0],
        )
        with workspace_context(self.tenant.pk):
            self.prepare_history()
            self.loan, _, _ = self.admit()
            self.target = Party.objects.create(display_name="Correct race customer")
            self.facts = dict(
                borrower_id=self.target.pk,
                reference="Book page 10",
                reason="Mistaken selection",
                request_key=uuid4().hex,
            )
            _, self.token = preview_borrower_correction(
                self.loan.pk, actor=self.actor, data=self.facts
            )

    def race(self, submissions):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections

        ready = Barrier(2)

        def submit(args):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.tenant.pk):
                    correction, created = record_borrower_correction(
                        self.loan.pk, actor=self.actor, confirmed=True, **args
                    )
                    return correction.pk, created
            except ValueError as exc:
                return str(exc)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(submit, submissions))

    def test_identical_concurrent_confirmations_record_once(self):
        args = dict(data=self.facts, review_token=self.token)
        results = self.race([args, args])
        self.assertTrue(all(isinstance(row, tuple) for row in results), results)
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [False, True])

    def test_competing_reviews_cannot_both_change_borrower(self):
        with workspace_context(self.tenant.pk):
            target = Party.objects.create(display_name="Second correction target")
            facts = dict(self.facts, borrower_id=target.pk, request_key=uuid4().hex)
            _, token = preview_borrower_correction(
                self.loan.pk, actor=self.actor, data=facts
            )
        results = self.race(
            [
                dict(data=self.facts, review_token=self.token),
                dict(data=facts, review_token=token),
            ]
        )
        self.assertEqual(sum(isinstance(row, tuple) for row in results), 1)
        with workspace_context(self.tenant.pk):
            self.assertEqual(
                self.loan.change_log.filter(event_kind="BORROWER_CORRECTED").count(), 1
            )
