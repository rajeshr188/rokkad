"""Reviewed preparation replacement preserves source identity, media and money boundaries."""

from uuid import uuid4
from unittest.mock import patch

from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.draft_replacement import (
    preview_draft_replacement,
    replace_draft,
)
from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number
from . import test_origination_review as fixtures


class DraftReplacementTests(fixtures.OriginationReviewTests):
    def test_replacement_can_be_reviewed_paid_and_closed_without_posting_original(self):
        loan, _, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        replacement, _ = replace_draft(
            loan.pk, actor=self.owner, values=values, token=token, confirmed=True
        )
        path = reverse(
            "workspace_loans:pawn_loan_review_disburse",
            args=[self.tenant.slug, replacement.pk],
        )
        self.assertEqual(self.confirm(path, self.client.get(path)).status_code, 302)
        detail = reverse(
            "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, replacement.pk]
        )
        self.assertContains(self.client.get(detail), "data-close-release-action")
        path = reverse("workspace_loans:loan_closing_create", args=[self.tenant.slug])
        page = self.client.get(path, {"purpose": "CURRENT", "loans": [replacement.pk]})
        payload = dict(
            purpose="CURRENT",
            loans=[replacement.pk],
            request_key=str(uuid4()),
            settlement_amount=str(page.context["quote"].minimum_settlement),
            interest_concession="0",
            confirm_collateral_handoff="on",
        )
        self.assertEqual(self.client.post(path, payload).status_code, 302)
        self.assertEqual(self.client.post(path, payload).status_code, 302)
        loan.refresh_from_db()
        replacement.refresh_from_db()
        self.assertEqual((loan.state, replacement.state), ("CANCELLED", "CLOSED"))
        self.assertFalse(loan.loan_events.exists())
        self.assertEqual(
            replacement.loan_events.filter(event_kind="DISBURSAL").count(), 1
        )
        self.assertEqual(replacement.releases.count(), 1)

    def replacement(self):
        loan, _, _, _ = self.start_review()
        _, target = self._configured_setup()
        for sequence in target.number_sequences.all():
            sequence.prefix = "R-" + sequence.prefix
            sequence.save(update_fields=["prefix"])
        values = dict(
            series_id=target.pk,
            product_version_id=self.product_version.pk,
            loan_date=loan.loan_date,
            tenure_months=loan.tenure_months,
            reason="Wrong register selected",
            request_key=str(uuid4()),
        )
        return loan, target, values

    def test_replacement_preserves_original_number_photos_and_atomic_retry(self):
        loan, target, values = self.replacement()
        old_number = loan.loan_number
        item_id = loan.collateral_items.get().pk
        source_photo = loan.collateral_items.get().photos.get()
        with source_photo.file.open("rb") as stream:
            original = stream.read()
        preview, token = preview_draft_replacement(
            loan.pk, actor=self.owner, values=values
        )
        self.assertEqual(m.PawnLoan.objects.count(), 1)
        replacement, created = replace_draft(
            loan.pk, actor=self.owner, values=values, token=token, confirmed=True
        )
        loan.refresh_from_db()
        self.assertTrue(created)
        self.assertEqual((loan.state, loan.loan_number), ("CANCELLED", old_number))
        self.assertEqual(
            (replacement.state, replacement.series_id, replacement.loan_number),
            ("DRAFT", target.pk, preview["number"]),
        )
        self.assertEqual(replacement.collateral_items.get().pk, item_id)
        self.assertFalse(loan.collateral_items.exists())
        self.assertEqual(
            replacement.collateral_items.get().photos.get().pk, source_photo.pk
        )
        for photo in (source_photo, replacement.collateral_items.get().photos.get()):
            with photo.file.open("rb") as stream:
                self.assertEqual(stream.read(), original)
        self.assertEqual(
            replace_draft(
                loan.pk, actor=self.owner, values=values, token=token, confirmed=True
            )[0].pk,
            replacement.pk,
        )
        self.assertEqual(m.PawnLoan.objects.count(), 2)
        self.assertFalse(m.PawnLoanEvent.objects.exists())
        self.assertFalse(m.PawnLoanDisbursalSnapshot.objects.exists())

    def test_changed_number_or_source_requires_review_and_no_cancellation(self):
        loan, target, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        allocate_pawn_loan_number(series=target, actor=self.owner)
        with self.assertRaisesMessage(ValueError, "expected number changed"):
            replace_draft(
                loan.pk, actor=self.owner, values=values, token=token, confirmed=True
            )
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(m.PawnLoan.objects.count(), 1)

    def test_exact_recovery_preserves_preparation_links_media_and_retry(self):
        loan, _, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        replacement, _ = replace_draft(
            loan.pk, actor=self.owner, values=values, token=token, confirmed=True
        )
        original = self.export()
        self.empty()
        self.assertTrue(self.restore(commit=True)["committed"])
        restored = self.export()
        for name in (
            "tables",
            "files",
            "reconciliation",
            "prerequisites",
            "schema",
            "guards_sha256",
        ):
            self.assertEqual(original[name], restored[name], name)
        self.assertEqual(
            replace_draft(
                loan.pk, actor=self.owner, values=values, token=token, confirmed=True
            )[0].pk,
            replacement.pk,
        )

    def test_portable_source_links_do_not_become_destination_loan_links(self):
        from apps.tenant_apps.loans.selectors.correction_guidance import (
            draft_replacement_link,
        )
        from apps.tenant_apps.loans.services.servicing_bundle import _adapt

        loan, _, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        replacement, _ = replace_draft(
            loan.pk, actor=self.owner, values=values, token=token, confirmed=True
        )
        row = replacement.change_log.get(metadata__has_key="draft_replacement_in")
        source = row.metadata["draft_replacement_in"]["source"]
        adapted = _adapt(
            {"source": source}, refs={}, external={}, numbers={}, event_keys={}
        )
        self.assertEqual(adapted["source"], source)
        self.assertEqual(draft_replacement_link(replacement)["other"].pk, loan.pk)
        row.metadata["draft_replacement_in"]["source"]["workspace_id"] += 10000
        row.save(update_fields=["metadata"])
        self.assertIsNone(draft_replacement_link(replacement))

    def test_failed_cancellation_rolls_back_number_new_draft_and_item_movement(self):
        from apps.tenant_apps.loans.services import draft_replacement as service

        loan, target, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        item = loan.collateral_items.get()
        photo = item.photos.get()
        counter = target.number_sequences.get(document_kind="PAWN_LOAN").next_number
        with patch.object(
            service, "cancel_pawn_loan", side_effect=ValueError("Cancellation failed")
        ):
            with self.assertRaisesMessage(ValueError, "Cancellation failed"):
                replace_draft(
                    loan.pk,
                    actor=self.owner,
                    values=values,
                    token=token,
                    confirmed=True,
                )
        self.assertEqual(m.PawnLoan.objects.count(), 1)
        self.assertEqual(
            target.number_sequences.get(document_kind="PAWN_LOAN").next_number, counter
        )
        item.refresh_from_db()
        self.assertEqual(item.loan_id, loan.pk)
        self.assertEqual(item.photos.get().pk, photo.pk)
        self.assertTrue(photo.file.storage.exists(photo.file.name))
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")

    def test_posted_history_and_foreign_register_cannot_use_preparation_replacement(
        self,
    ):
        loan, _, values = self.replacement()
        with self.assertRaisesMessage(ValueError, "in this Workspace"):
            preview_draft_replacement(
                loan.pk, actor=self.owner, values=values | {"series_id": 99999999}
            )
        from apps.tenant_apps.loans.services import (
            approve_pawn_loan,
            disburse_pawn_loan,
        )

        approve_pawn_loan(loan.pk, actor=self.owner)
        disburse_pawn_loan(loan.pk, actor=self.owner, effective_date=loan.loan_date)
        with self.assertRaisesMessage(ValueError, "unposted preparation"):
            preview_draft_replacement(loan.pk, actor=self.owner, values=values)

    def test_restricted_runtime_can_replace_but_cannot_cross_workspaces(self):
        from django.db import connection, transaction, DatabaseError
        from apps.orgs.models import Company

        loan, _, values = self.replacement()
        foreign = Company.objects.create(
            name="Foreign replacement workspace",
            schema_name=uuid4().hex,
            owner=self.owner,
            creator=self.owner,
        )
        role = connection.ops.quote_name("draft_replacement_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}"
            )
            cursor.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}"
            )
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            _, token = preview_draft_replacement(
                loan.pk, actor=self.owner, values=values
            )
            replacement, created = replace_draft(
                loan.pk, actor=self.owner, values=values, token=token, confirmed=True
            )
            self.assertTrue(created)
            self.assertEqual(replacement.workspace_id, self.tenant.pk)
            self.assertFalse(m.PawnLoan.objects.filter(workspace=foreign).exists())
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoan.objects.filter(pk=replacement.pk).update(workspace=foreign)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_browser_review_then_confirm_keeps_source_and_retries(self):
        loan, _, values = self.replacement()
        path = reverse(
            "workspace_loans:pawn_loan_replace_draft", args=[self.tenant.slug, loan.pk]
        )
        self.assertContains(self.client.get(path), "Replace mistaken preparation draft")
        payload = dict(
            series=values["series_id"],
            product_version=values["product_version_id"],
            **{
                key: values[key]
                for key in ("loan_date", "tenure_months", "reason", "request_key")
            },
            action="preview",
        )
        review = self.client.post(path, payload)
        self.assertContains(review, "Expected replacement number")
        payload.update(
            action="confirm",
            confirmed="on",
            review_token=review.context["form"]["review_token"].value(),
        )
        self.assertEqual(self.client.post(path, payload).status_code, 302)
        self.assertEqual(self.client.post(path, payload).status_code, 302)
        self.assertEqual(m.PawnLoan.objects.count(), 2)
        replacement = m.PawnLoan.objects.exclude(pk=loan.pk).get()
        for subject, other in ((loan, replacement), (replacement, loan)):
            page = self.client.get(
                reverse(
                    "workspace_loans:pawn_loan_detail",
                    args=[self.tenant.slug, subject.pk],
                )
            )
            self.assertEqual(page.status_code, 200)
            self.assertContains(page, other.loan_number)

    def test_replacement_review_expires_and_rejects_changed_product(self):
        from django.core import signing
        from apps.tenant_apps.loans.services.draft_replacement import SALT

        loan, _, values = self.replacement()
        _, token = preview_draft_replacement(loan.pk, actor=self.owner, values=values)
        data = signing.loads(token, salt=SALT)
        with patch("django.core.signing.time.time", return_value=1):
            expired = signing.dumps(data, salt=SALT)
        with self.assertRaisesMessage(ValueError, "expired"):
            replace_draft(
                loan.pk, actor=self.owner, values=values, token=expired, confirmed=True
            )
        m.LoanProductVersion.objects.filter(pk=self.product_version.pk).update(
            operational_grace_days=9
        )
        with self.assertRaisesMessage(ValueError, "changed"):
            replace_draft(
                loan.pk, actor=self.owner, values=values, token=token, confirmed=True
            )
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(m.PawnLoan.objects.count(), 1)
