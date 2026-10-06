"""Delegated preparation cannot approve, post or replay an owner admission."""
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied
from django.test import Client, override_settings
from django.urls import reverse

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import workspace_role_permissions
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.data_portability import loan_history, guided_openings
from apps.tenant_apps.loans.services.history_contract import encode
from . import test_loan_history as histories, test_guided_openings as registers, test_legacy_opening as legacy
from apps.tenant_apps.loans.tests import test_opening_import as openings


def importer(case):
    user = get_user_model().objects.create_user(username="delegated-preparer")
    role = Role.objects.create(name="Loan import preparation")
    Membership.objects.create(company=case.a, user=user, role=role)
    workspace_role_permissions(role, case.a).set(Permission.objects.filter(content_type__app_label="orgs",
        content_type__model="company", codename__in=("data_view", "data_import")))
    return user


class DelegatedHistoryTests(histories.LoanHistoryTests):
    def test_staff_prepare_owner_review_and_commit_only(self):
        with self.scoped():
            staff = importer(self)
            args = dict(workspace_id=self.a.pk, actor=staff)
            batch = loan_history.stage(**args, content=encode(histories.document()))
            loan_history.prepare(**args, batch_id=batch.public_id, values=self.mapping)
            batch.refresh_from_db()
            self.assertEqual(batch.state, "STAGED")
            self.assertEqual(batch.preview["profile"], "loan-import-preparation/1")
            self.assertEqual(batch.approval_digest, "")
            self.assertFalse(m.PawnLoan.objects.exists())
            for command, extra in ((loan_history.preview, dict(values=self.mapping)),
                    (loan_history.commit, dict(approval="", confirmed=True)), (loan_history.cancel, dict(confirmed=True))):
                with self.subTest(command=command.__name__), self.assertRaises(PermissionDenied):
                    command(**args, batch_id=batch.public_id, **extra)
            approval = loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
            loan_history.prepare(**args, batch_id=batch.public_id, values=self.mapping)
            with self.assertRaises(ValueError):
                loan_history.commit(**self.args, batch_id=batch.public_id, approval=approval, confirmed=True)
            approval = loan_history.preview(**self.args, batch_id=batch.public_id, values=self.mapping)
            origin = loan_history.commit(**self.args, batch_id=batch.public_id, approval=approval, confirmed=True)
            self.assertEqual(origin.imported_by_id, self.actor.pk)
            self.assertEqual(batch.created_by_id, staff.pk)

    def test_preparation_rejects_foreign_mapping_and_batch(self):
        with self.scoped():
            staff = importer(self)
            batch = loan_history.stage(workspace_id=self.a.pk, actor=staff, content=encode(histories.document()))
            changed = dict(self.mapping, series_id=999999999)
            with self.assertRaises(ValueError):
                loan_history.prepare(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id, values=changed)
            self.assertFalse(m.PawnLoan.objects.exists())
        with self.scoped(self.b), self.assertRaises(PermissionDenied):
            loan_history.get_batch(workspace_id=self.b.pk, actor=self.actor, batch_id=batch.public_id)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", ALLOWED_HOSTS=["testserver"], STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_staff_review_page_offers_preparation_without_commit(self):
        with self.scoped():
            staff = importer(self)
            batch = loan_history.stage(workspace_id=self.a.pk, actor=staff, content=encode(histories.document()))
            loan_history.prepare(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id, values=self.mapping)
        from apps.tenancy.testing import WorkspaceTestCase
        WorkspaceTestCase.start_active_trial(SimpleNamespace(tenant=self.a))
        client = Client()
        client.force_login(staff)
        response = client.get(reverse("workspace_portability:loan_batch", kwargs=dict(workspace_slug=self.a.slug, batch_id=batch.public_id)))
        self.assertContains(response, "Save preparation for owner review")
        self.assertNotContains(response, "Commit complete loan history")
        self.assertNotContains(response, "Validate and preview complete history")


class DelegatedRegisterTests(openings.OpeningImportFixture):
    def test_register_staff_preparation_creates_no_party_product_or_loan(self):
        with self.scoped():
            staff = importer(self)
            counts = tuple(model.objects.count() for model in (Party, m.LoanProductVersion, m.PawnLoan))
            batch = guided_openings.stage(workspace_id=self.a.pk, actor=staff, source_key="delegated-register",
                content=registers.csv_bytes([registers.row()]), filename="register.csv")
            mapping = dict(settings=dict(revision_id=self.review["mapping"]["licence_revision_id"], series_id=self.series.pk,
                cutover="2021-02-02", grace_days=3, reference="Checked paper register", rule_confirmed=True),
                borrowers={"borrower-1": "NEW"})
            guided_openings.prepare(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id, mapping=mapping)
            self.assertEqual(tuple(model.objects.count() for model in (Party, m.LoanProductVersion, m.PawnLoan)), counts)
            with self.assertRaises(PermissionDenied):
                guided_openings.preview(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id, mapping=mapping)
            reviewed, token = guided_openings.preview(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, mapping=mapping)
            self.assertEqual(reviewed.preview["issues"], [])
            result = guided_openings.commit(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, approval=token, confirmed=True)
            self.assertEqual(result.state, "COMPLETED")


class DelegatedLegacyTests(legacy.LegacyOpeningTests):
    def test_staff_can_stage_verified_source_but_cannot_approve_it(self):
        from apps.tenant_apps.data_portability import legacy_opening
        with self.scoped():
            staff = importer(self)
            batch = legacy_opening.stage(workspace_id=self.a.pk, actor=staff, archive_path="synthetic.dump",
                review=self.review, setup=self.setup)
            self.assertEqual(batch.created_by_id, staff.pk)
            self.assertEqual(batch.state, "STAGED")
            self.assertFalse(m.PawnLoan.objects.exists())
            with self.assertRaises(PermissionDenied):
                legacy_opening.preview(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id)
            from pathlib import Path
            from tempfile import TemporaryDirectory
            from io import StringIO
            from django.core.management import call_command
            from apps.tenant_apps.loans.services.history_contract import dump
            with TemporaryDirectory() as folder:
                source = Path(folder) / "opening.jsonl"
                source.write_text(dump(dict(profile="loan-opening-commit/1", review=self.review, setup=self.setup)) + "\n", encoding="utf-8")
                call_command("stage_legacy_opening", workspace_id=self.a.pk, actor_id=staff.pk,
                    dump="synthetic.dump", opening_file=str(source), stdout=StringIO())
            self.assertFalse(m.PawnLoan.objects.exists())
            with self.assertRaises(PermissionDenied):
                legacy_opening.commit(workspace_id=self.a.pk, actor=staff, batch_id=batch.public_id, approval="", confirmed=True)
            token = legacy_opening.preview(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id)
            result = legacy_opening.commit(workspace_id=self.a.pk, actor=self.actor, batch_id=batch.public_id, approval=token, confirmed=True)
            batch.refresh_from_db()
            self.assertEqual(batch.state, "COMPLETED")
            self.assertEqual(result.imported_by_id, self.actor.pk)
