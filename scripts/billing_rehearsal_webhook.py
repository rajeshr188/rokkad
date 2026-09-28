"""Expose only the signed billing callback to a temporary HTTPS tunnel."""
import hmac
import hashlib
from io import BytesIO
import os
from pathlib import Path
import sys
from wsgiref.simple_server import WSGIRequestHandler, make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CALLBACK_PATH = "/subscriptions/webhook/razorpay/"
MAX_BODY = 256 * 1024


def callback_only(application, secret):
    if not secret:
        raise ValueError("A webhook signing secret is required.")

    def serve(environ, start_response):
        def reject(code):
            start_response(code, [("Content-Length", "0"), ("Cache-Control", "no-store")])
            return [b""]

        if (environ.get("PATH_INFO") != CALLBACK_PATH or environ.get("QUERY_STRING")
                or environ.get("REQUEST_METHOD") != "POST"):
            return reject("404 Not Found")
        try:
            length = int(environ.get("CONTENT_LENGTH", ""))
        except ValueError:
            return reject("400 Bad Request")
        if not 0 < length <= MAX_BODY or environ.get("HTTP_TRANSFER_ENCODING"):
            return reject("413 Content Too Large")
        raw = environ["wsgi.input"].read(length)
        signature = environ.get("HTTP_X_RAZORPAY_SIGNATURE", "")
        expected = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        if len(raw) != length or not signature.isascii() or not hmac.compare_digest(expected, signature):
            return reject("400 Bad Request")
        # Do not forward cookies, authorization or proxy-derived Workspace hosts.
        clean = {key: value for key, value in environ.items() if not key.startswith("HTTP_")}
        clean.update({"HTTP_HOST": "127.0.0.1", "HTTP_X_RAZORPAY_SIGNATURE": signature,
                      "HTTP_X_RAZORPAY_EVENT_ID": environ.get("HTTP_X_RAZORPAY_EVENT_ID", ""),
                      "wsgi.input": BytesIO(raw), "CONTENT_TYPE": "application/json"})
        return application(clean, start_response)

    return serve


class QuietHandler(WSGIRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    if os.environ.get("DJANGO_SETTINGS_MODULE") != "django_project.settings.billing_rehearsal":
        raise RuntimeError("Only isolated billing rehearsal settings are supported.")
    from scripts.start_web import check_runtime
    check_runtime()
    from django.conf import settings
    from django.core.wsgi import get_wsgi_application
    app = callback_only(get_wsgi_application(), settings.RAZORPAY_WEBHOOK_SECRET)
    with make_server("127.0.0.1", 8893, app, handler_class=QuietHandler) as server:
        print("Signed billing callback listener ready on loopback port 8893.", flush=True)
        server.serve_forever()
