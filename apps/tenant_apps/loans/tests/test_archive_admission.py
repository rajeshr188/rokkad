from copy import deepcopy
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import override_settings
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.archive import accept_evidence, export_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.services.archive_admission import preview_archive_admission, admit_archive_history, archive_origin
from apps.tenant_apps.loans.services.recorded_history import preview_recorded_history
from apps.tenant_apps.loans.services.import_identity import find_source_origin
from . import test_recorded_origination as fixtures
from . import test_recorded_history as history
from apps.tenant_apps.data_portability.tests import test_loan_archive as archives


class ArchiveAdmissionTests(fixtures.RecordedOriginationTests):
    prepare_history = history.RecordedHistoryTests.prepare_history
    row = history.RecordedHistoryTests.row

    @classmethod
    def get_test_schema_name(cls):
        return "archive-admission"

    def setUp(self):
        super().setUp()
        self.start_active_trial()
        self.prepare_history()
        self.prepare_archive()

    def prepare_archive(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", date=self.today.isoformat(),
            amount="10200", number="R-0009", recipient="Borrower", reference="receipt:1")])
        self.document = archives.document()
        self.document["source"].update(system="legacy:491cf2e499eb499cb55568f3a8d5caaa:jcl", loan_id="girvi_loan:10")
        self.document["facts"].update(loan_number="P-0010", opened_on=self.day.isoformat(), closed_on=self.today.isoformat(),
            original_principal="10000", reported_balance="0", borrower_reference=None,
            collateral=[dict(description="Ring", quantity=1, gross_weight="10", net_weight="9")],
            payments=[dict(id="receipt:1", date=self.today.isoformat(), amount="10200")])
        self.evidence = self.accept()
        self.archive_args = dict(self.args, evidence_id=self.evidence.public_id,
            reconciliation="Checked original agreement, cash book and signed return receipt; borrower identity verified.")

    def accept(self):
        return accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=self.document,
            expected_sha256=digest(self.document), confirmed=True)

    def preview(self):
        return preview_archive_admission(**self.archive_args, data=self.data)

    def admit(self, token):
        return admit_archive_history(**self.archive_args, data=self.data, review_token=token, confirmed=True)

    def test_closed_admission_retains_sources_links_balances_and_retry(self):
        original = export_evidence(workspace_id=self.tenant.pk, actor=self.actor, evidence_id=self.evidence.public_id)
        count = m.PawnLoan.objects.count()
        review, token = self.preview()
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.assertFalse(m.HistoricalLoanImport.objects.exists())
        loan, created = self.admit(token)
        self.assertTrue(created)
        self.assertFalse(self.admit(token)[1])
        self.assertEqual(loan.state, "CLOSED")
        self.assertEqual(loan.historical_import.archive_evidence_id, self.evidence.pk)
        self.assertEqual(loan.historical_import.source_id, "jcl:girvi_loan:10")
        self.assertEqual(archive_origin(self.evidence).loan_id, loan.pk)
        self.assertEqual(export_evidence(workspace_id=self.tenant.pk, actor=self.actor, evidence_id=self.evidence.public_id), original)
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
        self.assertEqual(get_pawn_loan_balance(loan, as_of_date=self.today).total_due, 0)
        self.assertEqual(get_pawn_loan_exposure(loan.pk, as_of_date=self.today).total_economic_exposure, 0)
        self.assertEqual(loan.collateral_items.get().custody_state, "WITH_CUSTOMER")
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertEqual(review["archive"]["snapshot_ids"], [self.evidence.pk])
        self.assertEqual(find_source_origin(workspace_id=self.tenant.pk, namespace=self.evidence.source_namespace,
            source_id=self.evidence.source_id, borrower_source_system=self.evidence.source_system).loan_id, loan.pk)

    def test_other_snapshot_links_existing_loan_and_cannot_duplicate(self):
        self.document["source"]["snapshot_reference"] = "Second scan"
        other = self.accept()
        _, token = self.preview()
        loan, _ = self.admit(token)
        self.assertEqual(archive_origin(other).loan_id, loan.pk)
        self.archive_args["evidence_id"] = other.public_id
        with self.assertRaisesMessage(ValueError, "already has"):
            self.preview()
        with self.assertRaisesMessage(ValueError, "already has"):
            self.admit(token)

    def test_unified_directory_replaces_all_admitted_snapshots_with_ordinary_loan(self):
        from apps.tenant_apps.loans.filters import PawnLoanFilter
        from apps.tenant_apps.loans.selectors.directory import loan_directory_page, unadmitted_historical_records
        self.document["source"]["snapshot_reference"] = "Second scan"
        self.accept()
        _, token = self.preview()
        loan, _ = self.admit(token)
        self.assertFalse(unadmitted_historical_records(self.tenant.pk).exists())
        filtered = PawnLoanFilter({'q':'P-0010','state':'CLOSED'},
            queryset=m.PawnLoan.objects.filter(workspace=self.tenant),workspace=self.tenant)
        page, _ = loan_directory_page(workspace_id=self.tenant.pk,loan_filter=filtered,page=1)
        self.assertEqual(page.paginator.count,1)
        self.assertEqual(page.object_list,[dict(kind='ordinary',loan=loan)])
        self.assertEqual(m.HistoricalLoanEvidence.objects.count(),2)

    def test_invalid_legacy_scope_cannot_hide_archive_using_an_unscoped_match(self):
        from apps.tenant_apps.loans.selectors.directory import unadmitted_historical_records
        _, token = self.preview()
        loan, _ = self.admit(token)
        self.document['source'].update(system=f'legacy:{uuid4().hex}:jcl',
                                       loan_id=loan.historical_import.source_id)
        self.document['facts'].update(borrower_reference=None,payments=None)
        unmatched = self.accept()
        self.assertEqual(list(unadmitted_historical_records(self.tenant.pk)),[unmatched])

    def test_older_unscoped_import_hides_only_its_evidenced_legacy_schema(self):
        from apps.tenant_apps.loans.selectors.directory import unadmitted_historical_records
        snapshot = self.make_snapshot()
        m.HistoricalLoanImport.objects.create(workspace=self.tenant,loan=snapshot.loan,
            source_namespace=self.evidence.source_namespace,source_id=self.evidence.source_id,source_sha256='a'*64,
            document={'profile':'old-history','loan':{'id':self.evidence.source_id,
                'borrower':{'source_system':self.evidence.source_system}}},references={},imported_by=self.actor)
        self.document['source']['system'] = self.evidence.source_system.replace(':jcl',':jsk')
        other = self.accept()
        self.assertEqual(list(unadmitted_historical_records(self.tenant.pk)),[other])

    def test_snapshot_added_after_preview_requires_new_review(self):
        _, token = self.preview()
        self.document["source"]["snapshot_reference"] = "New source page"
        self.accept()
        with self.assertRaisesMessage(ValueError, "changed"):
            self.admit(token)
        self.assertFalse(m.HistoricalLoanImport.objects.exists())

    def test_conflicting_snapshot_cannot_be_ignored_by_selecting_older_evidence(self):
        self.document["source"]["snapshot_reference"] = "Contradictory source page"
        self.document["facts"]["original_principal"] = "9000"
        self.accept()
        with self.assertRaisesMessage(ValueError, "principal conflicts"):
            self.preview()

    def test_known_claim_conflicts_and_missing_receipts_are_refused(self):
        original = deepcopy(self.data)
        for key, value in (("principal", "11000"), ("number", "P-0020"), ("net_weight", "8"),
                           ("date", (self.day-timedelta(days=1)).isoformat())):
            self.data = dict(original, **{key:value})
            if key == "principal":
                self.data["cash_paid"] = value
            with self.assertRaises(ValueError):
                self.preview()
        self.data = deepcopy(original)
        self.data["events"][0]["reference"] = "Different receipt"
        with self.assertRaisesMessage(ValueError, "Include archived receipt"):
            self.preview()
        self.assertFalse(m.HistoricalLoanImport.objects.exists())

    def test_missing_archive_facts_can_be_supplied_with_checked_sources(self):
        self.document["source"]["loan_id"] = "girvi_loan:11"
        self.document["facts"].update(loan_number="P-0011", original_principal=None, payments=None, collateral=None)
        evidence = self.accept()
        self.archive_args["evidence_id"] = evidence.public_id
        self.data["number"] = "P-0011"
        _, token = self.preview()
        self.assertTrue(self.admit(token)[1])

    def test_manual_entry_cannot_bypass_retained_archive_or_admitted_number(self):
        with self.assertRaisesMessage(ValueError, "historical evidence"):
            preview_recorded_history(**self.args, data=self.data)
        _, token = self.preview()
        self.admit(token)
        with self.assertRaises(ValueError):
            preview_recorded_history(**self.args, data=self.data)

    def test_failure_rolls_back_loan_and_source_claim_together(self):
        _, token = self.preview()
        count = m.PawnLoan.objects.count()
        with patch.object(m.HistoricalLoanImport.objects, "create", side_effect=ValueError("Link failed")):
            with self.assertRaisesMessage(ValueError, "Link failed"):
                self.admit(token)
        self.assertEqual(m.PawnLoan.objects.count(), count)
        self.assertFalse(m.HistoricalLoanImport.objects.exists())

    def test_changed_review_and_missing_confirmation_are_refused(self):
        _, token = self.preview()
        with self.assertRaisesMessage(ValueError, "Confirm"):
            admit_archive_history(**self.archive_args, data=self.data, review_token=token)
        self.archive_args["reconciliation"] = "Different supporting records"
        with self.assertRaisesMessage(ValueError, "changed"):
            self.admit(token)

    def test_actor_authority_and_tampered_token_are_refused(self):
        from django.contrib.auth import get_user_model
        outsider = get_user_model().objects.create_user(username="archive-outsider")
        with self.assertRaises(PermissionDenied):
            preview_archive_admission(**dict(self.archive_args, actor=outsider), data=self.data)
        _, token = self.preview()
        with self.assertRaisesMessage(ValueError, "missing or expired"):
            self.admit(token + "changed")

    def test_complete_history_and_opening_routes_cannot_readmit_same_source(self):
        from apps.tenant_apps.data_portability.tests.test_loan_history import document
        from apps.tenant_apps.loans.services.history_import import import_complete_history
        from apps.tenant_apps.loans.services.opening_import import preview_opening_import
        from .test_opening_continuation import collection_review
        _, token = self.preview()
        self.admit(token)
        other = document()
        other["manifest"]["namespace"] = str(self.evidence.source_namespace)
        other["loan"]["id"] = self.evidence.source_id
        other["loan"]["borrower"]["source_system"] = self.evidence.source_system
        with self.assertRaisesMessage(ValueError, "different accepted history"):
            import_complete_history(workspace_id=self.tenant.pk, actor=self.actor, document=other,
                mapping=dict(revision_id=1, series_id=self.series.pk, product_version_id=self.data["product_version_id"], borrower_id=self.data["borrower_id"]))
        review = collection_review()
        review["source"].update(namespace=str(self.evidence.source_namespace), schema="jcl", loan_id=self.evidence.source_id)
        review["mapping"].update(workspace_id=self.tenant.pk, borrower_source_system=self.evidence.source_system)
        review["terms"]["maturity_date"] = "2021-04-01"
        review["obligations"][0].update(due="2021-04-01", interest="30")
        with self.assertRaisesMessage(ValueError, "different accepted financial origin"):
            preview_opening_import(workspace_id=self.tenant.pk, actor=self.actor, review=review,
                setup=dict(tenure_months=3, source_license_number="OLD-L", policy=other["loan"]["policy"]))

    def test_existing_financial_origin_blocks_archive_even_with_different_number(self):
        snapshot = self.make_snapshot()
        m.HistoricalLoanImport.objects.create(workspace=self.tenant, loan=snapshot.loan,
            source_namespace=self.evidence.source_namespace, source_id="jcl:girvi_loan:10", source_sha256="a"*64,
            document={"profile":"old-opening"}, references={}, imported_by=self.actor)
        with self.assertRaisesMessage(ValueError, "already has"):
            self.preview()

    def test_borrower_mapping_conflict_is_refused(self):
        from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
        from apps.tenant_apps.party.models import Party
        self.document["source"]["snapshot_reference"] = "Mapped borrower source"
        self.document["facts"]["borrower_reference"] = dict(system=self.evidence.source_system, id="customer:1")
        self.accept()
        party = Party.objects.create(workspace=self.tenant, display_name="Different borrower")
        parent = PartyIdentity.objects.create(workspace=self.tenant, party=party)
        SourceIdentity.objects.create(workspace=self.tenant, identity=parent, source_system=self.evidence.source_system,
            external_id="customer:1", accepted_digest="a"*64, local_digest="a"*64)
        with self.assertRaisesMessage(ValueError, "borrower differs"):
            self.preview()

    def assert_cross_workspace_link_refused(self, loan, other):
        with self.assertRaisesMessage(DatabaseError, "Invalid archive admission binding"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("""INSERT INTO loans_historicalloanimport
                    (public_id, workspace_id, loan_id, archive_evidence_id, source_namespace, source_id,
                     source_sha256, document, "references", imported_by_id, imported_at)
                    SELECT %s, %s, loan_id, archive_evidence_id, source_namespace, source_id, source_sha256,
                        document, "references", imported_by_id, imported_at FROM loans_historicalloanimport WHERE loan_id=%s""",
                    [uuid4(), other.pk, loan.pk])

    def test_restricted_role_links_immutable_source_and_hides_foreign_workspace(self):
        from apps.orgs.models import Company
        from apps.tenancy.context import without_workspace_context, workspace_context
        other = Company.objects.create(name="Other", schema_name="archive-other", owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("archive_admit_"+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            _, token = self.preview()
            loan, _ = self.admit(token)
            self.assert_cross_workspace_link_refused(loan, other)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.HistoricalLoanImport.objects.filter(loan=loan).update(archive_evidence=None)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.HistoricalLoanImport.objects.filter(loan=loan).delete()
            connection.check_constraints()
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.HistoricalLoanImport.objects.filter(loan_id=loan.pk).exists())
                with self.assertRaises(PermissionDenied):
                    self.preview()
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_ordinary_form_archive_review_and_bidirectional_links(self):
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_create", kwargs={"workspace_slug":self.tenant.slug})
        response = client.get(url, dict(entry="paper", archive=str(self.evidence.public_id)))
        self.assertContains(response, "Reconcile historical loan")
        post = {k:v for k,v in self.data.items() if k != "events"}
        post.update(entry_mode="paper", archive_evidence_id=str(self.evidence.public_id),
            reconciliation=self.archive_args["reconciliation"], intent_token=response.context["intent_token"],
            action="preview", **{"events-TOTAL_FORMS":"1", "events-INITIAL_FORMS":"0"})
        post.update({"events-0-"+k:v if v is not None else "" for k,v in self.data["events"][0].items()})
        response = client.post(url, post)
        self.assertEqual(response.context["form"].errors, {})
        self.assertTrue(response.context["review"], response.context["rows"].errors)
        self.assertContains(response, "checked source snapshots")
        import os
        from pathlib import Path
        if os.environ.get("PAPER_QA_CAPTURE"):
            Path("/qa/archive-review.html").write_bytes(response.content)
        post.update(action="confirm", confirm_review="on", review_token=response.context["review_token"])
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response.url), "retained historical evidence and attachments")
        archive_url = reverse("workspace_portability:archive_detail", kwargs={"workspace_slug":self.tenant.slug,"evidence_id":self.evidence.public_id})
        self.assertContains(client.get(archive_url), "linked to ordinary loan")
        self.assertEqual(client.post(url, post).status_code, 302)


class ArchiveAdmissionConcurrencyTests(history.RecordedHistoryConcurrencyTests):
    prepare_archive = ArchiveAdmissionTests.prepare_archive
    row = ArchiveAdmissionTests.row
    accept = ArchiveAdmissionTests.accept

    def setUp(self):
        super().setUp()
        from apps.tenancy.testing import start_workspace_trial
        from apps.tenancy.context import workspace_context
        start_workspace_trial(self.tenant)
        with workspace_context(self.tenant.pk):
            self.prepare_archive()
            _, token = preview_archive_admission(**self.archive_args, data=self.data)
            self.commit = dict(self.archive_args, data=self.data, review_token=token, confirmed=True)

    def race(self, submissions):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        from apps.tenancy.context import workspace_context
        ready = Barrier(2)
        def submit(values):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.tenant.pk):
                    loan, created = admit_archive_history(**values)
                    return loan.pk, created
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(submit, submissions))

    def test_distinct_submissions_for_same_paper_loan_cannot_both_commit(self):
        from apps.tenancy.context import workspace_context
        other = dict(self.commit, reconciliation="Different checked supporting page")
        with workspace_context(self.tenant.pk):
            args = {k:v for k,v in other.items() if k not in ("confirmed", "review_token")}
            _, other["review_token"] = preview_archive_admission(**args)
        results = self.race([self.commit, other])
        self.assertEqual(sum(row is not None for row in results), 1)
