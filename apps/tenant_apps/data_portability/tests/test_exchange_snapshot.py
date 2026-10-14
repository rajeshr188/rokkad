from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import json

from django.core.management import call_command, CommandError
from django.db import connection, connections

from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party, PartyContactMethod
from apps.tenant_apps.data_portability import exchange, services
from apps.tenant_apps.data_portability.models import WorkspaceNamespace
from .test_concurrency import PortabilityConcurrencyTests


class ExchangeSnapshotTests(PortabilityConcurrencyTests):
    def test_repeatable_snapshot_does_not_block_or_mix_concurrent_source_writes(self):
        with workspace_context(self.workspace.pk):
            first = Party.objects.create(display_name="Before one", party_code="S1")
            Party.objects.create(display_name="Before two", party_code="S2")
        original = services.export_parties
        changed = False

        def writer():
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET ROLE {self.role}")
                with workspace_context(self.workspace.pk):
                    with connection.cursor() as cursor:
                        cursor.execute("SET LOCAL lock_timeout = '1000ms'")
                    Party.objects.filter(pk=first.pk).update(display_name="After update")
                    Party.objects.create(display_name="After insert", party_code="S3")
                    PartyContactMethod.objects.create(party_id=first.pk, contact_type="EMAIL", value="after@example.com")
            finally:
                connections.close_all()

        def interleave(**values):
            nonlocal changed
            result = original(**values)
            if not changed:
                changed = True
                with ThreadPoolExecutor(max_workers=1) as pool:
                    pool.submit(writer).result(timeout=15)
            return result

        with TemporaryDirectory() as private, patch.object(exchange, "MAX_ROWS", 1), patch.object(services, "export_parties", side_effect=interleave):
            target = Path(private) / "complete"
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {self.role}")
            try:
                output = StringIO()
                call_command("portability_exchange", "export", workspace_id=self.workspace.pk, actor_id=self.actor.pk,
                    directory=str(target), party_only=True, stdout=output)
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
            doc = exchange.read_manifest(target)
            self.assertEqual(doc["snapshot"]["consistency"], "repeatable-read")
            self.assertEqual(doc["counts"]["party-master/1"], 2)
            self.assertEqual(doc["counts"]["party-contact/1"], 0)
            content = b"".join(exchange.chunk_bytes(target, entry) for entry in doc["chunks"])
            self.assertIn(b"Before one", content)
            self.assertNotIn(b"After", content)
            self.assertEqual(json.loads(output.getvalue())["sha256"], doc["sha256"])
        with workspace_context(self.workspace.pk):
            self.assertEqual(Party.objects.count(), 3)
            self.assertEqual(Party.objects.get(pk=first.pk).display_name, "After update")

    def test_failed_command_does_not_publish_output_or_leave_source_identities(self):
        with workspace_context(self.workspace.pk):
            borrower = Party.objects.create(display_name="Atomic export", party_code="S1")
            PartyContactMethod.objects.create(party=borrower, contact_type="EMAIL", value="first@example.com")
        with TemporaryDirectory() as private:
            target = Path(private) / "not-published"
            with patch.object(services, "export_children", side_effect=ValueError("Unsupported source data")):
                with self.assertRaises(CommandError):
                    call_command("portability_exchange", "export", workspace_id=self.workspace.pk, actor_id=self.actor.pk,
                        directory=str(target), party_only=True, stdout=StringIO())
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(private).iterdir()), [])
        with workspace_context(self.workspace.pk):
            self.assertFalse(WorkspaceNamespace.objects.exists())
