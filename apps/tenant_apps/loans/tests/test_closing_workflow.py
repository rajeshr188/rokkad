"""One closing experience preserves current/completed cash and custody meaning."""
from datetime import date
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.urls import reverse

from apps.tenant_apps.loans.models import PawnLoanRelease, PawnReleaseBatch, PawnLoanEvent
from apps.tenant_apps.loans.services.paper_closures import (
    preview_paper_closures, complete_paper_closures, set_paper_transition)
from apps.tenant_apps.loans.services.recorded_closures import preview_recorded_closure, record_paper_closure
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
from apps.tenant_apps.loans.tests import test_release_batches as batch_fixtures


class ClosingWorkflowTests(batch_fixtures.ReleaseBatchTests):
    def url(self, loan=None):
        return reverse("workspace_loans:pawn_loan_close", kwargs={
            "workspace_slug": self.tenant.slug, "pk": (loan or self.loans[0]).pk})

    def facts(self, loan=None, **overrides):
        loan = loan or self.loans[0]
        quote = preview_pawn_loan_full_release(loan.pk)
        return dict(date="2026-07-18", amount=str(quote.minimum_settlement), number="", reference="Book 7",
            basis="PAPER_SETTLEMENT", recipient="", request_key=str(uuid4()), interest_concession="0",
            concession_reason="", exception_reason="", paid_by="", collector_is_borrower=True,
            relationship="", authorization_note="") | overrides

    def batch(self, **overrides):
        preview = preview_paper_closures(workspace=self.tenant, actor=self.owner,
            loan_ids=[loan.pk for loan in self.loans], closure_date=date(2026, 7, 18))
        return dict(workspace=self.tenant, actor=self.owner, request_key=uuid4(), quote_token=preview["token"],
            confirmed=True, paper_reference="Book 7", rows=[dict(loan_id=row["loan"].pk,
                amount=str(row["amount"]), basis="PAPER_SETTLEMENT", paid_by="", collector_name="",
                number="", collector_is_borrower=True) for row in preview["rows"]]) | overrides

    def test_one_screen_selects_standing_preference_independently_of_native_origin(self):
        with patch("apps.tenant_apps.loans.web.closing.default_entry_purpose", return_value="PAPER"):
            response = self.client.get(self.url())
        self.assertContains(response, "Close / release loan")
        self.assertEqual(response.context["closure_purpose"], "PAPER")
        self.assertContains(response, "Record a settlement already completed")
        response = self.client.get(self.url(), {"purpose": "CURRENT"})
        self.assertEqual(response.context["closure_purpose"], "CURRENT")
        self.assertContains(response, "Confirm collection and full release")
        self.assertEqual(self.client.post(self.url(), {}).status_code, 400)
        self.assertEqual(self.client.get(self.url(), {"purpose": "UNKNOWN"}).status_code, 400)

    def test_unified_current_confirmation_uses_ordinary_release(self):
        amount = preview_pawn_loan_full_release(self.loans[0].pk).minimum_settlement
        response = self.client.post(self.url(), dict(purpose="CURRENT", request_key=str(uuid4()),
            settlement_amount=str(amount), confirm_collateral_handoff="on"))
        self.assertEqual(response.status_code, 302)
        release = self.loans[0].releases.get()
        self.assertNotIn("paper_closure", release.loan_event.payload["release"])
        self.assertTrue(all(item.returned_at is not None for item in release.items.all()))

    def test_unified_completed_review_confirm_and_duplicate_are_not_current_cash(self):
        facts = self.facts()
        web = dict(facts, collector_is_borrower="yes", purpose="PAPER", action="preview")
        response = self.client.post(self.url(), web)
        self.assertContains(response, "Physical cash and customer handover remain unconfirmed")
        self.assertFalse(PawnLoanRelease.objects.exists())
        web.update(action="confirm", confirmed="on", review_token=response.context["review_token"])
        self.assertEqual(self.client.post(self.url(), web).status_code, 302)
        self.assertEqual(self.client.post(self.url(), web).status_code, 302)
        self.assertEqual(PawnLoanRelease.objects.count(), 1)
        self.assertEqual(self.loans[0].collateral_items.get().custody_state, "PAPER_CLOSED")

    def test_mixed_bulk_retains_independent_settlement_and_unknown_custody_and_csv(self):
        command = self.batch()
        returned = command["rows"][1]
        returned.update(basis="RETURNED", paid_by="Family payer",
            collector_name=self.loans[1].borrower.display_name, number="PAPER-CLOSE-2")
        with patch("django.utils.timezone.localdate", return_value=date(2026, 7, 20)):
            batch = complete_paper_closures(**command)
        self.assertEqual(batch.effective_date, date(2026, 7, 18))
        self.assertEqual(batch.total_amount, sum(Decimal(row["amount"]) for row in command["rows"]))
        self.assertEqual(complete_paper_closures(**command).pk, batch.pk)
        self.assertEqual(self.loans[0].collateral_items.get().custody_state, "PAPER_CLOSED")
        self.assertEqual(self.loans[1].collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(self.loans[1].releases.get().release_number, "PAPER-CLOSE-2")
        self.assertTrue(all(item.returned_at is None for release in PawnLoanRelease.objects.all() for item in release.items.all()))
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        payload = PawnLoanDocumentProjectionBuilder.release_memo(self.loans[0].releases.get())
        self.assertIn(("Collected by", "Not confirmed by paper record"), payload.details)
        self.assertNotIn("Borrower receipt attested from paper record", str(payload.details))
        detail = self.client.get(reverse("workspace_loans:release_batch_detail", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": batch.pk}))
        self.assertContains(detail, "Physical cash and customer handover were not established")
        csv = self.client.get(reverse("workspace_loans:paper_closure_csv", kwargs={"workspace_slug": self.tenant.slug, "batch_pk": batch.pk}))
        self.assertContains(csv, "Not established")
        self.assertContains(csv, "Settlement amount")

    def test_bad_row_rolls_back_all_extended_settlements_and_original_numbers(self):
        command = self.batch()
        command["rows"][0]["number"] = "SOURCE-CLOSE-1"
        command["rows"][1]["amount"] = str(Decimal(command["rows"][1]["amount"]) + 1)
        before = PawnLoanEvent.objects.count()
        with self.assertRaises(ValueError): complete_paper_closures(**command)
        self.assertFalse(PawnLoanRelease.objects.exists())
        self.assertFalse(PawnReleaseBatch.objects.exists())
        self.assertEqual(PawnLoanEvent.objects.count(), before)
        for loan in self.loans:
            loan.refresh_from_db()
            self.assertEqual(loan.state, "ACTIVE")

    def test_optional_restriction_rechecks_single_and_bulk_and_retains_exceptions(self):
        facts = self.facts()
        _, token = preview_recorded_closure(loan_id=self.loans[0].pk, actor=self.owner, data=facts)
        batch = self.batch()
        set_paper_transition(workspace=self.tenant, actor=self.owner, system_first_date=date(2026, 7, 18),
            retired=True, reason="Owner operating commitment")
        with self.assertRaisesMessage(ValueError, "exception reason"):
            record_paper_closure(loan_id=self.loans[0].pk, actor=self.owner, data=facts, review_token=token, confirmed=True)
        with self.assertRaisesMessage(ValueError, "exception reason"): complete_paper_closures(**batch)
        facts["exception_reason"] = "Outage entry"
        _, token = preview_recorded_closure(loan_id=self.loans[0].pk, actor=self.owner, data=facts)
        release, _ = record_paper_closure(loan_id=self.loans[0].pk, actor=self.owner,
            data=facts, review_token=token, confirmed=True)
        self.assertEqual(release.loan_event.payload["release"]["paper_closure"]["exception_reason"], "Outage entry")
        self.assertEqual(self.client.get(self.url(self.loans[1])).context["closure_purpose"], "CURRENT")

    def test_confirmed_other_recipient_requires_authority_in_both_paths(self):
        facts = self.facts(basis="RETURNED", recipient="Spouse", collector_is_borrower=False, paid_by="Borrower")
        with self.assertRaisesMessage(ValueError, "authority"):
            preview_recorded_closure(loan_id=self.loans[0].pk, actor=self.owner, data=facts)
        command = self.batch()
        command["rows"][0].update(basis="RETURNED", collector_is_borrower=False,
            paid_by="Borrower", collector_name="Spouse")
        with self.assertRaises(ValueError): complete_paper_closures(**command)
        facts.update(relationship="Spouse", authorization_note="Signed authority")
        _, token = preview_recorded_closure(loan_id=self.loans[0].pk, actor=self.owner, data=facts)
        release, _ = record_paper_closure(loan_id=self.loans[0].pk, actor=self.owner,
            data=facts, review_token=token, confirmed=True)
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        memo = PawnLoanDocumentProjectionBuilder.release_memo(release)
        self.assertIn(("Collected by", "Spouse"), memo.details)
        self.assertIn(("Collection authorization", "Signed authority"), memo.details)

    def test_issued_legacy_bulk_form_retry_retains_original_profile_and_digest(self):
        command = self.batch()
        for loan, row in zip(self.loans, command["rows"]):
            row.pop("basis")
            row.pop("number")
            row.update(paid_by="Borrower", collector_name=loan.borrower.display_name)
        batch = complete_paper_closures(**command)
        data = dict(action="complete", loans=[str(loan.pk) for loan in self.loans],
            closure_date="2026-07-18", paper_reference=command["paper_reference"],
            request_key=str(command["request_key"]), quote_token=command["quote_token"], confirmed="on")
        for row in command["rows"]:
            prefix = f"row_{row['loan_id']}-"
            data.update({prefix + name: value for name, value in row.items() if name != "loan_id"})
            data.update({prefix + "include": "on", prefix + "collector_is_borrower": "yes"})
        url = reverse("workspace_loans:paper_closure_create", kwargs={"workspace_slug": self.tenant.slug})
        response = self.client.post(url, data)
        self.assertEqual(response.context["completed"].pk, batch.pk)
        self.assertEqual(PawnReleaseBatch.objects.count(), 1)
        self.assertEqual(PawnLoanRelease.objects.count(), 2)
        for release in PawnLoanRelease.objects.all():
            self.assertEqual(release.loan_event.payload["release"]["paper_closure"]["profile"], "paper-closure/1")

    def test_owner_can_require_all_recording_exceptions_without_a_cutoff(self):
        url = reverse("workspace_loans:paper_closure_settings", kwargs={"workspace_slug": self.tenant.slug})
        response = self.client.post(url, dict(retired="on", reason="All actions recorded as they happen"))
        self.assertEqual(response.status_code, 302)
        with self.assertRaisesMessage(ValueError, "exception reason"):
            preview_recorded_closure(loan_id=self.loans[0].pk, actor=self.owner, data=self.facts())
        self.assertEqual(self.client.get(self.url()).context["closure_purpose"], "CURRENT")

    def test_extended_unknown_batch_supports_later_handover_without_another_settlement(self):
        batch = complete_paper_closures(**self.batch())
        loan = self.loans[0]
        from apps.tenant_apps.loans.services.paper_handover import preview_paper_handover, confirm_paper_handover
        before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        data = dict(date="2026-07-18", recipient=loan.borrower.display_name, reference="Return slip", request_key=str(uuid4()))
        _, token = preview_paper_handover(loan.pk, actor=self.owner, data=data)
        confirm_paper_handover(loan.pk, actor=self.owner, data=data, review_token=token, confirmed=True)
        self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertEqual(batch.lines.count(), 2)

    def test_restricted_database_guards_require_exact_unknown_evidence(self):
        from apps.tenant_apps.loans.models import PawnReleaseBatchLine
        command = self.batch()
        command['rows'][1].update(basis='RETURNED', paid_by='Borrower',
            collector_name=self.loans[1].borrower.display_name)
        batch = complete_paper_closures(**command)
        unknown, returned = list(batch.lines.order_by('release__loan_id'))
        role = connection.ops.quote_name('closing_guards_' + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO {role}')
            cursor.execute(f'GRANT SELECT ON loans_pawnreleasebatch, loans_pawnloanrelease, loans_pawnloanevent TO {role}')
            cursor.execute(f'GRANT SELECT, INSERT, UPDATE ON loans_pawnreleasebatchline TO {role}')
            cursor.execute(f'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}')
        try:
            with connection.cursor() as cursor:
                cursor.execute(f'SET LOCAL ROLE {role}')
            for source, changes, message in (
                (unknown, dict(paid_by='Invented payer'), 'cannot assert payer'),
                (returned, dict(collector_name=''), 'Collector confirmation'),
                (returned, dict(paid_by=''), 'Paper closure payer required')):
                values = dict(workspace_id=self.tenant.pk, batch_id=batch.pk, release_id=source.release_id,
                    borrower_name=source.borrower_name, paid_by=source.paid_by, collector_name=source.collector_name,
                    collector_is_borrower=source.collector_is_borrower,
                    relationship=source.relationship, authorization_note=source.authorization_note)
                with self.subTest(changes=changes), self.assertRaisesMessage(DatabaseError, message), transaction.atomic():
                    PawnReleaseBatchLine.objects.create(**(values | changes))
            with self.assertRaisesMessage(DatabaseError, 'immutable'), transaction.atomic():
                batch.lines.update(paid_by='Rewritten')
        finally:
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute(f'DROP OWNED BY {role}')
                cursor.execute(f'DROP ROLE {role}')


from apps.tenant_apps.loans.tests import test_release_concessions as concession_fixtures


class CompletedConcessionTests(concession_fixtures.ReleaseConcessionTests):
    def test_completed_concession_retains_loss_and_unknown_handover(self):
        from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
        facts = dict(date=self.today.isoformat(), amount=str(self.quote.minimum_settlement - 5),
            number='', reference='Closing agreement', basis='PAPER_SETTLEMENT', recipient='',
            request_key=str(uuid4()), interest_concession='5', concession_reason='Agreed interest concession')
        review, token = preview_recorded_closure(loan_id=self.loan.pk, actor=self.actor, data=facts)
        self.assertEqual(review['interest_concession'], '5.00')
        release, created = record_paper_closure(loan_id=self.loan.pk, actor=self.actor,
            data=facts, review_token=token, confirmed=True)
        self.assertTrue(created)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.today)
        self.assertEqual(balance.total_due, 0)
        self.assertEqual(balance.interest_conceded, 5)
        self.assertEqual(release.settlement_amount, release.principal_amount + release.interest_amount + release.fee_amount)
        self.assertFalse(self.loan.collateral_items.exclude(custody_state='PAPER_CLOSED').exists())

    def test_completed_concession_requires_administrator_and_cannot_waive_principal(self):
        from django.contrib.auth import get_user_model
        from django.contrib.auth.models import Permission
        from apps.orgs.models import Membership, Role
        from apps.tenancy.testing import workspace_role_permissions
        user = get_user_model().objects.create_user(username='closing-release-only')
        role = Role.objects.create(name='Completed closure without concessions')
        Membership.objects.create(company=self.tenant, user=user, role=role)
        workspace_role_permissions(role, self.tenant).set(Permission.objects.filter(
            content_type__app_label='orgs', content_type__model='company', codename__in=['data_view', 'loan_release']))
        facts = dict(date=self.today.isoformat(), amount=str(self.quote.minimum_settlement - 5),
            number='', reference='Closing agreement', basis='PAPER_SETTLEMENT', recipient='',
            request_key=str(uuid4()), interest_concession='5', concession_reason='Agreed interest concession')
        with self.assertRaises(PermissionDenied):
            preview_recorded_closure(loan_id=self.loan.pk, actor=user, data=facts)
        facts.update(amount='0', interest_concession=str(self.quote.minimum_settlement))
        with self.assertRaises(ValueError):
            preview_recorded_closure(loan_id=self.loan.pk, actor=self.actor, data=facts)
        self.assertFalse(self.loan.releases.exists())
