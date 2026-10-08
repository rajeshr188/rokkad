from unittest.mock import patch
from io import StringIO
import json

from django.core.exceptions import PermissionDenied
from django.core.management import call_command, CommandError
from django.db import connection

from apps.orgs.audit import AuditLog
from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.data_portability.tests.fixtures import PortabilityFixture
from apps.tenant_apps.party.models import Party, PartyAddress, PartyContactMethod
from apps.tenant_apps.party.services.contact_details import ensure_party_display_defaults
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget


class PartyDisplayDefaultsTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        start_workspace_trial(self.a)

    def repair(self, party, **kwargs):
        return ensure_party_display_defaults(workspace_id=self.a.pk, party_id=party.pk,
            actor=kwargs.get("actor", self.actor))

    def address(self, party, **kwargs):
        return PartyAddress.objects.create(party=party, address_type=kwargs.pop("address_type", "HOME"),
            line1=kwargs.pop("line1", "1 Fictional Street"), city="Town", **kwargs)

    def phone(self, party, **kwargs):
        return PartyContactMethod.objects.create(party=party,
            contact_type=kwargs.pop("contact_type", "PHONE"),
            value=kwargs.pop("value", "9876543210"), **kwargs)

    def test_fills_search_defaults_without_rewriting_values_and_retries_are_noops(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower")
            work = self.address(party, address_type="WORK")
            home = self.address(party, line1="2 Home Street")
            phone = self.phone(party)
            with connection.cursor() as cursor:
                cursor.execute("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                self.assertEqual(cursor.fetchone(), (False, False))
            self.assertEqual(self.repair(party),
                {"address_id": home.pk, "contact_id": phone.pk, "phone_summary": True})
            party.refresh_from_db(); phone.refresh_from_db(); work.refresh_from_db(); home.refresh_from_db()
            self.assertTrue(home.is_default); self.assertFalse(work.is_default)
            self.assertTrue(phone.is_primary); self.assertFalse(phone.is_verified)
            self.assertEqual(phone.value, "9876543210")
            self.assertEqual(party.primary_phone, phone.value)
            label = PartyAutocompleteWidget().label_from_instance(party)
            self.assertIn(phone.value, label); self.assertIn(str(home), label)
            self.assertEqual(self.repair(party),
                {"address_id": None, "contact_id": None, "phone_summary": False})
            logs = AuditLog.objects.filter(company=self.a)
            self.assertEqual(logs.count(), 3)
            self.assertEqual(set(logs.values_list("user_id", flat=True)), {self.actor.pk})
            self.assertNotIn(phone.value, str(list(logs.values_list("data", flat=True))))
            self.assertNotIn(home.line1, str(list(logs.values_list("data", flat=True))))

    def test_preserves_existing_default_and_primary_instead_of_preferring_new_home(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower", primary_phone="9876543211")
            work = self.address(party, address_type="WORK", is_default=True)
            home = self.address(party)
            self.phone(party)
            chosen = self.phone(party, value=party.primary_phone, is_primary=True)
            self.repair(party)
            party.refresh_from_db(); home.refresh_from_db(); chosen.refresh_from_db()
            self.assertFalse(home.is_default); self.assertTrue(chosen.is_primary)
            self.assertEqual(party.primary_phone, "9876543211")
            self.assertEqual(PartyAddress.objects.filter(is_default=True).get().pk, work.pk)
            self.assertEqual(AuditLog.objects.filter(company=self.a).count(), 0)

    def test_matches_existing_master_phone_before_oldest_contact(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower", primary_phone="9876543211")
            other = self.phone(party)
            chosen = self.phone(party, value=party.primary_phone)
            self.repair(party)
            other.refresh_from_db(); chosen.refresh_from_db(); party.refresh_from_db()
            self.assertFalse(other.is_primary); self.assertTrue(chosen.is_primary)
            self.assertEqual(party.primary_phone, "9876543211")

    def test_existing_primary_populates_empty_search_summary(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower")
            self.phone(party)
            chosen = self.phone(party, value="9876543211", contact_type="MOBILE", is_primary=True)
            result = self.repair(party)
            party.refresh_from_db()
            self.assertIsNone(result["contact_id"])
            self.assertTrue(result["phone_summary"])
            self.assertEqual(party.primary_phone, chosen.value)

    def test_missing_data_and_unrelated_master_phone_are_not_fabricated_or_replaced(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower")
            self.phone(party, value="", contact_type="PHONE")
            self.phone(party, value="fiction@example.test", contact_type="EMAIL")
            self.assertEqual(self.repair(party),
                {"address_id": None, "contact_id": None, "phone_summary": False})
            self.assertFalse(party.addresses.exists())
            party.primary_phone = "9876543212"
            party.save(update_fields=["primary_phone"])
            phone = self.phone(party)
            self.repair(party)
            phone.refresh_from_db(); party.refresh_from_db()
            self.assertFalse(phone.is_primary)
            self.assertEqual(party.primary_phone, "9876543212")

    def test_actor_and_workspace_boundaries_refuse_repairs(self):
        with self.scoped(self.b):
            foreign = Party.objects.create(display_name="Other Workspace borrower")
        with self.scoped():
            local = Party.objects.create(display_name="Local borrower")
            self.phone(local)
            with self.assertRaises(Party.DoesNotExist): self.repair(foreign)
            with self.assertRaises(PermissionDenied): self.repair(local, actor=self.other_actor)
            with self.assertRaises(PermissionDenied):
                ensure_party_display_defaults(workspace_id=self.b.pk, party_id=foreign.pk, actor=self.actor)
            self.assertFalse(local.contact_methods.get().is_primary)

    def test_audit_failure_rolls_back_address_phone_and_summary_together(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower")
            address = self.address(party); phone = self.phone(party)
            original = AuditLog.log
            def fail_summary(*args, **kwargs):
                if kwargs["data"]["operation"] == "PARTY_PRIMARY_PHONE_SYNC":
                    raise RuntimeError("Audit unavailable")
                return original(*args, **kwargs)
            with patch("apps.tenant_apps.party.services.contact_details.AuditLog.log", side_effect=fail_summary):
                with self.assertRaises(RuntimeError): self.repair(party)
            address.refresh_from_db(); phone.refresh_from_db(); party.refresh_from_db()
            self.assertFalse(address.is_default); self.assertFalse(phone.is_primary)
            self.assertEqual(party.primary_phone, "")
            self.assertFalse(AuditLog.objects.filter(company=self.a).exists())

    def test_command_previews_requires_unchanged_source_and_repeated_apply_is_safe(self):
        with self.scoped():
            party = Party.objects.create(display_name="Fictional borrower")
            address = self.address(party); phone = self.phone(party)
            def run(**kwargs):
                output = StringIO()
                call_command("repair_party_display_defaults", workspace_id=self.a.pk,
                    actor_id=self.actor.pk, stdout=output, **kwargs)
                return json.loads(output.getvalue())
            preview = run()
            self.assertFalse(preview["applied"])
            self.assertEqual(preview["candidate_count"], 1)
            self.assertFalse(AuditLog.objects.filter(company=self.a).exists())
            with self.assertRaises(CommandError): run(apply=True)
            phone.value = "9876543211"
            phone.save()
            with self.assertRaises(CommandError): run(apply=True, expected_digest=preview["digest"])
            address.refresh_from_db(); self.assertFalse(address.is_default)
            applied = run(apply=True, expected_digest=run()["digest"])
            self.assertEqual(applied["changes"],
                {"address_defaults": 1, "primary_contacts": 1, "phone_summaries": 1})
            self.assertEqual(applied["remaining"]["phone_primary_missing"], 0)
            again = run(apply=True, expected_digest=run()["digest"])
            self.assertEqual(sum(again["changes"].values()), 0)

    def test_command_respects_workspace_scope_and_does_not_expose_contact_values(self):
        with self.scoped(self.b):
            foreign = Party.objects.create(display_name="Foreign borrower")
            foreign_address = self.address(foreign); foreign_phone = self.phone(foreign)
        with self.scoped():
            party = Party.objects.create(display_name="Local borrower")
            self.address(party); self.phone(party)
            output = StringIO()
            call_command("repair_party_display_defaults", workspace_id=self.a.pk,
                actor_id=self.actor.pk, stdout=output)
            result = json.loads(output.getvalue())
            self.assertEqual(result["parties"], 1)
            self.assertNotIn("Fictional Street", output.getvalue())
            self.assertNotIn("9876543210", output.getvalue())
        with self.scoped(self.b):
            foreign_address.refresh_from_db(); foreign_phone.refresh_from_db()
            self.assertFalse(foreign_address.is_default); self.assertFalse(foreign_phone.is_primary)
