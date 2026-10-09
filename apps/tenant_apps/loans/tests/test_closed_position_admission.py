"""Position admission keeps unknown past facts out of financial transactions."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile, ZIP_DEFLATED

from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.base import ContentFile
from django.db import connection, transaction, DatabaseError
from django.test import override_settings
from django.urls import reverse

from apps.tenancy.context import workspace_context, without_workspace_context
from apps.orgs.models import Company, Membership, Role
from apps.tenant_apps.party.models import Party
from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
from apps.tenant_apps.data_portability.tests.test_loan_archive import document as archive_document
from apps.tenant_apps.loans.services.closed_position import preview_closed_position, admit_closed_position, read_position
from apps.tenant_apps.loans.services.closed_position_portability import export_closed_position, parse_closed_position_file, preview_closed_position_file, admit_closed_position_file
from apps.tenant_apps.loans.services.closed_position_contract import encode
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.servicing_contract import get_servicing_position
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from .test_recorded_origination import RecordedOriginationTests
from .test_recorded_history import RecordedHistoryTests


class ClosedPositionAdmissionTests(RecordedOriginationTests):
    prepare_history = RecordedHistoryTests.prepare_history

    def setUp(self):
        super().setUp()
        self.prepare_position()

    def prepare_position(self):
        self.start_active_trial()
        self.prepare_history()
        self.document = dict(profile="loan-closed-position/1",
            source=dict(namespace=str(uuid4()), system="source-book", loan_id="loan-10"),
            loan=dict(number="P-0010", borrower_reference=dict(system="source-book", id="customer-1"),
                original_date=None, closed_on=None, original_principal=None, monthly_rate=None, tenure_months=None),
            position=dict(state="CLOSED", as_of=self.today.isoformat(), currency="INR", principal="0", interest="0", fees="0",
                custody="RETURNED_TO_BORROWER", basis="OWNER_CLOSED_POSITION", evidence_reference="Owner checked closed zero debt and returned jewellery."),
            earlier_history="UNAVAILABLE", retained_evidence=None)
        identity = PartyIdentity.objects.create(workspace=self.tenant, party_id=self.data["borrower_id"])
        SourceIdentity.objects.create(workspace=self.tenant, identity=identity, source_system="source-book", external_id="customer-1",
            accepted_digest="a"*64, local_digest="b"*64)
        self.mapping = dict(workspace_id=self.tenant.pk, actor=self.actor, borrower_id=self.data["borrower_id"], series_id=self.series.pk)

    def admit_position(self):
        summary, token = preview_closed_position(document=self.document, **self.mapping)
        loan, created = admit_closed_position(document=self.document, review_token=token, confirmed=True, **self.mapping)
        self.assertTrue(created)
        return loan, summary, token

    def retain_source(self):
        source = archive_document()
        source["source"].update(**self.document["source"])
        source["facts"].update(loan_number="P-0010", borrower_reference=self.document["loan"]["borrower_reference"],
            opened_on=None, closed_on=None, original_principal=None, reported_balance="0")
        self.document["retained_evidence"] = source
        evidence = accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=source,
            expected_sha256=digest(source), confirmed=True)
        self.mapping["evidence_id"] = evidence.public_id
        return evidence

    def test_minimal_closed_loan_has_zero_shared_position_without_dummy_terms_or_financial_history(self):
        before = m.PawnLoan.objects.count()
        summary, token = preview_closed_position(document=self.document, **self.mapping)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 1)
        loan, created = admit_closed_position(document=self.document, review_token=token, confirmed=True, **self.mapping)
        self.assertTrue(created)
        self.assertEqual(loan.state, "CLOSED")
        for field in ("product_version_id", "principal_amount", "monthly_interest_rate", "loan_date", "tenure_months", "policy_snapshot_id"):
            self.assertIsNone(getattr(loan, field))
        self.assertFalse(loan.collateral_items.exists())
        self.assertFalse(loan.releases.exists())
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertFalse(loan.disbursal_snapshots.exists())
        self.assertFalse(loan.repayment_schedules.exists())
        self.assertEqual(list(loan.loan_events.values_list("event_kind", flat=True)), ["MIGRATION_OPENING"])
        balance = get_pawn_loan_balance(loan, as_of_date=self.today)
        self.assertEqual((balance.total_due, balance.principal_disbursed, balance.interest_paid, balance.principal_paid), (0, 0, 0, 0))
        self.assertIsNone(balance.due_date)
        self.assertTrue(balance.financially_settled)
        self.assertTrue(balance.collateral_return_complete)
        self.assertEqual(get_pawn_loan_exposure(loan.pk, as_of_date=self.today).total_economic_exposure, 0)
        self.assertEqual(get_servicing_position(loan, as_of_date=self.today).balance.total_due, 0)
        self.assertFalse(transaction_completeness(loan, self.today).complete)
        self.assertEqual(summary["missing_original_details"], ["original_date", "closed_on", "original_principal", "monthly_rate", "tenure_months"])
        self.assertFalse(admit_closed_position(document=self.document, review_token=token, confirmed=True, **self.mapping)[1])
        self.seq.refresh_from_db(); self.assertEqual(self.seq.next_number, 11)
        from apps.tenant_apps.loans.selectors.interest_contract_inventory import interest_contract_inventory
        self.assertEqual(next(row for row in interest_contract_inventory() if row["loan_id"] == loan.pk)["status"], "VERIFIED_TERMINAL_POSITION")

    def test_known_original_terms_and_unknown_custody_remain_distinct(self):
        self.document["loan"].update(original_date=self.day.isoformat(), closed_on=self.today.isoformat(),
            original_principal="10000", monthly_rate="2", tenure_months=3)
        self.document["position"]["custody"] = "UNKNOWN"
        loan, _, _ = self.admit_position()
        self.assertEqual(loan.principal_amount, Decimal("10000"))
        self.assertFalse(get_pawn_loan_balance(loan, as_of_date=self.today).collateral_return_complete)
        with self.assertRaises(ValueError):
            get_pawn_loan_balance(loan, as_of_date=self.day)
        self.assertFalse(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=loan).exists())

    def test_stale_review_wrong_party_and_duplicate_number_roll_back(self):
        _, token = preview_closed_position(document=self.document, **self.mapping)
        changed = deepcopy(self.document); changed["position"]["custody"] = "UNKNOWN"
        before = m.PawnLoan.objects.count()
        with self.assertRaises(ValueError):
            admit_closed_position(document=changed, review_token=token, confirmed=True, **self.mapping)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        wrong = self.make_snapshot(save=False).loan.borrower_id
        with self.assertRaises(ValueError):
            preview_closed_position(document=self.document, **{**self.mapping, "borrower_id": wrong})
        loan, _, _ = self.admit_position()
        changed = deepcopy(self.document); changed["source"]["loan_id"] = "another-loan"
        changed["loan"]["number"] = "p-0010"
        with self.assertRaises(ValueError):
            preview_closed_position(document=changed, **self.mapping)
        changed = deepcopy(self.document); changed["loan"]["tenure_months"] = 12
        with self.assertRaises(ValueError):
            preview_closed_position(document=changed, **self.mapping)
        self.assertEqual(read_position(loan), self.document)

    def test_source_archive_remains_unchanged_and_ordinary_directory_suppresses_duplicate(self):
        evidence = self.retain_source()
        before = deepcopy(evidence.document)
        loan, _, _ = self.admit_position()
        self.assertEqual(loan.historical_import.archive_evidence_id, evidence.pk)
        evidence.refresh_from_db(); self.assertEqual(evidence.document, before)
        from apps.tenant_apps.loans.selectors.directory import unadmitted_historical_records
        self.assertFalse(unadmitted_historical_records(self.tenant.pk).exists())
        from apps.tenant_apps.loans.selectors.release_inventory import loan_release_inventory
        row = next(r for r in loan_release_inventory(as_of_date=self.today)["loans"] if r["loan_id"] == loan.pk)
        self.assertEqual(row["contract_profile"], "loan-closed-position/1")
        self.assertEqual(row["recorded_due"], 0)

    def test_nullable_native_terms_still_refused_by_model_and_database(self):
        seed = self.make_snapshot(save=False).loan
        seed.principal_amount = None
        with self.assertRaises(ValidationError):
            seed.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoan.objects.filter(pk=seed.pk).update(principal_amount=None)
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoan.objects.filter(pk=seed.pk).update(is_imported_closed_position=True, state="CLOSED",
                product_version_id=None, policy_snapshot_id=None)

    def test_restricted_role_cannot_reopen_change_terms_add_events_or_forge_incomplete_position(self):
        loan, _, _ = self.admit_position()
        other_workspace = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("closed_position_test_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
        try:
            with connection.cursor() as cursor: cursor.execute(f"SET LOCAL ROLE {role}")
            for values in (dict(state="ACTIVE"), dict(principal_amount=1), dict(is_imported_closed_position=False)):
                with self.subTest(values=values), self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoan.objects.filter(pk=loan.pk).update(**values)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.create(workspace=self.tenant, loan=loan, event_kind="REPAYMENT", effective_date=self.today,
                    payload={"values": {"principal": "1"}}, payload_fingerprint="c"*64, idempotency_key="forged-closed-payment")
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanPolicySnapshot.objects.bulk_create([m.LoanPolicySnapshot(workspace=self.tenant, loan=loan,
                    interest_method="SIMPLE", partial_month_method="FULL_MONTH", valuation_method="LATEST_APPRAISAL",
                    rounding_method="PER_ACCRUAL_PERIOD")])
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoan.objects.bulk_create([m.PawnLoan(workspace=self.tenant, license=self.series.license, series=self.series,
                    borrower_id=self.data["borrower_id"], loan_number="P-0999", state="CLOSED", is_imported_closed_position=True,
                    loan_date=None, tenure_months=None)])
                connection.check_constraints()
            with without_workspace_context(), workspace_context(other_workspace.pk):
                self.assertFalse(m.PawnLoan.objects.filter(pk=loan.pk).exists())
                self.assertFalse(m.HistoricalLoanImport.objects.filter(loan_id=loan.pk).exists())
                self.assertEqual(m.PawnLoan.objects.filter(pk=loan.pk).update(state="ACTIVE"), 0)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE"); cursor.execute(f"DROP OWNED BY {role}"); cursor.execute(f"DROP ROLE {role}")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_ordinary_detail_list_and_export_handle_unknown_terms(self):
        self.retain_source()
        loan, _, _ = self.admit_position()
        client = self.make_workspace_client(); client.force_login(self.actor)
        detail = reverse("workspace_loans:pawn_loan_detail", kwargs=dict(workspace_slug=self.tenant.slug, pk=loan.pk))
        self.assertContains(client.get(detail), "accepted zero-debt position")
        self.assertContains(client.get(detail), "Earlier financial history unavailable")
        listing = reverse("workspace_loans:pawn_loan_list", kwargs=dict(workspace_slug=self.tenant.slug))
        page = client.get(listing, dict(q="P-0010", records="ordinary"))
        self.assertContains(page, "P-0010")
        exported = client.post(reverse("workspace_portability:loan_export", kwargs=dict(workspace_slug=self.tenant.slug, loan_id=loan.pk)))
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(parse_closed_position_file(exported.content)[0], self.document)

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_portable_source_media_and_json_roundtrip_retry_and_tamper_refusal(self):
        evidence = self.retain_source()
        import hashlib
        content = b"source photograph fixture"
        attachment = m.HistoricalLoanAttachment(workspace=self.tenant, evidence=evidence, original_filename="original.jpg",
            mime_type="image/jpeg", byte_size=len(content), sha256=hashlib.sha256(content).hexdigest(),
            source_evidence=dict(source="source-book", item="item-1", verified_source_file=dict(sha256=hashlib.sha256(content).hexdigest())), imported_by=self.actor)
        attachment.file.save("fixture-source.jpg", ContentFile(content), save=False); attachment.save()
        loan, _, _ = self.admit_position()
        data, name = export_closed_position(workspace_id=self.tenant.pk, actor=self.actor, loan_id=loan.pk)
        self.assertTrue(name.endswith(".zip"))
        doc, claims, files = parse_closed_position_file(data)
        self.assertEqual(doc, self.document); self.assertEqual(files[attachment.sha256], content)
        summary, token = preview_closed_position_file(content=data, **self.mapping)
        same, created = admit_closed_position_file(content=data, review_token=token, confirmed=True, **self.mapping)
        self.assertEqual(same.pk, loan.pk); self.assertFalse(created)
        self.assertEqual(evidence.attachments.count(), 1)
        stream = BytesIO()
        with ZipFile(BytesIO(data)) as old, ZipFile(stream, "w", ZIP_DEFLATED) as new:
            for entry in old.namelist(): new.writestr(entry, b"tampered" if entry.startswith("media/") else old.read(entry))
        with self.assertRaises(ValueError): parse_closed_position_file(stream.getvalue())

    def test_unselected_source_requires_exact_party_mapping_and_current_owner_authority(self):
        self.document["loan"]["borrower_reference"]["id"] = "unmapped-customer"
        with self.assertRaises(ValueError): preview_closed_position(document=self.document, **self.mapping)
        with without_workspace_context():
            with self.assertRaises(PermissionDenied): preview_closed_position(document=self.document, **self.mapping)

    def test_new_retained_snapshot_invalidates_review_without_overwriting_evidence(self):
        evidence = self.retain_source()
        _, token = preview_closed_position(document=self.document, **self.mapping)
        changed = deepcopy(evidence.document)
        changed["source"]["snapshot_reference"] = "second source snapshot"
        accept_evidence(workspace_id=self.tenant.pk, actor=self.actor, document=changed,
            expected_sha256=digest(changed), confirmed=True)
        before = m.PawnLoan.objects.count()
        with self.assertRaises(ValueError):
            admit_closed_position(document=self.document, review_token=token, confirmed=True, **self.mapping)
        self.assertEqual(m.PawnLoan.objects.count(), before)
        evidence.refresh_from_db(); self.assertEqual(evidence.document, self.document["retained_evidence"])

    def test_retry_rechecks_current_owner_authority(self):
        loan, _, token = self.admit_position()
        from django.contrib.auth import get_user_model
        new_owner = get_user_model().objects.create_user(username="changed-position-owner")
        Company.all_objects.filter(pk=self.tenant.pk).update(owner=new_owner)
        with self.assertRaises(PermissionDenied):
            admit_closed_position(document=self.document, review_token=token, confirmed=True, **self.mapping)
        self.assertEqual(loan.loan_events.count(), 1)

    def test_source_systems_with_same_namespace_and_local_id_remain_distinct(self):
        first, _, _ = self.admit_position()
        changed = deepcopy(self.document)
        changed["source"]["system"] = "second: புத்தகம்"
        changed["loan"]["number"] = "P-0011"
        self.document = changed
        second, _, _ = self.admit_position()
        self.assertNotEqual(first.pk, second.pk)
        self.assertNotEqual(first.historical_import.source_id, second.historical_import.source_id)
        self.assertEqual(first.historical_import.source_namespace, second.historical_import.source_namespace)

    @override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_export_reimports_to_fresh_workspace_with_new_local_ids_and_exact_media(self):
        import hashlib
        evidence = self.retain_source()
        image = b"preserved source image bytes"
        checksum = hashlib.sha256(image).hexdigest()
        media = m.HistoricalLoanAttachment(workspace=self.tenant, evidence=evidence, original_filename="source.png",
            sha256=checksum, byte_size=len(image), mime_type="image/png",
            source_evidence=dict(verified_source_file=dict(sha256=checksum)), imported_by=self.actor)
        media.file.save("portable-source.png", ContentFile(image), save=False); media.save()
        source_loan, _, _ = self.admit_position()
        content, _ = export_closed_position(workspace_id=self.tenant.pk, actor=self.actor, loan_id=source_loan.pk)
        destination = Company.objects.create(name="Destination", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(destination.pk):
            Membership.objects.create(company=destination, user=self.actor, role=Role.objects.get_or_create(name="Owner")[0])
            start_workspace_trial(destination)
            borrower = Party.objects.create(display_name="Imported source borrower")
            licence = m.LoanLicense.objects.create(workspace=destination, name="Old book", license_number="Source-register",
                issued_on=self.day, expires_on=self.today + timedelta(days=365))
            series = m.LoanSeries.objects.create(license=licence, name="Old book", code="P")
            identity = PartyIdentity.objects.create(workspace=destination, party=borrower)
            SourceIdentity.objects.create(workspace=destination, identity=identity, source_system="source-book", external_id="customer-1",
                accepted_digest="a"*64, local_digest="b"*64)
            mapping = dict(workspace_id=destination.pk, actor=self.actor, borrower_id=borrower.pk, series_id=series.pk)
            _, token = preview_closed_position_file(content=content, **mapping)
            self.assertFalse(m.PawnLoan.objects.filter(workspace=destination).exists())
            restored, created = admit_closed_position_file(content=content, review_token=token, confirmed=True, **mapping)
            self.assertTrue(created); self.assertNotEqual(restored.pk, source_loan.pk)
            self.assertEqual(read_position(restored), self.document)
            self.assertEqual(get_pawn_loan_balance(restored, as_of_date=self.today).total_due, 0)
            self.assertFalse(restored.disbursal_snapshots.exists())
            imported_image = restored.historical_import.archive_evidence.attachments.get()
            with imported_image.file.open("rb") as stream: self.assertEqual(stream.read(), image)
            self.assertFalse(admit_closed_position_file(content=content, review_token=token, confirmed=True, **mapping)[1])
            self.assertEqual(restored.historical_import.archive_evidence.attachments.count(), 1)
