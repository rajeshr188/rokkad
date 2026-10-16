import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from scripts import browser_fixtures
from scripts.check_repository_hygiene import violations


class RepositoryHygieneTests(TestCase):
    def test_generated_paths_but_not_source_or_archived_documents(self):
        bad = ["staticfiles/admin/css/base.css", "outputs/proof.json", "media/photo.jpg",
               ".tmp/task/notes.md", "apps/__pycache__/models.pyc", "output/sample.pdf"]
        good = ["static/js/app.js", "apps/loans/static/logo.png",
                "docs/archive/reference/sample.pdf", "scripts/fixtures/bootstrap-5.3.8/manifest.json"]
        self.assertEqual(violations(bad + good), bad)

    def test_fixtures_are_available_without_outputs_or_network(self):
        assets = browser_fixtures.bootstrap_assets()
        self.assertEqual(set(assets), {"bootstrap.min.css", "bootstrap.bundle.min.js"})

    def test_modified_fixture_fails_before_browser_launch(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "manifest.json").write_text(json.dumps({"assets": {
                "bootstrap.min.css": {"sha384": "incorrect"}}}), encoding="utf-8")
            (root / "bootstrap.min.css").write_bytes(b"changed")
            with patch.object(browser_fixtures, "BOOTSTRAP", root):
                with self.assertRaisesRegex(ValueError, "integrity mismatch"):
                    browser_fixtures.bootstrap_assets()
