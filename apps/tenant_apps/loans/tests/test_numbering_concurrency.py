"""Real transactions issue unique approval numbers and roll back failed payout."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import pawn_drafts, pawn_lifecycle, loan_workflow
from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
from . import test_pawn_draft_ui as fixtures, test_draft_submissions as submissions


class NumberingConcurrencyTests(TransactionTestCase):
    def test_paper_original_claim_and_new_approval_share_reserved_register_safely(self):
        from apps.tenant_apps.loans.services.license_series import (
            reserve_sequence_through,
        )
        from apps.tenant_apps.loans.services.completed_payouts import (
            completed_payout_defaults,
            preview_completed_payout,
            record_completed_payout,
        )
        from apps.tenant_apps.loans.services.recorded_history import (
            new_recording_intent,
        )

        current, paper = self.loans
        with workspace_context(self.tenant.pk):
            reserve_sequence_through(
                series=self.series,
                document_kind="PAWN_LOAN",
                last_used_number=5000,
                evidence_reference="Fictional historical book through 5000",
                actor=self.owner,
            )
            prefix = m.LoanNumberSequence.objects.get(
                series=self.series, document_kind="PAWN_LOAN"
            ).prefix
            values = completed_payout_defaults(paper) | dict(
                number=prefix + "00001",
                source_reference="Historical book 1",
                reason="Original payout already completed",
                confirmed_rule=True,
            )
            intent = new_recording_intent(
                workspace=self.tenant, actor=self.owner, draft_id=paper.pk
            )
            _, review, _ = preview_completed_payout(
                workspace=self.tenant,
                actor=self.owner,
                loan_id=paper.pk,
                values=values,
                intent_token=intent,
            )

        def approve():
            return pawn_lifecycle.approve_pawn_loan(
                current.pk, actor=self.owner
            ).payload["loan_number"]

        def record():
            loan, _ = record_completed_payout(
                workspace=self.tenant,
                actor=self.owner,
                loan_id=paper.pk,
                values=values,
                intent_token=intent,
                review_token=review,
                confirmed=True,
            )
            return loan.loan_number

        results = self.race([approve, record])
        self.assertEqual(set(results), {prefix + "05001", prefix + "00001"})
        with workspace_context(self.tenant.pk):
            self.assertEqual(
                m.LoanNumberSequence.objects.get(
                    series=self.series, document_kind="PAWN_LOAN"
                ).next_number,
                5002,
            )

    def test_populated_numbering_migration_preserves_issued_rows_and_counter(self):
        from django.db.migrations.executor import MigrationExecutor
        from apps.tenancy.testing import historical_migration_database
        from apps.tenant_apps.loans.services.number_allocation import (
            allocate_pawn_loan_number,
        )

        with workspace_context(self.tenant.pk):
            for loan in self.loans:
                loan.loan_number = allocate_pawn_loan_number(
                    series=self.series, actor=self.owner
                ).value
                loan.save(update_fields=["loan_number"])
            sequences = list(m.LoanNumberSequence.objects.all())
        membership = Membership.objects.get(company=self.tenant, user=self.owner)
        old = [("loans", "0093_loan_entry_preference")]
        with historical_migration_database(
            self, old, [membership, *self.loans, *sequences]
        ) as (target, old_apps):
            original = list(
                old_apps.get_model("loans", "PawnLoan")
                .objects.using(target.alias)
                .order_by("pk")
                .values()
            )
            counters = list(
                old_apps.get_model("loans", "LoanNumberSequence")
                .objects.using(target.alias)
                .order_by("pk")
                .values()
            )
            new = [("loans", "0094_number_at_approval")]
            executor = MigrationExecutor(target)
            executor.migrate(new)
            apps = executor.loader.project_state(new).apps
            model = apps.get_model("loans", "PawnLoan")
            self.assertEqual(
                list(model.objects.using(target.alias).order_by("pk").values()),
                original,
            )
            self.assertEqual(
                list(
                    apps.get_model("loans", "LoanNumberSequence")
                    .objects.using(target.alias)
                    .order_by("pk")
                    .values()
                ),
                counters,
            )
            self.assertTrue(model._meta.get_field("loan_number").null)

    _configured_setup = fixtures.PawnDraftUiTests._configured_setup

    def setUp(self):
        self.owner = get_user_model().objects.create_user(
            username="numbering-race-" + uuid4().hex
        )
        self.tenant = Company.objects.create(
            name="Approval numbering",
            schema_name=uuid4().hex,
            owner=self.owner,
            creator=self.owner,
        )
        Membership.objects.create(
            user=self.owner,
            company=self.tenant,
            role=Role.objects.get_or_create(name="Owner")[0],
        )
        self.clock = patch(
            "django.utils.timezone.localdate", return_value=date(2026, 7, 18)
        )
        self.clock.start()
        self.addCleanup(self.clock.stop)
        with workspace_context(self.tenant.pk):
            self.party = Party.objects.create(display_name="Approval customer")
            self.product_version = _seed_default_loan_products()[0]
            m.LoanProductVersion.objects.filter(pk=self.product_version.pk).update(
                status="ACTIVE"
            )
            self.license, self.series = self._configured_setup()
            self.loans = [
                pawn_drafts.create_pawn_draft(
                    submissions.command(self), actor=self.owner
                )
                for _ in range(2)
            ]

    def race(self, calls):
        barrier = Barrier(2)

        def execute(call):
            try:
                with workspace_context(self.tenant.pk):
                    barrier.wait(timeout=15)
                    return call()
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            return list(executor.map(execute, calls))

    def test_simultaneous_approvals_receive_distinct_permanent_numbers(self):
        def approve(loan):
            return lambda: pawn_lifecycle.approve_pawn_loan(
                loan.pk, actor=self.owner
            ).payload["loan_number"]

        results = self.race([approve(loan) for loan in self.loans])
        self.assertEqual(len(set(results)), 2)
        with workspace_context(self.tenant.pk):
            self.assertEqual(
                m.LoanNumberSequence.objects.get(
                    series=self.series, document_kind="PAWN_LOAN"
                ).next_number,
                3,
            )
            self.assertEqual(m.PawnLoanApprovalSnapshot.objects.count(), 2)

    def test_simultaneous_same_combined_confirmation_returns_one_number_and_payout(
        self,
    ):
        loan = self.loans[0]
        with workspace_context(self.tenant.pk):
            loan_workflow.set_loan_workflow(actor=self.owner, mode="SIMPLE")
            _, token = loan_workflow.make_review(loan, actor=self.owner)

        def confirm():
            result = loan_workflow.review_and_disburse(
                loan.pk, actor=self.owner, effective_date=loan.loan_date, token=token
            )
            return result.loan_event.pk

        outcomes = self.race([confirm, confirm])
        self.assertEqual(outcomes[0], outcomes[1])
        with workspace_context(self.tenant.pk):
            self.assertEqual(
                m.PawnLoanEvent.objects.filter(event_kind="DISBURSAL").count(), 1
            )
            self.assertEqual(m.PawnLoanApprovalSnapshot.objects.count(), 1)
            self.assertEqual(
                m.LoanNumberSequence.objects.get(
                    series=self.series, document_kind="PAWN_LOAN"
                ).next_number,
                2,
            )
            self.assertIsNone(m.PawnLoan.objects.get(pk=self.loans[1].pk).loan_number)
