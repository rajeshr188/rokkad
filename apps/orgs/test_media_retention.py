"""Committed removals must not delete shared or historically referenced media."""
import tempfile

from django.core.files.base import ContentFile
from django.test import TestCase, override_settings

from apps.orgs import test_platform_console as console_tests
from apps.orgs.services.storage_references import collect_references
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party, PartyDocument, PartyPhoto
from apps.tenant_apps.party.services.photos import choose_photo, remove_photo, remember_profile_photo
from apps.tenant_apps.party.services.party_merge import merge_parties


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class MediaRetentionTests(TestCase):
    make_workspace = console_tests.PlatformConsoleTests.make_workspace
    subscription = console_tests.PlatformConsoleTests.subscription

    def setUp(self):
        console_tests.PlatformConsoleTests.setUp(self)
        self.subscription(5)
        media = tempfile.TemporaryDirectory(prefix="rokkad-retention-")
        self.addCleanup(media.cleanup)
        self.enterContext(override_settings(MEDIA_ROOT=media.name))
        self.enterContext(workspace_context(self.workspace.pk))

    def photo_party(self, name):
        party = Party.objects.create(display_name=name)
        party.profile_photo.save("fixture.jpg", ContentFile(b"synthetic private media"))
        remember_profile_photo(party, actor=self.owner)
        return party

    def test_default_replacement_and_selection_keep_both_gallery_files_after_commit(self):
        party = self.photo_party("Gallery")
        first = party.photos.get()
        with self.captureOnCommitCallbacks(execute=True):
            previous = party.profile_photo.name
            party.profile_photo.save("replacement.jpg", ContentFile(b"replacement"))
            remember_profile_photo(party, previous_name=previous, actor=self.owner)
        second = party.photos.exclude(pk=first.pk).get()
        with self.captureOnCommitCallbacks(execute=True):
            choose_photo(party=party, photo_id=first.pk, actor=self.owner)
        party.refresh_from_db()
        self.assertEqual(party.profile_photo.name, first.file.name)
        for photo in (first, second):
            self.assertTrue(photo.file.storage.exists(photo.file.name))

    def test_gallery_removal_retains_bytes_after_commit(self):
        party = self.photo_party("Removal")
        photo = party.photos.get()
        with self.captureOnCommitCallbacks(execute=True):
            remove_photo(party=party, photo_id=photo.pk, actor=self.owner)
        party.refresh_from_db()
        self.assertFalse(party.profile_photo)
        self.assertFalse(party.photos.exists())
        self.assertTrue(photo.file.storage.exists(photo.file.name))

    def test_clear_control_retains_bytes_after_commit(self):
        party = self.photo_party("Clear")
        storage, previous = party.profile_photo.storage, party.profile_photo.name
        with self.captureOnCommitCallbacks(execute=True):
            party.profile_photo = ""
            party.save(update_fields=["profile_photo"])
            remember_profile_photo(party, previous_name=previous, actor=self.owner)
        self.assertFalse(party.photos.exists())
        self.assertTrue(storage.exists(previous))

    def test_merge_retains_source_gallery_bytes_after_commit(self):
        target, source = self.photo_party("Target"), self.photo_party("Source")
        source_photo = source.photos.get()
        with self.captureOnCommitCallbacks(execute=True):
            merge_parties(target=target, source=source, actor=self.owner)
        self.assertTrue(target.photos.filter(file=source_photo.file.name).exists())
        self.assertTrue(source_photo.file.storage.exists(source_photo.file.name))

    def test_document_replacement_and_removal_preserve_receipt_source(self):
        from apps.tenant_apps.data_portability.models import LegacyMediaReceipt
        party = Party.objects.create(display_name="Document")
        document = PartyDocument.objects.create(party=party, title="Fixture", file=ContentFile(b"old", name="old.txt"))
        storage, old_name = document.file.storage, document.file.name
        LegacyMediaReceipt.objects.create(workspace=self.workspace, source_system="fixture", source_id="1",
            evidence_sha256="f"*64, source_evidence={"status":"EXACT_SOURCE_FILE_PRESERVED"},
            target={"kind":"party", "document_name":old_name}, imported_by=self.admin)
        with self.captureOnCommitCallbacks(execute=True):
            document.file.save("new.txt", ContentFile(b"new"))
        new_name = document.file.name
        with self.captureOnCommitCallbacks(execute=True):
            document.delete()
        self.assertTrue(storage.exists(old_name))
        self.assertTrue(storage.exists(new_name))
        refs = collect_references([self.workspace.pk])
        self.assertIn((self.workspace.pk, "historical_evidence"), refs[old_name])
        self.assertNotIn(new_name, refs)
