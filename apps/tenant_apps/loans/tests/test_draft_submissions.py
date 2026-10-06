import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import WorkspaceTestCase, historical_migration_database
from apps.tenant_apps.loans.models import PawnLoan, LoanNumberSequence
from apps.tenant_apps.loans.services.draft_submissions import (
    new_draft_submission, saved_draft_submission, submit_new_draft,
)
from apps.tenant_apps.loans.services import CollateralDraftInput, CreatePawnDraftCommand, DraftCollateralPhotoInput, cancel_pawn_loan
from apps.tenant_apps.loans.tests import test_pawn_draft_ui as fixtures


STORAGE = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def photo():
    return DraftCollateralPhotoInput(None, SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"))


def command(test):
    return CreatePawnDraftCommand(workspace_id=test.tenant.pk, borrower_id=test.party.pk,
        license_id=test.license.pk, series_id=test.series.pk, product_version_id=test.product_version.pk,
        principal_amount=Decimal("10000"), monthly_interest_rate=Decimal("2"), loan_date=date(2026, 7, 18),
        tenure_months=3, collateral=(CollateralDraftInput(description="Gold chain", metal="GOLD",
            gross_weight=Decimal("10"), net_weight=Decimal("9"), purity_percentage=Decimal("91.6"),
            latest_appraised_value=Decimal("50000"), allocated_principal=Decimal("10000")),))


@override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES=STORAGE)
class DraftSubmissionTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.PawnDraftUiTests.setup_tenant.__func__)
    _configured_setup = fixtures.PawnDraftUiTests._configured_setup
    _payload = fixtures.PawnDraftUiTests._payload

    @classmethod
    def get_test_schema_name(cls):
        return "draft-submission"

    def setUp(self):
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        super().setUp()
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.party = Party.objects.create(display_name="Draft Borrower")
        self.product_version = _seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
        self.license, self.series = self._configured_setup()
        self.command = command(self)
        self.token = new_draft_submission(workspace=self.tenant, actor=self.owner)
        self.url = reverse("loans:pawn_loan_create")
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        settings = override_settings(MEDIA_ROOT=self.media.name)
        settings.enable()
        self.addCleanup(settings.disable)

    def submit(self, **changes):
        values = dict(actor=self.owner, token=self.token, photos=(photo(),))
        values.update(changes)
        return submit_new_draft(self.command, **values)

    def test_retry_reuses_loan_number_photographs_and_audit(self):
        loan, created = self.submit()
        replay, created_again = self.submit()
        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(loan.pk, replay.pk)
        self.assertEqual(PawnLoan.objects.count(), 1)
        self.assertEqual(loan.collateral_items.get().photos.count(), 1)
        self.assertEqual(loan.change_log.count(), 1)
        self.assertEqual(LoanNumberSequence.objects.get(series=self.series, document_kind="PAWN_LOAN").next_number, 2)
        self.assertEqual(loan.created_by, self.owner)
        self.assertFalse(loan.loan_events.exists())

    def test_changed_payload_on_used_form_returns_existing_without_applying_changes(self):
        loan, _ = self.submit()
        self.command = replace(self.command, tenure_months=5)
        with patch("apps.tenant_apps.loans.services.draft_submissions.create_pawn_draft_with_photos") as create:
            replay, created = self.submit()
        create.assert_not_called()
        self.assertFalse(created)
        self.assertEqual(replay.pk, loan.pk)
        self.assertEqual(replay.tenure_months, 3)

    def test_new_form_can_create_identical_legitimate_loan(self):
        self.submit()
        self.submit(token=new_draft_submission(workspace=self.tenant, actor=self.owner))
        self.assertEqual(PawnLoan.objects.count(), 2)

    def test_cancelled_loan_cannot_be_recreated_by_old_submission(self):
        loan, _ = self.submit()
        cancel_pawn_loan(loan.pk, reason="Unused test draft", actor=self.owner)
        replay, created = self.submit()
        self.assertFalse(created)
        self.assertEqual(replay.state, "CANCELLED")
        self.assertEqual(PawnLoan.objects.count(), 1)

    def test_failed_photo_save_rolls_back_identity_number_and_files_then_allows_retry(self):
        from pathlib import Path
        from apps.tenant_apps.loans.services.pawn_drafts import _append_collateral_photo
        item = replace(self.command.collateral[0], allocated_principal=Decimal("5000"))
        self.command = replace(self.command, collateral=(item, item))
        calls = 0
        def failing(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise ValueError("Simulated photo failure")
            return _append_collateral_photo(*args, **kwargs)
        with patch("apps.tenant_apps.loans.services.pawn_drafts._append_collateral_photo", side_effect=failing):
            with self.assertRaisesMessage(ValueError, "photo failure"):
                self.submit(photos=(photo(), photo()))
        self.assertFalse(PawnLoan.objects.exists())
        self.assertFalse(any(p.is_file() for p in Path(self.media.name).rglob('*')))
        self.assertEqual(LoanNumberSequence.objects.get(series=self.series, document_kind="PAWN_LOAN").next_number, 1)
        loan, created = self.submit(photos=(photo(), photo()))
        self.assertTrue(created)
        self.assertTrue(loan.loan_number.endswith("00001"))

    def test_actor_workspace_signature_and_current_permission_are_required_on_replay(self):
        loan, _ = self.submit()
        other = get_user_model().objects.create_user(username="other-draft-admin")
        membership = Membership.objects.create(user=other, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        with self.assertRaises(PermissionDenied):
            self.submit(actor=other)
        with self.assertRaises(ValueError):
            self.submit(token=self.token + "tampered")
        token = new_draft_submission(workspace=self.tenant, actor=other)
        own, _ = self.submit(actor=other, token=token)
        membership.delete()
        with self.assertRaises(PermissionDenied):
            self.submit(actor=other, token=token)
        with self.assertRaises(PermissionDenied):
            submit_new_draft(replace(self.command, workspace_id=999999), actor=self.owner, token=self.token)
        with self.assertRaises(PermissionDenied):
            self.submit(actor=None)

    def test_get_and_preview_keep_reference_and_do_not_allocate(self):
        page = self.client.get(self.url)
        token = page.context["submission_token"]
        self.assertContains(page, 'name="submission_token"')
        payload = self._payload(self.license, self.series)
        payload.update(submission_token=token, action="preview")
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["submission_token"], token)
        self.assertFalse(PawnLoan.objects.exists())
        self.assertEqual(LoanNumberSequence.objects.get(series=self.series, document_kind="PAWN_LOAN").next_number, 1)

    def test_validation_error_retains_reference_and_corrected_retry_saves_once(self):
        payload = self._payload(self.license, self.series)
        token = payload["submission_token"]
        payload["collateral-0-net_weight"] = "12"
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["submission_token"], token)
        self.assertFalse(PawnLoan.objects.exists())
        corrected = self._payload(self.license, self.series)
        corrected["submission_token"] = token
        response = self.client.post(self.url, corrected)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PawnLoan.objects.count(), 1)

    def test_lost_response_recovery_works_without_files_even_after_setup_changes(self):
        payload = self._payload(self.license, self.series)
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 302)
        self.series.is_active = False
        self.series.save(update_fields=["is_active"])
        retry = self.client.post(self.url, {"submission_token": payload["submission_token"], "tenure_months": "99"})
        self.assertEqual(retry.status_code, 302)
        self.assertEqual(retry.url, response.url)
        self.assertIn("No changes were applied", " ".join(str(m) for m in retry.wsgi_request._messages))
        self.assertEqual(PawnLoan.objects.get().tenure_months, 3)

    def test_missing_or_invalid_reference_does_not_create_or_silently_replace_reference(self):
        for token in ("", "invalid"):
            payload = self._payload(self.license, self.series)
            payload["submission_token"] = token
            response = self.client.post(self.url, payload)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "save reference is missing or invalid")
            self.assertEqual(response.context["submission_token"], token)
        self.assertFalse(PawnLoan.objects.exists())

    def test_saved_draft_can_be_edited_repeatedly_without_new_number(self):
        loan, _ = self.submit()
        identity = loan.creation_submission_id
        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[loan.pk]))
        from html.parser import HTMLParser
        class SplitLink(HTMLParser):
            in_panel = False
            links = []
            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == "section" and "data-draft-split-discovery" in attrs:
                    self.in_panel = True
                if self.in_panel and tag == "a":
                    self.links.append(attrs["href"])
            def handle_endtag(self, tag):
                if tag == "section":
                    self.in_panel = False
        parser = SplitLink()
        parser.feed(detail.content.decode())
        update_url = reverse("workspace_loans:pawn_loan_update", args=[self.tenant.slug, loan.pk])
        self.assertEqual(parser.links, [update_url])
        for _ in range(3):
            edit = self.client.get(update_url)
            self.assertEqual(edit.context["loan"].pk, loan.pk)
            self.assertContains(edit, f'action="{update_url}"')
            self.assertContains(edit, "Save changes")
            self.assertContains(edit, "keeps the same loan number")
            self.assertNotContains(edit, "Saving creates")
        for amount in ("11000", "12000"):
            payload = self._payload(self.license, self.series)
            payload.pop("submission_token")
            payload.pop("collateral-0-photograph")
            payload["collateral-0-collateral_item_id"] = loan.collateral_items.get().pk
            payload["collateral-0-allocated_principal"] = amount
            response = self.client.post(reverse("loans:pawn_loan_update", args=[loan.pk]), payload)
            self.assertEqual(response.status_code, 302)
            loan.refresh_from_db()
            self.assertEqual(loan.principal_amount, Decimal(amount))
            self.assertEqual(loan.creation_submission_id, identity)
        self.assertEqual(PawnLoan.objects.count(), 1)
        self.assertEqual(loan.collateral_items.get().photos.count(), 1)
        self.assertEqual(LoanNumberSequence.objects.get(series=self.series, document_kind="PAWN_LOAN").next_number, 2)

    def test_restricted_database_role_enforces_unique_and_immutable_submission(self):
        loan, _ = self.submit()
        role = connection.ops.quote_name("submission_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnLoan.objects.filter(pk=loan.pk).update(creation_submission_id=None)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("DELETE FROM loans_pawnloan WHERE id=%s", [loan.pk])
            with self.assertRaises(DatabaseError), transaction.atomic():
                copy = PawnLoan.objects.get(pk=loan.pk)
                copy.pk = None
                copy.loan_number += "-duplicate"
                copy.save(force_insert=True)
            self.assertEqual(self.submit()[0].pk, loan.pk)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


@override_settings(STORAGES=STORAGE)
class DraftSubmissionConcurrencyTests(TransactionTestCase):
    _configured_setup = fixtures.PawnDraftUiTests._configured_setup

    def test_populated_migration_keeps_existing_loans_and_sequences_unchanged(self):
        from django.db.migrations.executor import MigrationExecutor
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        from apps.tenant_apps.loans.services.pawn_drafts import create_pawn_draft
        self.owner = get_user_model().objects.create_user(username="submission-migration")
        self.tenant = Company.objects.create(name="Submission migration", schema_name=uuid.uuid4().hex,
            owner=self.owner, creator=self.owner)
        Membership.objects.create(user=self.owner, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(self.tenant.pk):
            self.party = Party.objects.create(display_name="Existing borrower")
            self.product_version = _seed_default_loan_products()[0]
            type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
            self.license, self.series = self._configured_setup()
            loan = create_pawn_draft(command(self), actor=self.owner)
            before = PawnLoan.objects.values().get()
            numbers = list(LoanNumberSequence.objects.order_by("pk").values())
            sequences = list(LoanNumberSequence.objects.all())
        membership = Membership.objects.get(company=self.tenant, user=self.owner)
        with historical_migration_database(
            self,
            [("loans", "0026_collateral_quantity_and_interest_override")],
            [membership, loan, *sequences],
        ) as (target, old_apps):
            old_loan = old_apps.get_model("loans", "PawnLoan")
            old_numbers = old_apps.get_model("loans", "LoanNumberSequence")
            originals = list(old_loan.objects.using(target.alias).values())
            original_numbers = list(old_numbers.objects.using(target.alias).order_by("pk").values())
            after = [("loans", "0027_draft_submission_identity")]
            executor = MigrationExecutor(target)
            executor.migrate(after)
            apps = executor.loader.project_state(after).apps
            rows = list(apps.get_model("loans", "PawnLoan").objects.using(target.alias).values())
            self.assertTrue(all(row.pop("creation_submission_id") is None for row in rows))
            self.assertEqual(rows, originals)
            self.assertEqual(list(apps.get_model("loans", "LoanNumberSequence").objects.using(target.alias).order_by("pk").values()), original_numbers)
        with workspace_context(self.tenant.pk):
            self.assertEqual(PawnLoan.objects.values().get(), before)
            self.assertEqual(list(LoanNumberSequence.objects.order_by("pk").values()), numbers)

    def test_simultaneous_submissions_create_one_loan_and_photo(self):
        from apps.tenant_apps.party.models import Party
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        self.owner = get_user_model().objects.create_user(username="simultaneous-draft")
        self.tenant = Company.objects.create(name="Submission race", schema_name=uuid.uuid4().hex,
            owner=self.owner, creator=self.owner)
        Membership.objects.create(user=self.owner, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with workspace_context(self.tenant.pk):
                self.party = Party.objects.create(display_name="Borrower")
                self.product_version = _seed_default_loan_products()[0]
                type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
                self.license, self.series = self._configured_setup()
                values = command(self)
                token = new_draft_submission(workspace=self.tenant, actor=self.owner)
            barrier = Barrier(2)
            def submit(_):
                try:
                    with workspace_context(self.tenant.pk):
                        barrier.wait(timeout=10)
                        result, created = submit_new_draft(values, actor=self.owner, token=token, photos=(photo(),))
                        return result.pk, created
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(submit, range(2)))
            self.assertEqual(results[0][0], results[1][0])
            self.assertEqual({row[1] for row in results}, {True, False})
            with workspace_context(self.tenant.pk):
                self.assertEqual(PawnLoan.objects.count(), 1)
                self.assertEqual(PawnLoan.objects.get().collateral_items.get().photos.count(), 1)
                self.assertEqual(LoanNumberSequence.objects.get(series=self.series, document_kind="PAWN_LOAN").next_number, 2)
