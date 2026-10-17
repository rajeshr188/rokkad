"""Shared review, unchanged authority and exact combined-confirmation retries."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import override_settings
from django.urls import reverse

from apps.tenancy.testing import WorkspaceTestCase
from apps.orgs.models import Membership, Role
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.loan_workflow import (
    SALT,
    make_review,
    review_and_disburse,
    set_loan_workflow,
)
from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
from . import test_pawn_draft_ui as fixtures
from . import test_pawn_recovery as backups


@override_settings(
    ROOT_URLCONF="django_project.workspace_urls",
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
        },
    },
)
class OriginationReviewTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.PawnDraftUiTests.setup_tenant.__func__)
    _configured_setup = fixtures.PawnDraftUiTests._configured_setup
    _payload = fixtures.PawnDraftUiTests._payload
    export = backups.PawnRecoveryTests.export
    restore = backups.PawnRecoveryTests.restore
    empty = backups.PawnRecoveryTests.empty

    @classmethod
    def get_test_schema_name(cls):
        return "origination-review-lo03"

    @classmethod
    def setUpTestData(cls):
        from .recovery_fixtures import lock_recovery_fixture_tables

        lock_recovery_fixture_tables()
        super().setUpTestData()

    def setUp(self):
        super().setUp()
        for mock in (
            patch("django.utils.timezone.localdate", return_value=date(2026, 7, 18)),
            patch(
                "django.templatetags.static.StaticNode.handle_simple",
                side_effect=lambda path: f"/static/{path}",
            ),
        ):
            mock.start()
            self.addCleanup(mock.stop)
        self.owner = self.tenant.owner
        self.actor = self.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.party = Party.objects.create(display_name="Review Borrower")
        self.product_version = _seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(
            status="ACTIVE"
        )
        self.license, self.series = self._configured_setup()
        set_loan_workflow(actor=self.owner, mode="SIMPLE")

    def start_review(self, **changes):
        facts = dict(
            self._payload(self.license, self.series), action="review", **changes
        )
        response = self.client.post(reverse("loans:pawn_loan_create"), facts)
        self.assertEqual(response.status_code, 302)
        loan = m.PawnLoan.objects.get()
        path = reverse(
            "workspace_loans:pawn_loan_review_disburse",
            args=[self.tenant.slug, loan.pk],
        )
        self.assertEqual(response.url, path)
        page = self.client.get(path)
        return loan, path, facts, page

    def confirm(self, path, page):
        return self.client.post(
            path,
            dict(
                effective_date="2026-07-18",
                confirmed="on",
                review_token=page.context["form"].initial["review_token"],
            ),
        )

    def test_one_review_then_confirmation_records_one_payout_and_retries(self):
        loan, path, facts, page = self.start_review()
        self.assertContains(page, "data-origination-agreement")
        self.assertContains(page, "Gold chain")
        self.assertContains(page, "9,800")
        self.assertContains(page, "Confirm payout")
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(loan.loan_events.count(), 0)
        self.assertEqual(loan.approval_snapshots.count(), 0)
        facts.pop("collateral-0-photograph")
        self.assertEqual(
            self.client.post(reverse("loans:pawn_loan_create"), facts).url, path
        )
        for _ in range(2):
            self.assertEqual(self.confirm(path, page).status_code, 302)
        loan.refresh_from_db()
        self.assertEqual(loan.state, "ACTIVE")
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)
        self.assertEqual(loan.approval_snapshots.count(), 1)
        self.assertEqual(loan.disbursal_snapshot.net_disbursed, 9800)
        self.assertEqual(
            loan.approval_snapshots.get().payload["combined_review"]["actor"],
            self.owner.pk,
        )
        from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
        import fitz

        with fitz.open(
            stream=PawnLoanDocumentService.render_loan_ticket(loan).pdf, filetype="pdf"
        ) as document:
            printed = " ".join(page.get_text() for page in document)
        self.assertIn("18/07/2026", printed)
        self.assertIn("Pawn Loan Ticket", printed)
        self.assertNotIn("Recorded Paper Loan Contract", printed)
        # The old creation-form retry now returns the active loan, not a new review/debt.
        self.assertEqual(
            self.client.post(reverse("loans:pawn_loan_create"), facts).url,
            reverse(
                "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, loan.pk]
            ),
        )

    def test_review_explains_resolved_terms_and_changed_calculation_without_posting(
        self,
    ):
        from decimal import Decimal
        from apps.tenant_apps.loans.services.economic_policies import (
            create_pawn_loan_economic_policy,
        )

        loan, path, _, page = self.start_review()
        self.assertContains(page, "How this agreement is calculated")
        self.assertContains(page, "Where these terms came from")
        self.assertContains(page, "interest for a started month")
        create_pawn_loan_economic_policy(
            workspace=self.tenant,
            actor=self.owner,
            license=self.license,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            advance_interest_periods=1,
            partial_month_method="STARTED_WEEKS",
            effective_from=date(2026, 7, 18),
        )
        from apps.tenant_apps.loans.services.paper_entry_terms import paper_entry_terms

        paper_defaults = paper_entry_terms(
            workspace=self.tenant, series=self.series, day=loan.loan_date, metal="GOLD"
        )
        self.assertNotIn("advance_months", paper_defaults["values"])
        self.assertTrue(paper_defaults["messages"])
        failed = self.confirm(path, page)
        self.assertContains(failed, "Changed since your review")
        self.assertContains(failed, "Interest for started 7-day blocks")
        self.assertContains(failed, "Financial agreement correction currently requires")
        self.assertFalse(loan.loan_events.exists())
        self.assertFalse(loan.approval_snapshots.exists())
        fresh = self.client.get(path)
        self.assertEqual(self.confirm(path, fresh).status_code, 302)

    def test_saved_approval_rules_are_shown_without_replacing_them_from_setup(self):
        from decimal import Decimal
        from apps.tenant_apps.loans.services import approve_pawn_loan
        from apps.tenant_apps.loans.services.economic_policies import (
            create_pawn_loan_economic_policy,
        )
        from apps.tenant_apps.loans.services.origination_summary import (
            native_origination_summary,
        )

        loan, _, _, page = self.start_review()
        self.assertContains(page, "18/08/2026")
        approve_pawn_loan(loan.pk, actor=self.owner)
        loan.refresh_from_db()
        create_pawn_loan_economic_policy(
            workspace=self.tenant,
            actor=self.owner,
            license=self.license,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal(".8"),
            partial_month_method="STARTED_WEEKS",
            effective_from=loan.loan_date,
        )
        terms = dict(native_origination_summary(loan, None)["calculation_terms"])
        self.assertIn("full month's", terms["Part-month charging"])
        self.assertNotIn("Capability limits", terms)

    def test_change_summary_does_not_disclose_foreign_or_malformed_signed_reviews(self):
        from apps.tenant_apps.loans.services.loan_workflow import reviewed_term_changes

        loan, _, _, page = self.start_review()
        agreement = page.context["agreement"]
        token = page.context["form"].initial["review_token"]
        foreign = get_user_model().objects.create_user(username="foreign-reviewer")
        self.assertEqual(
            reviewed_term_changes(
                loan, actor=foreign, token=token, agreement=agreement
            ),
            [],
        )
        for value in ([], {}, {"version": 99}):
            self.assertEqual(
                reviewed_term_changes(
                    loan,
                    actor=self.owner,
                    token=signing.dumps(value, salt=SALT),
                    agreement=agreement,
                ),
                [],
            )

    def test_final_payout_failure_rolls_back_approval_and_all_financial_effects(self):
        loan, path, _, page = self.start_review()
        with patch(
            "apps.tenant_apps.loans.services.loan_workflow.disburse_pawn_loan",
            side_effect=ValueError("Payout failed"),
        ):
            self.assertContains(self.confirm(path, page), "Payout failed")
        loan.refresh_from_db()
        self.assertEqual(loan.state, "DRAFT")
        self.assertEqual(loan.approval_snapshots.count(), 0)
        self.assertEqual(loan.loan_events.count(), 0)
        self.assertEqual(self.confirm(path, page).status_code, 302)

    def test_changed_inputs_or_photo_policy_require_fresh_review(self):
        from apps.tenant_apps.loans.services.origination_settings import (
            set_collateral_photo_requirement,
        )

        loan, path, _, page = self.start_review()
        item = loan.collateral_items.get()
        item.description = "Corrected chain description"
        item.save(update_fields=["description"])
        self.assertContains(self.confirm(path, page), "changed")
        fresh = self.client.get(path)
        set_collateral_photo_requirement(
            workspace=self.tenant, actor=self.owner, required=True
        )
        self.assertContains(self.confirm(path, fresh), "policies changed")
        self.assertEqual(loan.approval_snapshots.count(), 0)
        self.assertEqual(self.confirm(path, self.client.get(path)).status_code, 302)

    def test_review_is_bound_to_user_date_loan_and_workspace(self):
        loan, _, _, page = self.start_review()
        values = signing.loads(page.context["form"].initial["review_token"], salt=SALT)
        for field, value in (
            ("actor", self.owner.pk + 1),
            ("loan", loan.pk + 1),
            ("workspace", self.tenant.pk + 1),
            ("date", "2026-07-19"),
        ):
            with self.subTest(field=field), self.assertRaises(ValueError):
                review_and_disburse(
                    loan.pk,
                    actor=self.owner,
                    effective_date=date(2026, 7, 18),
                    token=signing.dumps(dict(values, **{field: value}), salt=SALT),
                )
        self.assertEqual(loan.loan_events.count(), 0)
        self.assertEqual(loan.approval_snapshots.count(), 0)

    def test_active_retry_must_match_the_review_that_created_its_payout(self):
        loan, path, _, old = self.start_review()
        loan.tenure_months = 4
        loan.save(update_fields=["tenure_months"])
        fresh = self.client.get(path)
        self.assertEqual(self.confirm(path, fresh).status_code, 302)
        self.assertContains(
            self.confirm(path, old), "Another payout has already been recorded"
        )
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)

    def test_full_frozen_contract_is_checked_even_when_four_totals_match(self):
        from apps.tenant_apps.loans.services.pawn_lifecycle import approve_pawn_loan

        loan, path, _, page = self.start_review()

        def changed_contract(*args, **kwargs):
            approval = approve_pawn_loan(*args, **kwargs)
            approval.payload["collateral_economics"]["partial_month_cutoff_days"] += 1
            return approval

        with patch(
            "apps.tenant_apps.loans.services.loan_workflow.approve_pawn_loan",
            side_effect=changed_contract,
        ):
            self.assertContains(
                self.confirm(path, page), "economics changed during confirmation"
            )
        self.assertEqual(loan.approval_snapshots.count(), 0)
        self.assertEqual(loan.loan_events.count(), 0)

    def test_extended_and_staff_do_not_gain_combined_authority(self):
        set_loan_workflow(actor=self.owner, mode="EXTENDED")
        entry = reverse("loans:pawn_loan_create")
        self.assertNotContains(self.client.get(entry), 'value="review"')
        response = self.client.post(
            entry, dict(self._payload(self.license, self.series), action="review")
        )
        loan = m.PawnLoan.objects.get()
        self.assertEqual(
            response.url,
            reverse(
                "workspace_loans:pawn_loan_detail", args=[self.tenant.slug, loan.pk]
            ),
        )
        set_loan_workflow(actor=self.owner, mode="SIMPLE")
        staff = get_user_model().objects.create_user(username="lo03-staff")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.tenant, role=role)
        self.client.force_login(staff)
        self.assertNotContains(self.client.get(entry), 'value="review"')
        self.assertEqual(
            self.client.get(
                reverse("loans:pawn_loan_review_disburse", args=[loan.pk])
            ).status_code,
            403,
        )
        self.assertEqual(loan.loan_events.count(), 0)

    def test_issued_v1_review_remains_accepted_without_new_binding_fields(self):
        loan, _, _, _ = self.start_review()
        _, token = make_review(loan)
        self.assertNotIn("version", signing.loads(token, salt=SALT))
        for _ in range(2):
            review_and_disburse(
                loan.pk, actor=self.owner, effective_date=date(2026, 7, 18), token=token
            )
        self.assertEqual(loan.approval_snapshots.count(), 1)
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)

    def test_invalid_or_expired_review_cannot_post(self):
        loan, _, _, page = self.start_review()
        token = page.context["form"].initial["review_token"]
        for invalid in (
            "broken",
            signing.dumps([], salt=SALT),
            signing.dumps({"version": 99}, salt=SALT),
        ):
            with self.subTest(token=invalid), self.assertRaises(ValueError):
                review_and_disburse(
                    loan.pk,
                    actor=self.owner,
                    effective_date=date(2026, 7, 18),
                    token=invalid,
                )
        with (
            patch("django.core.signing.time.time", return_value=9999999999),
            self.assertRaisesMessage(ValueError, "expired"),
        ):
            review_and_disburse(
                loan.pk, actor=self.owner, effective_date=date(2026, 7, 18), token=token
            )
        self.assertEqual(loan.approval_snapshots.count(), 0)
        self.assertEqual(loan.loan_events.count(), 0)

    def test_combined_review_proof_photos_and_retry_survive_exact_recovery(self):
        loan, path, _, page = self.start_review()
        self.assertEqual(self.confirm(path, page).status_code, 302)
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
        self.assertEqual(self.confirm(path, page).status_code, 302)
        self.assertEqual(loan.approval_snapshots.count(), 1)
        self.assertEqual(loan.loan_events.filter(event_kind="DISBURSAL").count(), 1)
