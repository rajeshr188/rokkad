import json
from datetime import date
from io import StringIO
from unittest.mock import patch
from uuid import uuid4, uuid5

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import connection

from apps.orgs.audit import AuditLog
from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.data_portability.models import PartyIdentity, SourceIdentity
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.data_portability.tests.test_loan_archive import document
from apps.tenant_apps.loans.models import HistoricalLoanEvidence, LoanLicense, LoanSeries, PawnLoan
from apps.tenant_apps.loans.services.archive_contract import review_document
from apps.tenant_apps.loans.services.customer_status import repair_customer_statuses
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party


class CustomerStatusRepairTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        start_workspace_trial(self.a)

    def run_repair(self, **kwargs):
        return repair_customer_statuses(workspace_id=self.a.pk, actor=self.actor, **kwargs)

    def apply(self):
        return self.run_repair(apply=True, expected_digest=self.run_repair()["digest"])

    def loan(self, party, state):
        licence, _ = LoanLicense.objects.get_or_create(workspace=self.a, license_number="TEST-L",
            defaults={"name": "Test licence", "issued_on": date(2026, 1, 1), "expires_on": date(2027, 1, 1)})
        series, _ = LoanSeries.objects.get_or_create(license=licence, code="T", defaults={"name": "Test"})
        return PawnLoan.objects.create(workspace=self.a, license=licence, series=series, borrower=party,
            product_version=ensure_test_product_version(self.a), loan_number="T" + str(party.pk), state=state,
            principal_amount=1000, monthly_interest_rate=2, loan_date=date(2026, 1, 1))

    def archive(self, party, *, namespace=None, system=None, external="contact_customer:1"):
        namespace = namespace or uuid4()
        system = system or f"legacy:{namespace.hex}:jcl"
        identity, _ = PartyIdentity.objects.get_or_create(party=party)
        SourceIdentity.objects.create(identity=identity, source_system=system,
            external_id=str(uuid5(uuid5(namespace, "jcl"), external)), accepted_digest="a" * 64, local_digest="b" * 64)
        return self.evidence(namespace, system, external)

    def evidence(self, namespace, system, external):
        value = document()
        value["source"].update(namespace=str(namespace), system=system, loan_id="girvi_loan:1")
        value["facts"]["borrower_reference"] = {"system": system, "id": external}
        review = review_document(value)
        return HistoricalLoanEvidence.objects.create(source_namespace=namespace, source_system=system,
            source_id="girvi_loan:1", source_sha256=review["source_sha256"], review=review,
            accepted_by=self.actor, document=value)

    def test_all_ordinary_states_count_and_only_status_metadata_changes(self):
        with self.scoped():
            borrowers = []
            for state in ("DRAFT", "APPROVED", "ACTIVE", "CLOSED", "CANCELLED"):
                party = Party.objects.create(display_name=state, status="INACTIVE", credit_hold=True,
                    primary_phone="9876543210", metadata={"source_note": "keep"})
                self.loan(party, state); borrowers.append(party)
            none = Party.objects.create(display_name="No loans")
            with connection.cursor() as cursor:
                cursor.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                self.assertEqual(cursor.fetchone(), (False, False))
            before = list(PawnLoan.objects.order_by("pk").values())
            preview = self.run_repair()
            self.assertEqual(preview["counts"]["activate"], 5)
            self.assertFalse(AuditLog.objects.filter(company=self.a).exists())
            self.assertEqual(self.apply()["changed"], 6)
            for party in borrowers:
                party.refresh_from_db(); self.assertEqual(party.status, "ACTIVE")
                self.assertTrue(party.credit_hold)
                self.assertEqual(party.primary_phone, "9876543210")
                self.assertEqual(party.metadata, {"source_note": "keep"})
                self.assertEqual(party.updated_by_id, self.actor.pk)
            none.refresh_from_db(); self.assertEqual(none.status, "INACTIVE")
            self.assertEqual(before, list(PawnLoan.objects.order_by("pk").values()))
            self.assertEqual(self.apply()["changed"], 0)
            self.assertEqual(AuditLog.objects.filter(company=self.a).count(), 6)
            self.assertEqual(set(AuditLog.objects.filter(company=self.a).values_list("user_id", flat=True)), {self.actor.pk})

    def test_exact_legacy_borrower_alias_keeps_historical_only_customer_active(self):
        with self.scoped():
            party = Party.objects.create(display_name="Historical borrower", status="INACTIVE")
            archive = self.archive(party)
            before = archive.document.copy()
            self.assertEqual(self.run_repair()["counts"]["historical_only"], 1)
            self.apply(); party.refresh_from_db(); archive.refresh_from_db()
            self.assertEqual(party.status, "ACTIVE"); self.assertEqual(archive.document, before)
            self.assertFalse(PawnLoan.objects.exists())
            self.assertEqual(AuditLog.objects.get(company=self.a).data["retained_historical_loan"], True)

    def test_exact_nonlegacy_alias_is_supported(self):
        with self.scoped():
            party = Party.objects.create(display_name="Paper borrower", status="INACTIVE")
            identity = PartyIdentity.objects.create(party=party)
            SourceIdentity.objects.create(identity=identity, source_system="paper-book", external_id="customer-1",
                accepted_digest="a" * 64, local_digest="b" * 64)
            self.evidence(uuid4(), "paper-book", "customer-1")
            self.apply(); party.refresh_from_db(); self.assertEqual(party.status, "ACTIVE")

    def test_unmatched_archive_and_namespace_mismatch_block_changes_instead_of_guessing_names(self):
        with self.scoped():
            party = Party.objects.create(display_name="Same name")
            namespace = uuid4()
            self.archive(party, namespace=uuid4(), system=f"legacy:{namespace.hex}:jcl")
            self.assertEqual(self.run_repair()["unresolved_archives"], 1)
            with self.assertRaises(ValidationError): self.apply()
            party.refresh_from_db(); self.assertEqual(party.status, "ACTIVE")
            self.assertFalse(AuditLog.objects.filter(company=self.a).exists())

    def test_preview_expires_when_new_loan_is_created(self):
        with self.scoped():
            party = Party.objects.create(display_name="Borrower")
            preview = self.run_repair()
            self.loan(party, "DRAFT")
            with self.assertRaises(ValidationError):
                self.run_repair(apply=True, expected_digest=preview["digest"])
            party.refresh_from_db(); self.assertEqual(party.status, "ACTIVE")

    def test_status_and_audit_rollback_together(self):
        with self.scoped():
            party = Party.objects.create(display_name="No loans")
            with patch("apps.tenant_apps.loans.services.customer_status.AuditLog.log", side_effect=RuntimeError("Unavailable")):
                with self.assertRaises(RuntimeError): self.apply()
            party.refresh_from_db(); self.assertEqual(party.status, "ACTIVE")

    def test_protected_merge_or_block_requires_review(self):
        with self.scoped():
            for status in ("BLOCKED", "ARCHIVED"):
                Party.objects.create(display_name=status, status=status)
            self.assertEqual(self.run_repair()["counts"]["protected"], 2)
            with self.assertRaises(ValidationError): self.apply()

    def test_permission_and_workspace_isolation(self):
        with self.scoped(self.b):
            foreign = Party.objects.create(display_name="Foreign borrower")
            self.archive(foreign)
        with self.scoped():
            local = Party.objects.create(display_name="Local customer")
            with self.assertRaises(PermissionDenied):
                repair_customer_statuses(workspace_id=self.a.pk, actor=self.other_actor)
            with self.assertRaises(PermissionDenied):
                repair_customer_statuses(workspace_id=self.b.pk, actor=self.actor)
            self.assertEqual(self.run_repair()["parties"], 1)
            self.assertEqual(self.run_repair()["counts"]["active"], 0)
            self.apply(); local.refresh_from_db(); self.assertEqual(local.status, "INACTIVE")
        with self.scoped(self.b):
            foreign.refresh_from_db(); self.assertEqual(foreign.status, "ACTIVE")

    def test_command_is_aggregate_only_and_requires_preview(self):
        with self.scoped():
            Party.objects.create(display_name="Private customer", primary_phone="9876543210")
            def command(**kwargs):
                output = StringIO()
                call_command("repair_customer_statuses", workspace_id=self.a.pk, actor_id=self.actor.pk, stdout=output, **kwargs)
                self.assertNotIn("Private customer", output.getvalue())
                self.assertNotIn("9876543210", output.getvalue())
                return json.loads(output.getvalue())
            with self.assertRaises(CommandError): command(apply=True)
            result = command(apply=True, expected_digest=command()["digest"])
            self.assertEqual(result["changed"], 1)
