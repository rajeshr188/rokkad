"""Independent entry preferences survive the reviewed fresh-business package."""

from apps.tenant_apps.loans import models as loans
from apps.tenant_apps.loans.services import business_setup_portability as setup
from apps.tenant_apps.loans.services.entry_purpose import (
    new_loan_entry_purpose as default_entry_purpose,
)
from apps.tenant_apps.data_portability import business_package as package
from . import test_business_package as package_fixtures
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture
from pathlib import Path
from tempfile import TemporaryDirectory
from django.test import override_settings


class EntryPreferencePackageTests(OpeningImportFixture):
    export = package_fixtures.BusinessPackageTests.export
    preview = package_fixtures.BusinessPackageTests.preview
    restore = package_fixtures.BusinessPackageTests.restore

    def setUp(self):
        super().setUp()
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "source"
        self.directory.mkdir()
        self.enterContext(
            override_settings(
                STORAGES={
                    "default": {
                        "BACKEND": "django.core.files.storage.FileSystemStorage"
                    },
                    "staticfiles": {
                        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
                    },
                },
                MEDIA_ROOT=Path(self.temp.name) / "storage",
            )
        )

    def test_entry_preferences_select_version_five_and_restore_scoped_meaning(self):
        with self.scoped():
            self.write()
            loans.LoanEntryPreference.objects.create(
                workspace=self.a, purpose="PAPER", updated_by=self.actor
            )
            loans.LoanEntryPreference.objects.create(
                workspace=self.a,
                license=self.series.license,
                series=self.series,
                purpose="DIRECT",
                updated_by=self.actor,
            )
            with self.assertRaisesMessage(ValueError, "profile 5"):
                setup.export_setup(
                    workspace_id=self.a.pk,
                    actor=self.actor,
                    save_file=lambda field: None,
                    version=4,
                )
            exported = self.export()
            self.assertEqual(exported["profile"], package.ENTRY_PROFILE)
        with self.scoped(self.b):
            review = self.preview(exported)
            receipt = self.restore(exported, review)
            self.assertEqual(receipt.summary["profile"], package.ENTRY_PROFILE)
            self.assertEqual(loans.LoanEntryPreference.objects.count(), 2)
            restored = loans.LoanSeries.objects.get()
            self.assertEqual(default_entry_purpose(workspace=self.b), "PAPER")
            self.assertEqual(
                default_entry_purpose(workspace=self.b, series_id=restored.pk), "DIRECT"
            )
            self.assertEqual(self.restore(exported, review).pk, receipt.pk)
