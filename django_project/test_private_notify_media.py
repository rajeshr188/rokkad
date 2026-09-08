from pathlib import Path
from tempfile import TemporaryDirectory

from django.http import Http404
from django.test import RequestFactory, SimpleTestCase

from django_project.media import serve_public_media


class PrivateNotifyMediaTests(SimpleTestCase):
    def test_raw_artifact_paths_are_denied_but_public_media_remains_available(self):
        request = RequestFactory().get("/media/logo.txt")
        with TemporaryDirectory() as root:
            Path(root, "logo.txt").write_text("public")
            for path in ("notify_v2/artifacts/file.pdf", "other/../notify_v2/artifacts/file.pdf", "notify_v2\\artifacts\\file.pdf"):
                with self.subTest(path=path), self.assertRaises(Http404):
                    serve_public_media(request, path, document_root=root)
            response = serve_public_media(request, "logo.txt", document_root=root)
            try:
                self.assertEqual(b"".join(response.streaming_content), b"public")
            finally:
                response.close()
