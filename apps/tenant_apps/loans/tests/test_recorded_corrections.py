from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

from dateutil.relativedelta import relativedelta
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.test import override_settings
from django.test import TransactionTestCase
from django.urls import reverse
from unittest.mock import patch

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from . import test_recorded_origination as fixtures
from . import test_recorded_history as history


class RecordedCorrectionTests(fixtures.RecordedOriginationTests):
    prepare_history = history.RecordedHistoryTests.prepare_history
    row = history.RecordedHistoryTests.row
    admit = history.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "recorded-corrections"

    def setUp(self):
        super().setUp()
        self.prepare_history()
        self.day = self.today - relativedelta(months=2)
        self.later = self.day + relativedelta(months=1) + timedelta(days=2)
        self.series.license.issued_on = self.day
        self.series.license.save()
        self.data.update(date=self.day.isoformat(), events=[self.row(date=self.later.isoformat())])
        self.loan, _, _ = self.admit()
        self.original = self.loan.loan_events.get(event_kind="REPAYMENT")
        self.correction = dict(operation="ADD", target=None, date=(self.day+timedelta(days=2)).isoformat(),
            amount="2000", reference="Missing August receipt", before=None, reason="Paper page was omitted", request_key=uuid4().hex)

    def correct(self):
        review, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertFalse(review["blockers"])
        created = record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertTrue(created)
        return review, token

    def active_receipts(self):
        return self.loan.loan_events.filter(event_kind="REPAYMENT", reversed_by_event__isnull=True).order_by("effective_date", "pk")

    def test_missing_earlier_receipt_restates_interest_allocations_asof_and_risk(self):
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        original_payload = deepcopy(self.original.payload)
        count = self.loan.loan_events.count()
        review, _ = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertEqual(self.loan.loan_events.count(), count)
        self.assertEqual(Decimal(review["before"]["principal"]), 8400)
        self.assertEqual(Decimal(review["after"]["principal"]), 6364)
        self.correct()
        balance = collection_balance(self.loan, self.today)
        self.assertEqual(balance.principal_outstanding, 6364)
        self.assertEqual(balance.interest_outstanding, Decimal("127.28"))
        receipts = list(self.active_receipts())
        self.assertEqual([Decimal(e.payload["values"]["interest"]) for e in receipts], [200, 164])
        self.assertEqual([Decimal(e.payload["repayment"]["amount_received"]) for e in receipts], [2000, 2000])
        self.original.refresh_from_db()
        self.assertEqual(self.original.payload, original_payload)
        self.assertEqual(self.original.reversed_by_event.effective_date, self.original.effective_date)
        self.assertEqual(receipts[1].payload["history_correction"]["source_event_id"], self.original.pk)
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
        self.assertEqual(exposure.total_economic_exposure, Decimal("6491.28"))
        old_date = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day+timedelta(days=3))
        self.assertEqual(old_date.total_economic_exposure, 8200)
        self.assertEqual(self.loan.collateral_items.get().custody_state, "IN_VAULT")

    def test_replace_and_repeat_correction_preserve_root_and_reference(self):
        self.correction.update(operation="REPLACE", target=self.original.pk, date=self.later.isoformat(),
                               amount="1000", reference="Receipt 10")
        _, token = self.correct()
        self.assertEqual(collection_balance(self.loan, self.today).principal_outstanding, 9400)
        count = self.loan.loan_events.count()
        self.assertFalse(record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True))
        self.assertEqual(count, self.loan.loan_events.count())
        active = self.active_receipts().get()
        self.correction.update(target=active.pk, amount="1500", request_key=uuid4().hex)
        self.correct()
        self.assertEqual(collection_balance(self.loan, self.today).principal_outstanding, 8900)
        self.assertEqual(self.active_receipts().get().payload["history_correction"]["root_event_id"], self.original.pk)

    def test_void_is_correction_not_refund_and_preserves_interest(self):
        self.correction.update(operation="VOID", target=self.original.pk, date=None, amount=None, reference="")
        self.correct()
        balance = collection_balance(self.loan, self.today)
        self.assertEqual(balance.principal_outstanding, 10000)
        self.assertEqual(balance.interest_outstanding, 600)
        self.assertFalse(self.active_receipts().exists())

    def test_move_receipt_to_actual_earlier_date(self):
        self.correction.update(operation="REPLACE", target=self.original.pk, reference="Receipt 10")
        self.correct()
        balance = collection_balance(self.loan, self.today)
        self.assertEqual(balance.principal_outstanding, 8200)
        self.assertEqual(balance.interest_outstanding, 328)

    def test_same_day_order_is_explicit(self):
        self.correction.update(date=self.later.isoformat(), amount="100", before=self.original.pk)
        self.correct()
        receipts = list(self.active_receipts())
        self.assertEqual([Decimal(e.payload["values"]["interest"]) for e in receipts], [100, 300])
        self.assertEqual(Decimal(receipts[0].payload["repayment"]["amount_received"]), 100)

    def test_missing_confirmation_expired_review_and_failure_after_reversal_are_atomic(self):
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        with self.assertRaisesMessage(ValueError, "Confirm"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token)
        with patch("django.core.signing.time.time", return_value=9999999999), self.assertRaisesMessage(ValueError, "expired"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        count = self.loan.loan_events.count()
        with patch("apps.tenant_apps.loans.services.recorded_corrections._record_pawn_loan_repayment_at", side_effect=ValueError("Replay failed")):
            with self.assertRaisesMessage(ValueError, "Replay failed"):
                record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertEqual(count, self.loan.loan_events.count())
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())

    def test_renewed_source_is_blocked_but_successor_collections_can_be_corrected(self):
        self.data.update(number="P-0020", source_reference="Other source", events=[
            self.row(kind="RENEW", number="P-0021", rate="1.5", tenure=3, date=self.later.isoformat())])
        self.args["intent_token"] = history.new_recording_intent(workspace=self.tenant, actor=self.actor)
        source, _, _ = self.admit()
        review, token = preview_correction(source.pk, actor=self.actor, data=self.correction)
        self.assertFalse(token)
        self.assertTrue(any("RENEWAL_SETTLEMENT" in blocker for blocker in review["blockers"]))
        successor = source.renewal_as_source.successor_loan
        self.correction.update(date=self.today.isoformat(), reference="Successor missed receipt")
        review, token = preview_correction(successor.pk, actor=self.actor, data=self.correction)
        self.assertFalse(review["blockers"])
        record_correction(successor.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.assertEqual(source.renewal_as_source.successor_principal_amount, 8400)

    def test_net_report_cash_counts_existing_receipt_once_after_reallocation(self):
        from apps.tenant_apps.loans.selectors.reports import _event_report_row
        self.correct()
        rows = [_event_report_row(e) for e in self.loan.loan_events.all() if e.event_kind in ("REPAYMENT", "REVERSAL")]
        self.assertEqual(sum((r.amount for r in rows), Decimal("0")), 4000)
        self.assertTrue(any("historical correction" in r.activity for r in rows))

    def test_bad_order_duplicate_overpayment_and_empty_reason_leave_originals(self):
        for changes in (dict(before=self.original.pk), dict(reference=" receipt 10 "), dict(amount="999999"), dict(reason=""), dict(date=(self.today+timedelta(days=1)).isoformat())):
            with self.subTest(changes=changes):
                count = self.loan.loan_events.count()
                with self.assertRaises(ValueError):
                    preview_correction(self.loan.pk, actor=self.actor, data=dict(self.correction, **changes))
                self.assertEqual(count, self.loan.loan_events.count())
                self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())

    def test_changed_review_and_changed_idempotency_facts_are_refused(self):
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.correction["amount"] = "1000"
        with self.assertRaisesMessage(ValueError, "changed"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        _, token = self.correct()
        self.correction["amount"] = "900"
        with self.assertRaisesMessage(ValueError, "different facts"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)

    def test_new_collection_invalidates_preview_and_followup_collections_still_work(self):
        from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="new-now", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token=token, confirmed=True)
        self.correct()
        result = record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="after-correction", actor=self.actor)
        self.assertEqual(result.allocation.interest, Decimal("27.28"))
        self.assertEqual(result.allocation.principal, Decimal("72.72"))

    def test_closed_history_lists_lifecycle_dependencies_without_writing(self):
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        release_pawn_loan_in_full(self.loan.pk, settlement_amount=collection_balance(self.loan, self.today).total_due,
                                 request_key="close", actor=self.actor)
        count = self.loan.loan_events.count()
        review, token = preview_correction(self.loan.pk, actor=self.actor, data=self.correction)
        self.assertFalse(token)
        self.assertTrue(any("RELEASE_RECEIPT" in blocker for blocker in review["blockers"]))
        self.assertEqual(count, self.loan.loan_events.count())
        with self.assertRaises(ValueError):
            record_correction(self.loan.pk, actor=self.actor, data=self.correction, review_token="", confirmed=True)

    def test_generic_reversal_cannot_split_recorded_correction(self):
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        self.correct()
        with self.assertRaisesMessage(ValueError, "Review paper history correction"):
            reverse_pawn_loan_event(self.active_receipts().last().pk, actor=self.actor, reason="Unsafe standalone reversal")

    def test_actor_and_foreign_workspace_cannot_correct(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        stranger = get_user_model().objects.create_user(username="correction-stranger")
        with self.assertRaises(PermissionDenied):
            preview_correction(self.loan.pk, actor=stranger, data=self.correction)
        other = Company.objects.create(name="Other correction", schema_name="other-correction", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(ValueError):
            preview_correction(self.loan.pk, actor=self.actor, data=self.correction)

    def test_restricted_role_posts_restatements_and_hides_them_from_other_workspace(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        other = Company.objects.create(name="Other role", schema_name="other-correction-role", owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("paper_correct_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            self.correct()
            connection.check_constraints()
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnLoanEvent.objects.filter(loan_id=self.loan.pk).exists())
                self.assertFalse(m.ObligationAllocation.objects.filter(loan_id=self.loan.pk).exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_http_review_confirm_and_retry_replacement(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_correct_paper_history", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk})
        self.assertContains(client.get(url), "Review paper history correction")
        self.correction.update(operation="REPLACE", target=self.original.pk, reference="Receipt 10")
        post = {key: value if value is not None else "" for key, value in self.correction.items()}
        post["action"] = "preview"
        response = client.post(url, post)
        self.assertContains(response, "Check every affected allocation")
        self.assertContains(response, "Previously " + self.later.isoformat())
        self.assertEqual(response.context["form"].errors, {})
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/correction-review.html").write_bytes(response.content)
        post.update(action="confirm", confirmed="on", review_token=response.context["form"]["review_token"].value())
        self.assertEqual(client.post(url, post).status_code, 302)
        self.assertEqual(client.post(url, post).status_code, 302)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        receipt = self.active_receipts().get()
        status = dict(PawnLoanDocumentProjectionBuilder.repayment_receipt(receipt).details)["Document status"]
        self.assertIn("not a new cash collection", status)
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        import fitz
        pdf = PawnLoanDocumentService.render_repayment_receipt(receipt).pdf
        document = fitz.open(stream=pdf, filetype="pdf")
        text = " ".join(" ".join(page.get_text().split()) for page in document)
        self.assertIn("not a new cash collection", text)
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path("/qa/corrected-receipt.pdf").write_bytes(pdf)
            for index, page in enumerate(document):
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(f"/qa/corrected-receipt-{index}.png")


class CorrectionConcurrencyTests(TransactionTestCase):
    make_snapshot = fixtures.RecordedOriginationTests.make_snapshot

    def setUp(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context
        self.actor = get_user_model().objects.create_user(username="correction-race-" + uuid4().hex)
        self.tenant = Company.objects.create(name="Correction race", schema_name="correction-" + uuid4().hex,
                                             owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            history.RecordedHistoryTests.prepare_history(self)
            _, token = history.preview_recorded_history(**self.args, data=self.data)
            self.loan, _ = history.admit_recorded_history(**self.args, data=self.data, review_token=token, confirmed=True)
            data = dict(operation="ADD", target=None, date=self.today.isoformat(), amount="2000", reference="Concurrent receipt",
                        before=None, reason="Missed page", request_key=uuid4().hex)
            _, token = preview_correction(self.loan.pk, actor=self.actor, data=data)
            self.submit = dict(loan_id=self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)

    def race(self, submissions):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from apps.tenancy.context import workspace_context
        ready = Barrier(2)
        def submit(data):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.tenant.pk):
                    return record_correction(**data)
            except ValueError:
                return "stale"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(submit, submissions))

    def test_same_correction_posts_once(self):
        from apps.tenancy.context import workspace_context
        self.assertEqual(sorted(self.race([self.submit, self.submit])), [False, True])
        with workspace_context(self.tenant.pk):
            self.assertEqual(self.loan.loan_events.filter(event_kind="REPAYMENT").count(), 1)

    def test_competing_reviews_cannot_both_post(self):
        from apps.tenancy.context import workspace_context
        other = deepcopy(self.submit)
        other["data"].update(request_key=uuid4().hex, reference="Different receipt")
        with workspace_context(self.tenant.pk):
            _, other["review_token"] = preview_correction(self.loan.pk, actor=self.actor, data=other["data"])
        result = self.race([self.submit, other])
        self.assertEqual(result.count(True), 1)
        self.assertEqual(result.count("stale"), 1)
