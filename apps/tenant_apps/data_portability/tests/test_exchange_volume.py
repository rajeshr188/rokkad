"""Large synthetic file layout, distinct from a full financial restore benchmark."""
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from django.test import SimpleTestCase, tag

from apps.tenant_apps.data_portability import exchange
from apps.tenant_apps.data_portability.contracts import dump


@tag("large_exchange_volume")
class ExchangeVolumeTests(SimpleTestCase):
    def test_jcl_closed_cohort_size_has_bounded_verifiable_manifest_and_files(self):
        namespace = str(uuid4())
        with TemporaryDirectory() as private:
            root = Path(private)
            (root / "chunks").mkdir()
            entries = []
            for i in range(1,26650):
                document = dict(profile="loan-closed-position/1",
                    source=dict(namespace=namespace, system="synthetic-book", loan_id=str(i)),
                    loan=dict(number=f"S{i:06d}", borrower_reference=dict(system="synthetic-book", id="synthetic-borrower"),
                        original_date=None, closed_on=None, original_principal=None, monthly_rate=None, tenure_months=None),
                    position=dict(state="CLOSED", as_of="2026-10-10", currency="INR", principal="0", interest="0", fees="0",
                        custody="RETURNED_TO_BORROWER", basis="OWNER_CLOSED_POSITION", evidence_reference="Synthetic source position, not real staff acceptance"),
                    earlier_history="UNAVAILABLE", retained_evidence=None)
                content = dump(document).encode()
                path = f"chunks/{i:06d}.json"
                (root/path).write_bytes(content)
                entries.append(dict(path=path, profile=document["profile"], count=1, bytes=len(content), sha256=exchange.sha(content), source_loan_ids=[i]))
            manifest = dict(profile=exchange.PROFILE, scope="PARTIAL", source_namespace=namespace,
                snapshot=dict(consistency="repeatable-read", captured_at="2026-10-10T00:00:00+00:00", as_of="2026-10-10"),
                include_loans=True, counts={**{p:0 for p in exchange.PARTY_MODELS}, "loans":26649}, chunks=entries, exclusions=exchange.EXCLUSIONS)
            manifest["sha256"] = exchange.sha(dump(manifest).encode())
            raw = dump(manifest).encode()
            self.assertLess(len(raw), exchange.MAX_MANIFEST)
            (root/"manifest.json").write_bytes(raw)
            checked = exchange.read_manifest(root, expected_sha256=manifest["sha256"])
            self.assertEqual(len(checked["chunks"]), 26649)
            for entry in checked["chunks"]:
                exchange.chunk_bytes(root, entry)
