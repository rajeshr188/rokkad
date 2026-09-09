import posixpath
from pathlib import Path
from tempfile import TemporaryDirectory

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from django_project.media import serve_public_media


class PrivateNotifyMediaTests(SimpleTestCase):
    def test_raw_artifact_paths_are_denied_but_public_media_remains_available(self):
        request = RequestFactory().get("/media/logo.txt")
        with TemporaryDirectory() as root:
            Path(root, "company_logos").mkdir()
            Path(root, "company_logos/logo.txt").write_text("public")
            for path in ("notify_v2/artifacts/file.pdf", "other/../notify_v2/artifacts/file.pdf", "notify_v2\\artifacts\\file.pdf", "party_profile_photos/photo.jpg", "party_documents/1/kyc.pdf", "loans/collateral/photo.jpg", "loans/documents/file.pdf", "loans/regulatory/license.pdf", "company_logos/../party_documents/1/kyc.pdf", "unknown/file.txt"):
                target = Path(root, posixpath.normpath(path.replace("\\", "/")))
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"private evidence")
                with self.subTest(path=path), self.assertRaises(Http404):
                    serve_public_media(request, path, document_root=root)
            response = serve_public_media(request, "company_logos/logo.txt", document_root=root)
            try:
                self.assertEqual(b"".join(response.streaming_content), b"public")
            finally:
                response.close()
