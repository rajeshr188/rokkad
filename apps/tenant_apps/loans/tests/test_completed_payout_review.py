"""Completed facts share one review independently of prior digital approval."""

from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.core.exceptions import PermissionDenied
from django.db import connection

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services import approve_pawn_loan, reopen_pawn_loan
from apps.tenant_apps.loans.services.completed_payouts import (
    preview_completed_payout,
    record_completed_payout,
)
from apps.tenant_apps.loans.services.loan_workflow import make_earlier_payout_review
from apps.tenant_apps.rates.services import withdraw_quote, record_quote
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.party_merge import merge_parties
from . import test_earlier_payout as fixtures


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class CompletedFactReviewTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.EarlierPayoutTests.setup_tenant.__func__)
    make_loan = fixtures.EarlierPayoutTests.make_loan
    setUp = fixtures.EarlierPayoutTests.setUp

    @classmethod
    def get_test_schema_name(cls):
        return "completed-fact-review-ls02"

    def start(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        self.url = reverse(
            "workspace_loans:pawn_loan_record_completed_payout",
            args=[self.tenant.slug, self.loan.pk],
        )
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.post = {
            name: (
                page.context["form"][name].value()
                if page.context["form"][name].value() is not None
                else ""
            )
            for name in page.context["form"].fields
        }
        self.post.update(
            completed_payout_form="1",
            intent_token=page.context["intent_token"],
            action="preview",
            reason="Missed digital payout; original ticket checked",
            confirmed_rule="on",
            reviewed_evidence="on",
        )
        return page

    def approve(self):
        with patch(
            "django.utils.timezone.now", return_value=self.next_day - timedelta(days=1)
        ):
            approval = approve_pawn_loan(self.loan.pk, actor=self.actor)
        reopen_pawn_loan(
            self.loan.pk, actor=self.actor, reason="Recording completed facts"
        )
        self.loan.refresh_from_db()
        return approval

    def preview(self):
        page = self.client.post(self.url, self.post)
        self.assertEqual(page.status_code, 200)
        self.assertIsNotNone(page.context["review"], page.context["form"].errors)
        self.post.update(
            action="confirm",
            review_token=page.context["review_token"],
            confirm_review="on",
        )
        return page

    def test_unapproved_and_approved_drafts_share_two_step_review_and_retry(self):
        approval = self.approve()
        original = deepcopy(approval.payload)
        identity = (
            self.loan.pk,
            self.loan.loan_number,
            self.loan.borrower_id,
            list(self.loan.collateral_items.values_list("pk", flat=True)),
        )
        counters = list(m.LoanNumberSequence.objects.values_list("pk", "next_number"))
        self.start()
        self.assertFalse(self.loan.loan_events.exists())
        page = self.preview()
        self.assertContains(page, "Review before recording")
        self.assertNotContains(page, 'name="reason" maxlength=')
        self.assertFalse(self.loan.loan_events.exists())
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertEqual(
            (
                self.loan.pk,
                self.loan.loan_number,
                self.loan.borrower_id,
                list(self.loan.collateral_items.values_list("pk", flat=True)),
            ),
            identity,
        )
        self.assertEqual(
            list(m.LoanNumberSequence.objects.values_list("pk", "next_number")),
            counters,
        )
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertEqual(self.loan.approval_snapshots.count(), 1)
        self.assertEqual(self.loan.disbursal_snapshot.basis, "RECORDED")
        self.assertIsNone(self.loan.disbursal_snapshot.approval_snapshot_id)
        approval.refresh_from_db()
        self.assertEqual(approval.payload, original)

    def test_unapproved_draft_uses_same_review_without_creating_approval(self):
        self.assertIsNone(self.loan.loan_number)
        page = self.start()
        self.assertTemplateUsed(page, "loans/pawn/completed_payout.html")
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.loan.refresh_from_db()
        self.assertTrue(self.loan.loan_number)

    def test_unnumbered_completed_payout_can_claim_its_actual_issued_number(self):
        self.assertIsNone(self.loan.loan_number)
        self.start()
        self.post["number"] = "PAPER-ORIGINAL-007"
        page = self.preview()
        self.assertContains(page, "PAPER-ORIGINAL-007")
        self.loan.refresh_from_db()
        self.assertIsNone(self.loan.loan_number)
        before = list(m.LoanNumberSequence.objects.values_list("pk", "next_number"))
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.loan_number, "PAPER-ORIGINAL-007")
        self.assertEqual(
            list(m.LoanNumberSequence.objects.values_list("pk", "next_number")), before
        )
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_withdrawn_quote_is_explicitly_reviewed_without_retrospective_approval(
        self,
    ):
        approval = self.approve()
        original = deepcopy(approval.payload)
        withdraw_quote(
            workspace=self.tenant,
            actor=self.actor,
            quote_id=self.quote.pk,
            reason="Original price corrected",
        )
        page = self.start()
        self.assertContains(page, "Corrected or withdrawn")
        self.post["reviewed_evidence"] = ""
        self.assertIsNone(self.client.post(self.url, self.post).context["review"])
        self.post["reviewed_evidence"] = "on"
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.payload, original)
        self.assertEqual(self.loan.approval_snapshots.count(), 1)
        evidence = self.loan.disbursal_snapshots.get().evidence["recording"][
            "draft_source"
        ]["approval_evidence"]
        self.assertEqual(evidence[0]["quotes"][0]["status"], "CORRECTED_OR_WITHDRAWN")

    def test_quote_change_after_preview_rejects_stale_review(self):
        self.approve()
        self.start()
        self.preview()
        withdraw_quote(
            workspace=self.tenant,
            actor=self.actor,
            quote_id=self.quote.pk,
            reason="Changed after review",
        )
        page = self.client.post(self.url, self.post)
        self.assertContains(page, "changed since review")
        self.assertFalse(self.loan.loan_events.exists())
        self.assertFalse(self.loan.disbursal_snapshots.exists())

    def test_prior_day_quote_allowed_at_original_approval_does_not_block_completed_facts(
        self,
    ):
        with patch(
            "django.utils.timezone.now", return_value=self.next_day - timedelta(days=1)
        ):
            record_quote(
                workspace=self.tenant,
                actor=self.actor,
                supersedes_id=self.quote.pk,
                values=dict(
                    rate_source=self.source,
                    metal="Gold",
                    currency="INR",
                    purity="24k",
                    buying_rate=3000,
                    selling_rate=3100,
                    effective_at=self.quote.effective_at - timedelta(days=1),
                    reason="Fictional prior-day source",
                ),
            )
        self.approve()
        with self.assertRaises(ValueError):
            make_earlier_payout_review(self.loan, actor=self.actor)
        self.start()
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)

    def test_changed_deductions_cannot_silently_rewrite_approved_terms(self):
        self.approve()
        self.start()
        self.post.update(document_charge="10", cash_paid="990")
        page = self.client.post(self.url, self.post)
        self.assertContains(page, "Actual terms differ from retained approval")
        self.assertFalse(self.loan.loan_events.exists())

    def test_review_is_actor_bound_and_requires_payout_confirmation(self):
        self.approve()
        self.start()
        self.preview()
        self.post["confirm_review"] = ""
        self.assertContains(self.client.post(self.url, self.post), "Review and confirm")
        self.post["confirm_review"] = "on"
        other = get_user_model().objects.create_user(username="ls02-other")
        Membership.objects.create(
            user=other,
            company=self.tenant,
            role=Role.objects.get_or_create(name="Admin")[0],
        )
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, self.post).status_code, 403)
        self.assertFalse(self.loan.loan_events.exists())

    def test_commands_require_actor_permission_and_evidence_acknowledgment(self):
        self.approve()
        page = self.start()
        values = dict(self.post)
        values["reviewed_evidence"] = False
        with self.assertRaisesMessage(ValueError, "acknowledge"):
            preview_completed_payout(
                workspace=self.tenant,
                actor=self.actor,
                loan_id=self.loan.pk,
                values=values,
                intent_token=page.context["intent_token"],
            )
        with self.assertRaises(PermissionDenied):
            preview_completed_payout(
                workspace=self.tenant,
                actor=None,
                loan_id=self.loan.pk,
                values=values,
                intent_token=page.context["intent_token"],
            )

    def test_profile_blockers_are_disclosed_before_completed_fact_entry(self):
        from apps.tenant_apps.loans.services.completed_payouts import (
            completed_payout_profile_blockers,
        )
        from types import SimpleNamespace

        unsupported = SimpleNamespace(
            product_version=SimpleNamespace(
                repayment_structure="AMORTISING", amortisation_method="FIXED"
            ),
            approval_snapshots=self.loan.approval_snapshots,
        )
        self.assertIn(
            "non-amortising monthly", completed_payout_profile_blockers(unsupported)[0]
        )
        before = list(self.loan.loan_events.values_list("pk", "payload_fingerprint"))
        self.assertEqual(completed_payout_profile_blockers(self.loan), ())
        self.assertEqual(
            list(self.loan.loan_events.values_list("pk", "payload_fingerprint")), before
        )

    def test_review_rejects_changed_draft_and_retains_unpaid_state(self):
        self.approve()
        self.start()
        self.preview()
        self.loan.tenure_months = 10
        self.loan.save(update_fields=["tenure_months"])
        self.assertContains(
            self.client.post(self.url, self.post), "Actual terms differ"
        )
        self.assertFalse(self.loan.loan_events.exists())

    def test_review_accepts_audited_same_customer_merge_without_rewriting_approval(
        self,
    ):
        approval = self.approve()
        original = deepcopy(approval.payload)
        target = Party.objects.create(display_name="Retained same customer")
        merge_parties(target=target, source=self.loan.borrower, actor=self.actor)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.borrower_id, target.pk)
        self.start()
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        approval.refresh_from_db()
        self.assertEqual(approval.payload, original)

    def test_retained_changed_evidence_and_completed_facts_survive_exact_recovery(self):
        from .test_pawn_recovery import PawnRecoveryTests

        self.approve()
        withdraw_quote(
            workspace=self.tenant,
            actor=self.actor,
            quote_id=self.quote.pk,
            reason="Retained changed source",
        )
        self.start()
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        original = PawnRecoveryTests.export(self)
        PawnRecoveryTests.empty(self)
        self.assertTrue(PawnRecoveryTests.restore(self, commit=True)["committed"])
        restored = PawnRecoveryTests.export(self)
        for key in ("tables", "files", "reconciliation", "guards_sha256"):
            self.assertEqual(original[key], restored[key], key)

    def test_multiple_saved_item_principals_and_different_rates_are_preserved(self):
        item = self.loan.collateral_items.get()
        item.allocated_principal = 500
        item.save(update_fields=["allocated_principal"])
        second = m.PawnCollateralItem.objects.create(
            loan=self.loan,
            description="Second pledge",
            metal="GOLD",
            quantity=1,
            gross_weight=1,
            net_weight=1,
            purity_percentage=100,
            allocated_principal=500,
            monthly_interest_rate=4,
        )
        self.loan.monthly_interest_rate = 3
        self.loan.save(update_fields=["monthly_interest_rate"])
        self.start()
        self.preview()
        self.assertEqual(self.client.post(self.url, self.post).status_code, 302)
        snapshot = self.loan.disbursal_snapshots.get()
        self.assertEqual(snapshot.monthly_interest, 30)
        self.assertEqual(
            list(
                self.loan.collateral_items.order_by("pk").values_list(
                    "pk", "allocated_principal", "monthly_interest_rate"
                )
            ),
            [(item.pk, 500, 2), (second.pk, 500, 4)],
        )

    def test_common_command_uses_restricted_role_and_refuses_foreign_workspace(self):
        self.approve()
        self.start()
        review = self.preview()
        values = review.context["form"].cleaned_data
        foreign = Company.objects.create(
            name="Other fictional workspace",
            schema_name=uuid4().hex,
            owner=self.actor,
            creator=self.actor,
        )
        role = connection.ops.quote_name("ls02_runtime_" + uuid4().hex)
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
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
                )
                self.assertEqual(cursor.fetchone(), (False, False))
            with self.assertRaises(PermissionDenied):
                preview_completed_payout(
                    workspace=foreign,
                    actor=self.actor,
                    loan_id=self.loan.pk,
                    values=values,
                    intent_token=self.post["intent_token"],
                )
            loan, created = record_completed_payout(
                workspace=self.tenant,
                actor=self.actor,
                loan_id=self.loan.pk,
                values=values,
                intent_token=self.post["intent_token"],
                review_token=self.post["review_token"],
                confirmed=True,
            )
            self.assertTrue(created)
            self.assertEqual(loan.loan_events.count(), 1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
