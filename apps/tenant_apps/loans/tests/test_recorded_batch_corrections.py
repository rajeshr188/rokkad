from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch

from dateutil.relativedelta import relativedelta
from django.test import override_settings
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.recorded_batch_corrections import preview_batch_correction, record_batch_correction
from apps.tenant_apps.loans.services.recorded_corrections import preview_correction
from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
from apps.tenant_apps.loans.services.recorded_collections import collection_balance
from apps.tenant_apps.loans.services.release_batches import preview_release_batch, complete_release_batch
from apps.tenant_apps.loans.selectors.recorded_batches import batch_financial_review
from . import test_recorded_origination as fixtures
from . import test_recorded_history as history
from . import test_recorded_corrections as receipt_tests
from . import test_release_batches as batch_tests


class RecordedBatchCorrectionTests(fixtures.RecordedOriginationTests):
    prepare_history = history.RecordedHistoryTests.prepare_history
    row = history.RecordedHistoryTests.row
    admit = history.RecordedHistoryTests.admit

    @classmethod
    def get_test_schema_name(cls):
        return "batch-corrections"

    def setUp(self):
        super().setUp()
        self.prepare_history()
        self.day = self.today - relativedelta(months=2)
        self.later = self.day + relativedelta(months=1) + timedelta(days=2)
        self.series.license.issued_on = self.day
        self.series.license.save()
        self.data.update(date=self.day.isoformat(), events=[self.row(date=self.later.isoformat())])

    def make_batch(self, *, paper=False):
        self.loans = []
        for number in ("0010", "0011"):
            self.data.update(number="P-" + number, source_reference="Paper book " + number)
            self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
            self.loans.append(self.admit()[0])
        quote = preview_release_batch(workspace=self.tenant, actor=self.actor, loan_ids=[loan.pk for loan in self.loans])
        self.assertTrue(quote["ready"], quote)
        if paper:
            from apps.tenant_apps.loans.services.paper_closures import preview_paper_closures, complete_paper_closures
            preview = preview_paper_closures(workspace=self.tenant, actor=self.actor,
                loan_ids=[loan.pk for loan in self.loans], closure_date=self.today)
            self.batch = complete_paper_closures(workspace=self.tenant, actor=self.actor, request_key=uuid4(),
                quote_token=preview["token"], confirmed=True, paper_reference="Separate receipts on page 8",
                rows=[dict(loan_id=row["loan"].pk, amount=str(row["amount"]), paid_by="Individual payer",
                    collector_name="Borrower") for row in preview["rows"]])
        else:
            self.batch = complete_release_batch(workspace=self.tenant, actor=self.actor, request_key=uuid4(),
                quote_token=quote["quote_token"], paid_by="Family payer", payment_reference="Shared collection",
                payment_confirmed=True, collectors=[dict(loan_id=loan.pk, collector_is_borrower=True,
                    collector_name="", relationship="", authorization_note="", handover_confirmed=True) for loan in self.loans])
        self.assertEqual(self.batch.total_amount, Decimal("17136"))
        self.facts = dict(total_received="12982.56", reference="Checked combined receipt", reason="Missing paper pages",
            request_key=uuid4().hex, confirmed_unchanged=True, loans=[dict(loan_id=loan.pk, correction=dict(
                operation="ADD", target=None, date=(self.day+timedelta(days=2)).isoformat(), amount="2000",
                reference="Missing receipt", before=None, settlement=dict(cash_received="6491.28", cash_paid="0",
                    interest_offset="0", reference="Checked release", confirmed_unchanged=True))) for loan in self.loans])
        return self.batch

    def preview(self):
        return preview_batch_correction(self.batch.pk, actor=self.actor, data=self.facts)

    def record(self, token):
        return record_batch_correction(self.batch.pk, actor=self.actor, data=self.facts, review_token=token, confirmed=True)

    def test_atomic_restatement_retains_originals_custody_and_zero_balances(self):
        self.make_batch()
        originals = list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint"))
        custody = list(m.PawnCollateralCustodyEvent.objects.values_list("pk", flat=True))
        review, token = self.preview()
        self.assertEqual(list(m.PawnLoanEvent.objects.values_list("pk", "payload_fingerprint")), originals)
        self.assertEqual(Decimal(review["total"]), Decimal("12982.56"))
        self.assertTrue(self.record(token))
        self.assertFalse(self.record(token))
        self.batch.refresh_from_db()
        self.assertEqual(self.batch.total_amount, Decimal("17136"))
        current = batch_financial_review(self.batch)
        self.assertEqual(current["total"], Decimal("12982.56"))
        self.assertEqual([line.release.settlement_amount for line in current["lines"]], [Decimal("6491.28")]*2)
        self.assertEqual(list(self.batch.lines.values_list("release__settlement_amount", flat=True)), [Decimal("8568")]*2)
        self.assertEqual(list(m.PawnCollateralCustodyEvent.objects.values_list("pk", flat=True)), custody)
        self.assertEqual(list(m.PawnLoanEvent.objects.filter(pk__in=[pk for pk, _ in originals]).values_list("pk", "payload_fingerprint")), originals)
        from apps.tenant_apps.loans.services.obligations import reconcile_loan_obligations
        for loan in self.loans:
            loan.refresh_from_db()
            self.assertEqual(loan.state, "CLOSED")
            self.assertEqual(collection_balance(loan, self.today).total_due, 0)
            self.assertEqual(reconcile_loan_obligations(loan).integrity_findings, ())

    def test_unchanged_member_is_included_without_new_events(self):
        self.make_batch()
        sibling = self.loans[1]
        before = list(sibling.loan_events.values_list("pk", flat=True))
        self.facts["loans"][1]["correction"] = None
        self.facts["total_received"] = "15059.28"
        review, token = self.preview()
        self.assertFalse(review["rows"][1]["changed"])
        self.record(token)
        self.assertEqual(list(sibling.loan_events.values_list("pk", flat=True)), before)

    def test_mismatched_total_or_second_loan_failure_rolls_back_everything(self):
        self.make_batch()
        before = list(m.PawnLoanEvent.objects.values_list("pk", flat=True))
        self.facts["total_received"] = "12982.55"
        with self.assertRaisesMessage(ValueError, "Combined collection"):
            self.preview()
        self.assertEqual(list(m.PawnLoanEvent.objects.values_list("pk", flat=True)), before)
        self.facts["total_received"] = "12982.56"
        _, token = self.preview()
        from apps.tenant_apps.loans.services import recorded_batch_corrections as service
        original = service._run
        calls = []
        def fail_second(*args, **kwargs):
            calls.append(args[0].pk)
            if len(calls) == 2:
                raise ValueError("Second member failed")
            return original(*args, **kwargs)
        with patch.object(service, "_run", side_effect=fail_second):
            with self.assertRaisesMessage(ValueError, "Second member failed"):
                self.record(token)
        self.assertEqual(list(m.PawnLoanEvent.objects.values_list("pk", flat=True)), before)

    def test_requires_complete_membership_and_checked_source(self):
        self.make_batch()
        original = deepcopy(self.facts)
        for rows in (self.facts["loans"][:1], self.facts["loans"]*2,
                     [dict(loan_id=999999, correction=None), self.facts["loans"][1]]):
            self.facts = dict(original, loans=rows)
            with self.assertRaises(ValueError):
                self.preview()
        self.facts = dict(original, confirmed_unchanged=False)
        with self.assertRaisesMessage(ValueError, "Confirm"):
            self.preview()

    def test_single_loan_route_cannot_change_shared_collection(self):
        self.make_batch()
        change = dict(self.facts["loans"][0]["correction"], reason="Missing page", request_key=uuid4().hex)
        review, token = preview_correction(self.loans[0].pk, actor=self.actor, data=change)
        self.assertFalse(token)
        self.assertIn("combined release batch", " ".join(review["blockers"]))

    def test_authority_and_restricted_role_workspace_isolation(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company
        from apps.tenancy.context import workspace_context, without_workspace_context
        self.make_batch()
        stranger = get_user_model().objects.create_user(username="batch-stranger")
        with self.assertRaises(PermissionDenied):
            preview_batch_correction(self.batch.pk, actor=stranger, data=self.facts)
        other = Company.objects.create(name="Other batch", schema_name="other-batch", owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("batch_correct_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            _, token = self.preview()
            self.record(token)
            connection.check_constraints()
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.PawnReleaseBatch.objects.filter(pk=self.batch.pk).exists())
                self.assertFalse(m.PawnLoanEvent.objects.filter(loan_id=self.loans[0].pk).exists())
                with self.assertRaises(ValueError):
                    self.preview()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_review_tampering_confirmation_and_changed_retry_are_refused(self):
        self.make_batch()
        _, token = self.preview()
        with self.assertRaisesMessage(ValueError, "Confirm"):
            record_batch_correction(self.batch.pk, actor=self.actor, data=self.facts, review_token=token)
        with self.assertRaisesMessage(ValueError, "missing or expired"):
            self.record(token + "tampered")
        original = self.facts["reference"]
        self.facts["reference"] = "Changed source"
        with self.assertRaisesMessage(ValueError, "changed"):
            self.record(token)
        self.facts["reference"] = original
        self.record(token)
        self.facts["reference"] = "Changed retry"
        with self.assertRaisesMessage(ValueError, "different facts"):
            self.record(token)

    def test_sibling_change_invalidates_older_review_and_corrections_can_repeat(self):
        self.make_batch()
        old_facts = deepcopy(self.facts)
        _, old_token = self.preview()
        self.facts["loans"][1]["correction"] = None
        self.facts.update(total_received="15059.28", request_key=uuid4().hex)
        _, token = self.preview()
        self.record(token)
        self.facts = old_facts
        with self.assertRaisesMessage(ValueError, "changed"):
            self.record(old_token)
        self.facts["loans"][0]["correction"] = None
        self.facts["request_key"] = uuid4().hex
        _, token = self.preview()
        self.record(token)
        self.assertEqual(batch_financial_review(self.batch)["total"], Decimal("12982.56"))

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_http_review_confirmation_retry_and_projected_detail(self):
        self.make_batch()
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:release_batch_correct_history", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": self.batch.pk})
        self.assertContains(client.get(url), "Review release batch correction")
        standalone = reverse("workspace_loans:pawn_loan_correct_paper_history", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loans[0].pk})
        self.assertRedirects(client.get(standalone), url)
        post = {k: v for k, v in self.facts.items() if k != "loans"}
        post.update(action="preview", changed_loans=[str(loan.pk) for loan in self.loans])
        for row in self.facts["loans"]:
            prefix = f"loan_{row['loan_id']}-"
            for key, value in row["correction"].items():
                if key == "settlement":
                    post.update({prefix+"settlement_"+k: v for k, v in value.items()})
                else:
                    post[prefix+key] = value if value is not None else ""
        response = client.post(url, post)
        self.assertEqual(response.context["form"].errors, {})
        self.assertTrue(response.context["review"], [row["form"].errors for row in response.context["rows"]])
        self.assertContains(response, "Check the combined collection")
        import os
        from pathlib import Path
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path("/qa/batch-correction-review.html").write_bytes(response.content)
        post.update(action="confirm", confirmed=True, review_token=response.context["form"].data["review_token"])
        self.assertEqual(client.post(url, post).status_code, 302)
        self.assertEqual(client.post(url, post).status_code, 302)
        detail = client.get(reverse("workspace_loans:release_batch_detail", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": self.batch.pk}))
        self.assertContains(detail, "12,982.56")
        self.assertContains(detail, "17,136")
        self.assertContains(detail, "6,491.28", count=2)
        listing = client.get(reverse("workspace_loans:release_batch_list", kwargs={"workspace_slug": self.tenant.slug}))
        self.assertContains(listing, "12,982.56")
        self.assertContains(listing, "Reviewed correction; original 17,136")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_paper_batch_csv_and_memo_show_current_cash_and_original_handover(self):
        self.make_batch(paper=True)
        self.facts["reference"] = "=Checked paper page"
        _, token = self.preview()
        self.record(token)
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        response = client.get(reverse("workspace_loans:paper_closure_csv", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": self.batch.pk}))
        self.assertContains(response, "6491.28", count=2)
        self.assertContains(response, "Settlement correction")
        self.assertContains(response, "Individual payer", count=2)
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        import fitz
        import os
        from pathlib import Path
        pdf = PawnLoanDocumentService.render_release_memo(self.batch.lines.first().release).pdf
        document = fitz.open(stream=pdf, filetype="pdf")
        text = " ".join(" ".join(page.get_text().split()) for page in document)
        self.assertIn("6,491.28", text)
        self.assertIn("Historical settlement correction", text)
        self.assertIn(f"batch #{self.batch.pk}", text)
        self.assertIn("Separate receipts on page 8", text)
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path("/qa/corrected-batch-release.pdf").write_bytes(pdf)
            for index, page in enumerate(document):
                page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(f"/qa/corrected-batch-release-{index}.png")


class BatchCorrectionConcurrencyTests(receipt_tests.CorrectionConcurrencyTests):
    def setUp(self):
        super().setUp()
        from apps.tenancy.context import workspace_context
        with workspace_context(self.tenant.pk):
            quote = preview_release_batch(workspace=self.tenant, actor=self.actor, loan_ids=[self.loan.pk])
            self.batch = complete_release_batch(workspace=self.tenant, actor=self.actor, request_key=uuid4(),
                quote_token=quote["quote_token"], paid_by="Borrower", payment_reference="Paper total", payment_confirmed=True,
                collectors=[dict(loan_id=self.loan.pk, collector_is_borrower=True, handover_confirmed=True)])
            child = dict(self.submit["data"], settlement=dict(cash_received="8200", cash_paid="0", interest_offset="0",
                reference="Checked closure", confirmed_unchanged=True))
            data = dict(total_received="8200", reference="Combined paper receipt", reason="Missing receipt",
                request_key=uuid4().hex, confirmed_unchanged=True, loans=[dict(loan_id=self.loan.pk, correction=child)])
            _, token = preview_batch_correction(self.batch.pk, actor=self.actor, data=data)
            self.submit = dict(batch_id=self.batch.pk, actor=self.actor, data=data, review_token=token, confirmed=True)

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
                    return record_batch_correction(**data)
            except ValueError:
                return "stale"
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(submit, submissions))

    def test_competing_reviews_cannot_both_post(self):
        from apps.tenancy.context import workspace_context
        other = deepcopy(self.submit)
        other["data"].update(request_key=uuid4().hex, reference="Different paper page")
        with workspace_context(self.tenant.pk):
            _, other["review_token"] = preview_batch_correction(self.batch.pk, actor=self.actor, data=other["data"])
        result = self.race([self.submit, other])
        self.assertEqual(result.count(True), 1)
        self.assertEqual(result.count("stale"), 1)


class MixedOriginBatchCorrectionTests(batch_tests.ReleaseBatchTests):
    make_snapshot = fixtures.RecordedOriginationTests.make_snapshot
    prepare_history = history.RecordedHistoryTests.prepare_history
    admit = history.RecordedHistoryTests.admit

    def test_native_members_remain_unchanged_and_cannot_use_paper_correction(self):
        self.actor = self.owner
        self.prepare_history()
        paper = self.admit()[0]
        self.loans.append(paper)
        quote = preview_release_batch(workspace=self.tenant, actor=self.actor, loan_ids=[loan.pk for loan in self.loans])
        batch = complete_release_batch(workspace=self.tenant, actor=self.actor, request_key=uuid4(),
            quote_token=quote["quote_token"], paid_by="Family", payment_reference="Combined", payment_confirmed=True,
            collectors=[dict(loan_id=loan.pk, collector_is_borrower=True, handover_confirmed=True) for loan in self.loans])
        child = dict(operation="ADD", target=None, date=self.today.isoformat(), amount="2000", reference="Missing receipt",
            before=None, settlement=dict(cash_received="8200", cash_paid="0", interest_offset="0",
                reference="Checked closure", confirmed_unchanged=True))
        data = dict(total_received=str(batch.total_amount-2000), reference="Checked combined receipt", reason="Missing page",
            request_key=uuid4().hex, confirmed_unchanged=True,
            loans=[dict(loan_id=loan.pk, correction=child if loan == paper else None) for loan in self.loans])
        originals = list(m.PawnLoanEvent.objects.exclude(loan=paper).values_list("pk", "payload_fingerprint"))
        _, token = preview_batch_correction(batch.pk, actor=self.actor, data=data)
        record_batch_correction(batch.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(list(m.PawnLoanEvent.objects.exclude(loan=paper).values_list("pk", "payload_fingerprint")), originals)
        data["loans"][0]["correction"] = child
        with self.assertRaisesMessage(ValueError, "admitted"):
            preview_batch_correction(batch.pk, actor=self.actor, data=data)
        data["loans"][0]["correction"] = None
        from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
        native_release = batch.lines.get(release__loan=self.loans[0]).release
        reverse_pawn_loan_event(native_release.loan_event_id, actor=self.actor, reason="Mistaken native handover")
        financial = batch_financial_review(batch)
        self.assertTrue(financial["reversed"])
        self.assertEqual(financial["total"], Decimal(data["total_received"]))
        with self.assertRaisesMessage(ValueError, "reversed or incomplete"):
            preview_batch_correction(batch.pk, actor=self.actor, data=data)
