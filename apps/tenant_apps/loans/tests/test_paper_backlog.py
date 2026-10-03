from uuid import uuid4
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.test import override_settings
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.paper_backlog import record_backlog_checkpoint
from apps.tenant_apps.loans.services.batch_transaction_reviews import preview_batch_transaction_review, confirm_batch_transaction_review
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from . import test_recorded_origination as origins, test_recorded_history as histories


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PaperBacklogTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    admit = histories.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "paper-backlog"

    def setUp(self):
        self.prepare_history()

    def facts(self):
        return dict(book_reference="Lakshmi book A", through_date=self.today, last_page_reference="Page 12",
            state="ENTERED", note="Finished entering this book day", request_key=uuid4().hex)

    def two_loans(self):
        first, _, _ = self.admit()
        self.data.update(number="P-0011", source_reference="Book A / loan 11")
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        second, _, _ = self.admit()
        return first, second

    def test_progress_is_append_only_idempotent_and_has_no_financial_effect(self):
        loan, _, _ = self.admit()
        before = loan.loan_events.count(), loan.transaction_reviews.count()
        data = self.facts()
        checkpoint, created = record_backlog_checkpoint(workspace=self.tenant, actor=self.actor, **data)
        self.assertTrue(created)
        self.assertFalse(record_backlog_checkpoint(workspace=self.tenant, actor=self.actor, **data)[1])
        self.assertEqual((loan.loan_events.count(), loan.transaction_reviews.count()), before)
        with self.assertRaisesMessage(ValueError, "different progress"):
            record_backlog_checkpoint(workspace=self.tenant, actor=self.actor, **dict(data, state="NEEDS_REVIEW"))
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PaperBacklogCheckpoint.objects.filter(pk=checkpoint.pk).update(state="NEEDS_REVIEW")

    def test_restricted_role_isolates_checkpoint_and_forbids_mutation(self):
        checkpoint, _ = record_backlog_checkpoint(workspace=self.tenant, actor=self.actor, **self.facts())
        other = Company.objects.create(name="Other backlog", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("paper_backlog_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PaperBacklogCheckpoint.objects.filter(pk=checkpoint.pk).delete()
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PaperBacklogCheckpoint.objects.filter(pk=checkpoint.pk).exists())
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO loans_paperbacklogcheckpoint
                        (workspace_id, recorded_by_id, book_reference, through_date, last_page_reference, state, note, request_key, recorded_at)
                        VALUES (%s,%s,'Forged',%s,'1','ENTERED','','forged',CURRENT_TIMESTAMP)""",
                        [self.tenant.pk, self.actor.pk, self.today])
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_batch_creates_separate_reviews_and_retries_without_duplicates(self):
        first, second = self.two_loans()
        data = dict(through_date=self.today, confirmed_complete=True, source_reference="Book A / day checked", request_key=uuid4().hex)
        rows, token = preview_batch_transaction_review([second.pk, first.pk], actor=self.actor, **data)
        self.assertEqual(len(rows), 2)
        result = confirm_batch_transaction_review([first.pk, second.pk], actor=self.actor, **data, review_token=token, acknowledged=True)
        self.assertTrue(all(created for _, created in result))
        again = confirm_batch_transaction_review([first.pk, second.pk], actor=self.actor, **data, review_token=token, acknowledged=True)
        self.assertFalse(any(created for _, created in again))
        self.assertEqual(first.transaction_reviews.count(), 2)
        self.assertEqual(second.transaction_reviews.count(), 2)

    def test_stale_last_loan_rolls_back_every_batch_confirmation(self):
        first, second = self.two_loans()
        data = dict(through_date=self.today, confirmed_complete=True, source_reference="Book A / day checked", request_key=uuid4().hex)
        _, token = preview_batch_transaction_review([first.pk, second.pk], actor=self.actor, **data)
        record_pawn_loan_repayment(second.pk, amount="200", request_key="later", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            confirm_batch_transaction_review([first.pk, second.pk], actor=self.actor, **data, review_token=token, acknowledged=True)
        self.assertEqual(first.transaction_reviews.count(), 1)
        self.assertEqual(second.transaction_reviews.count(), 1)

    def test_batch_refuses_changed_selection_and_requires_authorized_actor(self):
        first, second = self.two_loans()
        data = dict(through_date=self.today, confirmed_complete=True, source_reference="Book A / day checked", request_key=uuid4().hex)
        _, token = preview_batch_transaction_review([first.pk, second.pk], actor=self.actor, **data)
        with self.assertRaisesMessage(ValueError, "selection"):
            confirm_batch_transaction_review([first.pk], actor=self.actor, **data, review_token=token, acknowledged=True)
        with self.assertRaises(PermissionDenied):
            preview_batch_transaction_review([first.pk], actor=None, **data)
        with self.assertRaises(PermissionDenied):
            record_backlog_checkpoint(workspace=self.tenant, actor=None, **self.facts())

    def test_backlog_and_batch_review_pages_are_reachable(self):
        self.start_active_trial()
        self.client.force_login(self.actor)
        for name in ("paper_backlog", "paper_batch_review"):
            response = self.client.get(reverse("workspace_loans:" + name, kwargs={"workspace_slug": self.tenant.slug}))
            self.assertEqual(response.status_code, 200)
            import os
            if os.environ.get("PAPER_QA_CAPTURE"):
                from pathlib import Path
                Path(os.environ["PAPER_QA_CAPTURE"], name.replace("_", "-") + ".html").write_bytes(response.content)

    def test_ordinary_batch_review_confirms_all_selected_loans(self):
        first, second = self.two_loans()
        self.start_active_trial()
        self.client.force_login(self.actor)
        path = reverse("workspace_loans:paper_batch_review", kwargs=dict(workspace_slug=self.tenant.slug))
        data = dict(numbers=first.loan_number+"\n"+second.loan_number, through_date=self.today.isoformat(),
            confirmed_complete="complete", source_reference="Both paper pages checked", request_key=uuid4().hex)
        response = self.client.post(path, dict(data, action="preview"))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["form"].errors)
        self.assertEqual(len(response.context["review"]), 2)
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path(os.environ["PAPER_QA_CAPTURE"], "paper-batch-review.html").write_bytes(response.content)
        response = self.client.post(path, dict(data, action="confirm", acknowledged="on", review_token=response.context["form"]["review_token"].value()))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(first.transaction_reviews.count(), 2)
        self.assertEqual(second.transaction_reviews.count(), 2)
