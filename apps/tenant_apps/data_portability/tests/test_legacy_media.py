import copy
import hashlib
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch
from uuid import UUID, uuid5

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management.base import CommandError
from django.db import DatabaseError, transaction
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, override_settings
from PIL import Image

from apps.orgs.models import Membership
from apps.tenant_apps.data_portability import legacy_media as service
from apps.tenant_apps.data_portability.legacy_media_storage import R2MediaCopies
from apps.tenant_apps.data_portability.loan_archive_views import attachment
from apps.tenant_apps.data_portability.models import LegacyMediaReceipt, PartyIdentity, SourceIdentity
from apps.tenant_apps.loans.models import HistoricalLoanAttachment, HistoricalLoanEvidence, PawnLoan, PawnLoanEvent
from apps.tenant_apps.loans.services.archive import accept_evidence
from apps.tenant_apps.loans.services.history_contract import digest
from apps.tenant_apps.party.models import Party, PartyDocument
from .fixtures import PortabilityFixture
from .test_loan_archive import document
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture

NAMESPACE = "6ca968d6-2647-4dbb-8e39-24f0c1a12ed6"
buffer = BytesIO()
Image.new("RGB", (2, 2)).save(buffer, "PNG")
PNG = buffer.getvalue()


def evidence(customer=True, default="t"):
    source = dict(schema="jcl", table="contact_customerpic" if customer else "girvi_loanitem", source_id="1",
                  parent_field="customer_id" if customer else "loan_id", parent_id="1", field="image" if customer else "pic",
                  stored_path="customer_pics/old.jpg" if customer else "loan_pics/old.jpg")
    sha = hashlib.sha256(PNG).hexdigest()
    result = dict(namespace=NAMESPACE, archive_sha256="a" * 64, source=source, status="EXACT_SOURCE_FILE_PRESERVED",
        verified_source_file=dict(bucket="test", object_key=f"media/legacy/{UUID(NAMESPACE).hex}/branch/jcl/{sha}/{source['stored_path']}",
                                  sha256=sha, byte_size=len(PNG), content_type="image/png"))
    if customer:
        result["customer_source"] = dict(schema="jcl", archive_sha256="a" * 64,
            source_row=dict(id="1", customer_id="1", image=source["stored_path"], is_default=default))
    return result


class LocalCopies:
    def __init__(self, root):
        self.root = Path(root)

    def prepare(self, names):
        for name in names.values():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(PNG)

    def verify(self, name, original):
        if hashlib.sha256((self.root / name).read_bytes()).hexdigest() != original["sha256"]:
            raise ValidationError("Hash mismatch")


class LegacyMediaTests(PortabilityFixture):
    def setUp(self):
        super().setUp()
        self.root = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=self.root, STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}))
        self.storage = LocalCopies(self.root)
        with self.scoped():
            self.party = Party.objects.create(display_name="Source customer", party_code="MEDIA")
            identity = PartyIdentity.objects.create(party=self.party)
            SourceIdentity.objects.create(identity=identity, source_system=f"legacy:{UUID(NAMESPACE).hex}:jcl",
                external_id=str(uuid5(uuid5(UUID(NAMESPACE), "jcl"), "contact_customer:1")),
                accepted_digest="a" * 64, local_digest="b" * 64)

    def attach(self, value=None):
        value = value or evidence()
        kind, _ = service.resolve_target(workspace_id=self.a.pk, actor=self.actor, evidence=value)
        self.storage.prepare(service.application_names(workspace_id=self.a.pk, evidence=value, kind=kind))
        return service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=value, storage=self.storage)

    def archive(self, value):
        doc = document()
        doc["source"].update(namespace=NAMESPACE, system=f"legacy:{UUID(NAMESPACE).hex}:jcl",
                             loan_id="girvi_loan:1", snapshot_reference="sha256:" + "a" * 64)
        doc["source_records"] = [{"source": {"external_id": "girvi_loanitem:1", "schema": "jcl"},
            "facts": {"loan_id": "1", "pic": value["source"]["stored_path"]}}]
        return accept_evidence(workspace_id=self.a.pk, actor=self.actor, document=doc,
                               expected_sha256=digest(doc), confirmed=True)

    def test_party_retains_all_photos_and_default_uses_independent_copy(self):
        with self.scoped():
            receipt, created = self.attach()
            self.assertTrue(created)
            self.party.refresh_from_db()
            photo = PartyDocument.objects.get()
            self.assertNotEqual(self.party.profile_photo.name, photo.file.name)
            self.assertTrue(photo.file.name.endswith(".png"))
            self.assertFalse(photo.is_verified)
            self.assertNotIn("legacy/", photo.file.name)
            repeated, created = self.attach()
            self.assertFalse(created)
            self.assertEqual(receipt.pk, repeated.pk)
            self.assertEqual(PartyDocument.objects.count(), 1)
            self.assertFalse(PawnLoan.objects.exists())

    def test_unknown_default_is_not_selected(self):
        with self.scoped():
            self.attach(evidence(default="f"))
            self.party.refresh_from_db()
            self.assertFalse(self.party.profile_photo)
            self.assertEqual(PartyDocument.objects.count(), 1)

    def test_removal_does_not_erase_other_copy_and_retry_does_not_restore(self):
        with self.scoped():
            receipt, _ = self.attach()
            self.party.refresh_from_db()
            self.party.profile_photo.delete()
            self.assertTrue((Path(self.root) / receipt.target["document_name"]).exists())
            _, created = service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=evidence(), storage=None)
            self.assertFalse(created)
            self.party.refresh_from_db()
            self.assertFalse(self.party.profile_photo)

    def test_existing_local_profile_is_not_overwritten(self):
        with self.scoped():
            self.party.profile_photo = "local.png"
            self.party.save(update_fields=["profile_photo"])
            with self.assertRaises(ValidationError):
                self.attach()
            self.assertFalse(LegacyMediaReceipt.objects.exists())
            self.assertFalse(PartyDocument.objects.exists())

    def test_changed_evidence_and_revoked_actor_block_retry(self):
        with self.scoped():
            self.attach()
            changed = evidence(default="f")
            with self.assertRaises(ValidationError):
                service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=changed, storage=None)
            Membership.objects.filter(company=self.a, user=self.actor).delete()
            with self.assertRaises(PermissionDenied):
                service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=evidence(), storage=None)

    def test_archive_append_and_private_route_preserve_accepted_document(self):
        with self.scoped():
            value = evidence(False)
            archive = self.archive(value)
            before = archive.document
            receipt, _ = self.attach(value)
            archive.refresh_from_db()
            self.assertEqual(archive.document, before)
            self.assertFalse(PawnLoanEvent.objects.exists())
            request = RequestFactory().get("/private/?inline=1")
            request.user, request.workspace = self.actor, self.a
            response = attachment(request, archive.public_id, receipt.target["attachment_id"])
            self.assertEqual(b"".join(response.streaming_content), PNG)
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["Content-Type"], "image/png")
            with patch("django.http.response.signals.request_finished.send"):
                response.close()
            with self.assertRaises(Http404):
                attachment(request, archive.public_id, receipt.target["attachment_id"] + 1)
            request.user = AnonymousUser()
            self.assertEqual(attachment(request, archive.public_id, receipt.target["attachment_id"]).status_code, 302)
        with self.scoped(self.b):
            request.user, request.workspace = self.actor, self.b
            with self.assertRaises(PermissionDenied):
                attachment(request, archive.public_id, receipt.target["attachment_id"])
            self.assertFalse(HistoricalLoanAttachment.objects.exists())
            self.assertFalse(LegacyMediaReceipt.objects.exists())

    def test_source_item_parent_path_and_archive_snapshot_must_match(self):
        with self.scoped():
            value = evidence(False)
            self.archive(value)
            for change in ("parent", "path", "snapshot"):
                changed = copy.deepcopy(value)
                if change == "parent": changed["source"]["parent_id"] = "2"
                elif change == "snapshot": changed["archive_sha256"] = "b" * 64
                else:
                    changed["source"]["stored_path"] = "loan_pics/other.jpg"
                    changed["verified_source_file"]["object_key"] = changed["verified_source_file"]["object_key"].replace("old.jpg", "other.jpg")
                with self.assertRaises((ValidationError, HistoricalLoanEvidence.DoesNotExist)):
                    service.resolve_target(workspace_id=self.a.pk, actor=self.actor, evidence=changed)
            self.assertFalse(LegacyMediaReceipt.objects.exists())

    def test_sql_immutability_and_cross_workspace_insert(self):
        with self.scoped():
            value = evidence(False)
            archive = self.archive(value)
            receipt, _ = self.attach(value)
            media = HistoricalLoanAttachment.objects.get()
            for query in (lambda: LegacyMediaReceipt.objects.filter(pk=receipt.pk).update(source_id="changed"),
                          lambda: LegacyMediaReceipt.objects.filter(pk=receipt.pk).delete(),
                          lambda: HistoricalLoanAttachment.objects.filter(pk=media.pk).update(file="changed"),
                          lambda: HistoricalLoanAttachment.objects.filter(pk=media.pk).delete()):
                with self.assertRaises(DatabaseError), transaction.atomic(): query()
        with self.scoped(self.b):
            values = {f.attname: getattr(media, f.attname) for f in media._meta.fields if f.name != "id"}
            values["workspace_id"] = self.b.pk
            with self.assertRaises(DatabaseError), transaction.atomic():
                HistoricalLoanAttachment.objects.bulk_create([HistoricalLoanAttachment(**values)])


class MediaStorageTests(SimpleTestCase):
    def test_interrupted_stream_restarts_the_get_and_checks_complete_bytes(self):
        from urllib3.exceptions import ReadTimeoutError
        adapter = object.__new__(R2MediaCopies)
        adapter.bucket = "test"
        broken = Mock()
        broken.__enter__ = Mock(return_value=broken)
        broken.__exit__ = Mock(return_value=False)
        broken.read.side_effect = ReadTimeoutError(None, None, "interrupted stream")
        adapter._request = Mock(side_effect=[{"Body": broken}, {"Body": BytesIO(PNG)}])
        with patch("apps.tenant_apps.data_portability.legacy_media_storage.time.sleep"):
            self.assertEqual(adapter._read("key", evidence()["verified_source_file"]), PNG)
        self.assertEqual(adapter._request.call_count, 2)
        broken.__exit__.assert_called_once()

    def test_confirmed_blank_source_images_are_not_presented_as_usable_photos(self):
        from helpers.legacy_media import BLANK_LEGACY_IMAGE_SHA256
        from apps.tenant_apps.loans.models import PawnCollateralPhoto
        sha = next(iter(BLANK_LEGACY_IMAGE_SHA256))
        self.assertTrue(PawnCollateralPhoto(sha256=sha, source_evidence={"legacy": True}).is_blank_legacy_image)
        self.assertFalse(PawnCollateralPhoto(sha256=sha).is_blank_legacy_image)
        self.assertTrue(HistoricalLoanAttachment(sha256=sha).is_blank_legacy_image)
        self.assertTrue(PartyDocument(metadata={"legacy_media": {"verified_source_file": {"sha256": sha}}}).is_blank_legacy_image)
        self.assertFalse(PartyDocument(metadata={}).is_blank_legacy_image)

    def test_operator_rejects_changed_input_and_wrong_database_before_copy(self):
        from apps.tenant_apps.data_portability.management.commands.linode_media import Command, checked_jsonl
        with TemporaryDirectory() as root:
            path = Path(root) / "source.jsonl"
            path.write_text('{}\n')
            with self.assertRaises(CommandError): checked_jsonl(path, '0' * 64)
        connection = Mock(settings_dict={"NAME": "normal-development"})
        with patch("apps.tenant_apps.data_portability.management.commands.linode_media.connection", connection), \
                self.assertRaises(CommandError):
            Command().handle(database="normal-development")
        connection.cursor.assert_not_called()

    def test_transport_retry_never_disables_certificate_verification(self):
        from botocore.exceptions import SSLError
        adapter = object.__new__(R2MediaCopies)
        adapter.client = Mock()
        adapter.client.get_object.side_effect = [SSLError(endpoint_url="https://example", error="UNEXPECTED_EOF"), {"ok": True}]
        with patch("apps.tenant_apps.data_portability.legacy_media_storage.time.sleep"):
            self.assertEqual(adapter._request("get_object"), {"ok": True})
        adapter.client.reset_mock()
        adapter.client.get_object.side_effect = SSLError(endpoint_url="https://example", error="CERTIFICATE_VERIFY_FAILED")
        with self.assertRaises(SSLError): adapter._request("get_object")
        self.assertEqual(adapter.client.get_object.call_count, 1)

    def test_candidates_and_cross_branch_originals_are_rejected(self):
        for change in ("candidate", "branch", "path"):
            value = evidence()
            if change == "candidate": value["status"] = "SHARED_CANDIDATE_UNVERIFIED"
            elif change == "branch": value["source"]["schema"] = "jsk"
            else: value["source"]["stored_path"] = "../photo.jpg"
            with self.assertRaises(ValidationError): service.validate_evidence(value)

    def test_r2_conditional_creation_validates_image_and_readback(self):
        storage = Mock(bucket_name="test", location="media/application/test", endpoint_url="https://test.r2.cloudflarestorage.com")
        storage.connection.meta.client.get_object.side_effect = lambda **kw: {"Body": BytesIO(PNG)}
        with patch("apps.tenant_apps.data_portability.legacy_media_storage.default_storage", storage):
            adapter = R2MediaCopies()
            adapter.prepare({"file": "legacy_import/photo.png"}, evidence()["verified_source_file"])
            kwargs = storage.connection.meta.client.put_object.call_args.kwargs
            self.assertEqual(kwargs["IfNoneMatch"], "*")
            self.assertEqual(kwargs["ContentType"], "image/png")
            self.assertTrue(kwargs["Key"].startswith("media/application/"))
            storage.connection.meta.client.delete_object.assert_not_called()
            from botocore.exceptions import ClientError
            storage.connection.meta.client.put_object.side_effect = ClientError(
                {"ResponseMetadata": {"HTTPStatusCode": 412}, "Error": {"Code": "PreconditionFailed"}}, "PutObject")
            adapter.verified.clear()
            adapter.prepare({"file": "legacy_import/photo.png"}, evidence()["verified_source_file"])
            adapter.verified.clear()
            storage.connection.meta.client.get_object.side_effect = lambda **kw: {"Body": BytesIO(b"changed")}
            with self.assertRaises(ValidationError): adapter.verify("legacy_import/photo.png", evidence()["verified_source_file"])


class ActiveLegacyMediaTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        from apps.tenant_apps.data_portability.models import LoanHistoryBatch
        self.root = self.enterContext(TemporaryDirectory())
        self.enterContext(override_settings(MEDIA_ROOT=self.root))
        self.storage = LocalCopies(self.root)
        with self.scoped():
            self.origin = self.write()
            value = evidence(False)
            source = self.review["source"]
            value["namespace"] = source["namespace"]
            value["source"]["schema"] = source["schema"]
            original = value["verified_source_file"]
            original["object_key"] = f"media/legacy/{UUID(value['namespace']).hex}/branch/{source['schema']}/{original['sha256']}/{value['source']['stored_path']}"
            LoanHistoryBatch.objects.create(workspace=self.a, profile="legacy-opening/1", state="COMPLETED",
                result=self.origin, created_by=self.actor, source_sha256=self.origin.source_sha256,
                document={"opening": self.origin.document, "source_evidence": {"archive_sha256": "a" * 64, "records": [
                    {"source": {"external_id": "girvi_loanitem:1", "schema": source["schema"]},
                     "facts": {"loan_id": "1", "pic": value["source"]["stored_path"]}}]}})
            self.value = value

    def test_active_photo_preserves_money_and_original_capture_is_unknown(self):
        from apps.tenant_apps.loans.models import PawnCollateralPhoto
        with self.scoped():
            before = list(PawnLoanEvent.objects.values())
            kind, item = service.resolve_target(workspace_id=self.a.pk, actor=self.actor, evidence=self.value)
            self.assertEqual(kind, "collateral")
            self.storage.prepare(service.application_names(workspace_id=self.a.pk, evidence=self.value, kind=kind))
            receipt, created = service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=self.value, storage=self.storage)
            self.assertTrue(created)
            photo = PawnCollateralPhoto.objects.get(pk=receipt.target["photo_id"])
            self.assertEqual(photo.collateral_item_id, item.pk)
            self.assertEqual(photo.workflow_source, "LEGACY_IMPORT")
            self.assertIn("capture date unknown", photo.get_workflow_source_display())
            self.assertEqual(list(PawnLoanEvent.objects.values()), before)
            _, created = service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=self.value, storage=None)
            self.assertFalse(created)
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnCollateralPhoto.objects.filter(pk=photo.pk).update(source_evidence={})

    def test_missing_copy_and_other_workspace_cannot_attach(self):
        with self.scoped():
            with self.assertRaises(FileNotFoundError):
                service.attach(workspace_id=self.a.pk, actor=self.actor, evidence=self.value, storage=self.storage)
            self.assertFalse(LegacyMediaReceipt.objects.exists())
        with self.scoped(self.b):
            from apps.tenant_apps.loans.models import HistoricalLoanEvidence
            with self.assertRaises(HistoricalLoanEvidence.DoesNotExist):
                service.resolve_target(workspace_id=self.b.pk, actor=self.actor, evidence=self.value)
