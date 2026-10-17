"""Issued identity, preparation correction, immutable history and ticket print gates."""

from dataclasses import replace
from io import BytesIO
from uuid import uuid4

import fitz
from django.db import connection, transaction, DatabaseError
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.forms import PawnDraftForm
from apps.tenant_apps.loans.filters import PawnLoanFilter
from apps.tenant_apps.loans.services import (
    pawn_drafts as drafts,
    pawn_lifecycle as lifecycle,
)
from apps.tenant_apps.loans.services import loan_workflow as workflow
from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
from . import test_origination_review as fixtures, test_draft_submissions as submissions


class DelayedNumberingTests(fixtures.OriginationReviewTests):
    def test_product_can_change_before_issue_and_is_locked_after_reopening(self):
        loan = self.draft()
        product = m.LoanProductVersion.objects.get(pk=self.product_version.pk)
        product.pk = None
        product.product = m.LoanProduct.objects.create(
            workspace=self.tenant,
            code="PREPARATION-ALTERNATE",
            name="Alternate preparation product",
        )
        product.version += 1
        product.save(force_insert=True)
        values = submissions.command(self)
        item = loan.collateral_items.get()
        command = drafts.UpdatePawnDraftCommand(
            borrower_id=loan.borrower_id,
            principal_amount=values.principal_amount,
            monthly_interest_rate=values.monthly_interest_rate,
            loan_date=loan.loan_date,
            tenure_months=3,
            collateral=(replace(values.collateral[0], collateral_item_id=item.pk),),
            product_version_id=product.pk,
        )
        edited = drafts.update_pawn_draft(loan.pk, command, actor=self.owner)
        self.assertEqual(edited.product_version_id, product.pk)
        self.assertIsNone(edited.loan_number)
        lifecycle.approve_pawn_loan(loan.pk, actor=self.owner)
        lifecycle.reopen_pawn_loan(loan.pk, actor=self.owner, reason="Check terms")
        with self.assertRaisesMessage(drafts.PawnDraftError, "issued number"):
            drafts.update_pawn_draft(
                loan.pk,
                replace(command, product_version_id=self.product_version.pk),
                actor=self.owner,
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoan.objects.filter(pk=loan.pk).update(
                product_version_id=self.product_version.pk
            )

    def test_exhausted_series_cannot_issue_and_keeps_preparation_unapproved(self):
        loan = self.draft()
        seq = self.series.number_sequences.get(document_kind="PAWN_LOAN")
        type(seq).objects.filter(pk=seq.pk).update(next_number=seq.maximum_number + 1)
        with self.assertRaisesMessage(ValueError, "exhausted"):
            lifecycle.approve_pawn_loan(loan.pk, actor=self.owner)
        loan.refresh_from_db()
        self.assertIsNone(loan.loan_number)
        self.assertEqual(loan.state, "DRAFT")
        self.assertFalse(loan.approval_snapshots.exists())

    def test_downgrade_refuses_retained_unnumbered_preparations(self):
        from importlib import import_module
        from types import SimpleNamespace

        loan = self.draft()
        guard = import_module(
            "apps.tenant_apps.loans.migrations.0094_number_at_approval"
        ).require_numbered_rows
        with self.assertRaisesMessage(RuntimeError, "unnumbered preparations"):
            guard(None, SimpleNamespace(connection=connection))
        lifecycle.approve_pawn_loan(loan.pk, actor=self.owner)
        guard(None, SimpleNamespace(connection=connection))

    def test_historical_range_and_original_claim_do_not_rewind_approval_numbering(self):
        from apps.tenant_apps.loans.services.license_series import (
            reserve_sequence_through,
        )
        from apps.tenant_apps.loans.services.recorded_numbers import claim_number

        reserve_sequence_through(
            series=self.series,
            document_kind="PAWN_LOAN",
            last_used_number=5000,
            evidence_reference="Fictional original register through 5000",
            actor=self.owner,
        )
        first, second = self.draft(), self.draft()
        approval = lifecycle.approve_pawn_loan(second.pk, actor=self.owner)
        self.assertTrue(approval.payload["loan_number"].endswith("05001"))
        seq = self.series.number_sequences.get(document_kind="PAWN_LOAN")
        with transaction.atomic():
            claim_number(
                self.series, f"{seq.prefix}00001", kind="PAWN_LOAN", actor=self.owner
            )
        seq.refresh_from_db()
        self.assertEqual(seq.next_number, 5002)
        first.refresh_from_db()
        self.assertIsNone(first.loan_number)

    def test_failed_combined_payout_rolls_back_number_before_retry(self):
        from unittest.mock import patch

        loan = self.draft()
        _, token = workflow.make_review(loan, actor=self.owner)
        with patch(
            "apps.tenant_apps.loans.services.loan_workflow.disburse_pawn_loan",
            side_effect=ValueError("Failed payout"),
        ):
            with self.assertRaisesMessage(ValueError, "Failed payout"):
                workflow.review_and_disburse(
                    loan.pk,
                    actor=self.owner,
                    effective_date=loan.loan_date,
                    token=token,
                )
        loan.refresh_from_db()
        self.assertIsNone(loan.loan_number)
        self.assertEqual(loan.state, "DRAFT")
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertFalse(loan.loan_events.exists())
        self.assertEqual(
            self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1
        )
        workflow.review_and_disburse(
            loan.pk, actor=self.owner, effective_date=loan.loan_date, token=token
        )
        loan.refresh_from_db()
        self.assertTrue(loan.loan_number.endswith("00001"))

    @classmethod
    def get_test_schema_name(cls):
        return "delayed-numbering"

    def draft(self):
        return drafts.create_pawn_draft(submissions.command(self), actor=self.owner)

    def test_preparation_references_and_approval_ticket_gate(self):
        loan = self.draft()
        self.assertIsNone(loan.loan_number)
        self.assertEqual(str(loan), f"Draft #{loan.pk}")
        self.assertEqual(
            self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1
        )
        matches = PawnLoanFilter(
            {"q": loan.display_reference},
            queryset=m.PawnLoan.objects.all(),
            workspace=self.tenant,
        )
        self.assertEqual(list(matches.qs), [loan])
        from apps.tenant_apps.loans.selectors.party_history import (
            get_party_pawn_loan_history_summary,
        )

        history = get_party_pawn_loan_history_summary(loan.borrower)
        self.assertEqual(history["active_loans"][0].loan_id, loan.display_reference)
        from openpyxl import load_workbook
        from apps.tenant_apps.loans.services.directory_export import (
            export_loan_directory,
        )

        workbook = load_workbook(
            BytesIO(
                export_loan_directory(
                    workspace=self.tenant,
                    loan_filter=matches,
                    as_of_date=loan.loan_date,
                )
            )
        )
        rows = list(workbook["Loans"].values)
        self.assertEqual(rows[1][:2], ("Preparation", loan.display_reference))
        path = reverse(
            "workspace_loans:pawn_loan_ticket_pdf", args=[self.tenant.slug, loan.pk]
        )
        self.assertEqual(self.client.get(path).status_code, 409)
        self.assertFalse(m.LoanDocumentIssue.objects.exists())
        detail = self.client.get(
            reverse(
                "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, loan.pk]
            )
        )
        self.assertContains(detail, loan.display_reference)
        self.assertNotContains(detail, "Print draft preview")
        self.assertNotContains(detail, 'id="print-loan-ticket-title"')
        self.assertNotContains(
            detail, "Wrong register or product? Review a replacement"
        )

    def test_ticket_prints_only_permanent_number_after_approval_before_payout(self):
        loan = self.draft()
        draft_reference = loan.display_reference
        lifecycle.approve_pawn_loan(loan.pk, actor=self.owner)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "APPROVED")
        self.assertTrue(loan.loan_number)
        self.assertFalse(loan.loan_events.exists())
        result = PawnLoanDocumentService.render_loan_ticket(loan)
        with fitz.open(stream=result.pdf, filetype="pdf") as pdf:
            text = "".join(page.get_text() for page in pdf)
        self.assertIn(loan.loan_number, text)
        self.assertNotIn(draft_reference, text)
        detail = self.client.get(
            reverse(
                "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, loan.pk]
            )
        )
        self.assertContains(detail, 'id="print-loan-ticket-title"')
        path = reverse(
            "workspace_loans:pawn_loan_ticket_pdf", args=[self.tenant.slug, loan.pk]
        )
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        lifecycle.reopen_pawn_loan(loan.pk, actor=self.owner, reason="Correct draft")
        self.assertEqual(self.client.get(path).status_code, 409)

    def test_first_approval_order_and_reopen_cancel_keep_issued_identity(self):
        first, second = self.draft(), self.draft()
        approved_second = lifecycle.approve_pawn_loan(second.pk, actor=self.owner)
        approved_first = lifecycle.approve_pawn_loan(first.pk, actor=self.owner)
        self.assertTrue(approved_second.payload["loan_number"].endswith("00001"))
        self.assertTrue(approved_first.payload["loan_number"].endswith("00002"))
        lifecycle.reopen_pawn_loan(
            second.pk, actor=self.owner, reason="Correct preparation"
        )
        approval = lifecycle.approve_pawn_loan(second.pk, actor=self.owner)
        self.assertEqual(
            approval.payload["loan_number"], approved_second.payload["loan_number"]
        )
        lifecycle.cancel_pawn_loan(
            first.pk, actor=self.owner, reason="Borrower withdrew"
        )
        self.assertEqual(
            self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 3
        )
        self.assertEqual(
            m.PawnLoan.objects.get(pk=first.pk).loan_number,
            approved_first.payload["loan_number"],
        )

    def test_scope_edit_keeps_identity_and_items_but_invalidates_old_review(self):
        loan, _, _, _ = self.start_review()
        _, token = workflow.make_review(loan, actor=self.owner)
        _, target = self._configured_setup()
        for seq in target.number_sequences.all():
            seq.prefix = "NEW-" + seq.prefix
            seq.save(update_fields=["prefix"])
        original_item = loan.collateral_items.get()
        photos = list(original_item.photos.values())
        values = submissions.command(self)
        update = drafts.UpdatePawnDraftCommand(
            borrower_id=loan.borrower_id,
            principal_amount=values.principal_amount,
            monthly_interest_rate=values.monthly_interest_rate,
            loan_date=loan.loan_date,
            tenure_months=3,
            collateral=(
                replace(values.collateral[0], collateral_item_id=original_item.pk),
            ),
            series_id=target.pk,
            product_version_id=self.product_version.pk,
        )
        edited = drafts.update_pawn_draft(loan.pk, update, actor=self.owner)
        self.assertEqual(edited.pk, loan.pk)
        self.assertIsNone(edited.loan_number)
        self.assertEqual(edited.series_id, target.pk)
        self.assertEqual(edited.collateral_items.get().pk, original_item.pk)
        self.assertEqual(list(edited.collateral_items.get().photos.values()), photos)
        audit = edited.change_log.order_by("pk").last().metadata
        self.assertEqual(audit["before"]["series_id"], self.series.pk)
        self.assertEqual(audit["after"]["series_id"], target.pk)
        self.assertFalse(
            PawnDraftForm(workspace=self.tenant, instance=edited)
            .fields["series"]
            .disabled
        )
        with self.assertRaisesMessage(ValueError, "changed"):
            workflow.review_and_disburse(
                loan.pk, actor=self.owner, effective_date=loan.loan_date, token=token
            )
        _, token = workflow.make_review(edited, actor=self.owner)
        workflow.review_and_disburse(
            edited.pk, actor=self.owner, effective_date=edited.loan_date, token=token
        )
        edited.refresh_from_db()
        self.assertTrue(edited.loan_number.startswith("NEW-"))
        self.assertEqual(
            self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1
        )
        self.assertEqual(
            target.number_sequences.get(document_kind="PAWN_LOAN").next_number, 2
        )

    def test_grandfathered_numbered_review_is_not_reassigned(self):
        from apps.tenant_apps.loans.services.number_allocation import (
            allocate_pawn_loan_number,
        )

        loan, path, _, _ = self.start_review()
        loan.loan_number = allocate_pawn_loan_number(
            series=self.series, actor=self.owner
        ).value
        loan.save(update_fields=["loan_number"])
        page = self.client.get(path)
        self.assertEqual(self.confirm(path, page).status_code, 302)
        self.assertEqual(self.confirm(path, page).status_code, 302)
        loan.refresh_from_db()
        self.assertTrue(loan.loan_number.endswith("00001"))
        self.assertEqual(
            self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 2
        )

    def test_exact_recovery_preserves_multiple_unnumbered_drafts(self):
        first, second = self.draft(), self.draft()
        original = self.export()
        self.empty()
        self.assertTrue(self.restore(commit=True)["committed"])
        self.assertEqual(
            list(m.PawnLoan.objects.order_by("pk").values_list("pk", "loan_number")),
            [(first.pk, None), (second.pk, None)],
        )
        restored = self.export()
        self.assertEqual(original["tables"], restored["tables"])

    def test_restricted_sql_cannot_publish_without_number_or_reassign_issued_identity(
        self,
    ):
        loan = self.draft()
        role = connection.ops.quote_name("number_stage_" + uuid4().hex)
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
            for state in ("APPROVED", "ACTIVE", "CLOSED"):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoan.objects.filter(pk=loan.pk).update(state=state)
            lifecycle.approve_pawn_loan(loan.pk, actor=self.owner)
            loan.refresh_from_db()
            lifecycle.reopen_pawn_loan(
                loan.pk, actor=self.owner, reason="Correct facts"
            )
            for value in (None, "", "OTHER-NUMBER"):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoan.objects.filter(pk=loan.pk).update(loan_number=value)
            self.assertTrue(
                PawnDraftForm(workspace=self.tenant, instance=loan)
                .fields["series"]
                .disabled
            )
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
