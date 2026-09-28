"""Short-lived loopback credential entry. No Django, payment writes or request logs."""
import ctypes
from ctypes import wintypes
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import time
from urllib.parse import parse_qs

import requests


ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / "outputs" / "razorpay-test-form-status.json"


def protect(data):
    """Encrypt the whole credential using current-user Windows DPAPI."""
    if os.name != "nt":
        raise RuntimeError("Windows required")

    class Blob(ctypes.Structure):
        _fields_ = [("size", wintypes.DWORD), ("data", ctypes.POINTER(ctypes.c_ubyte))]

    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt.CryptProtectData.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR,
                                      ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                      wintypes.DWORD, ctypes.POINTER(Blob)]
    crypt.CryptProtectData.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    try:
        if not crypt.CryptProtectData(ctypes.byref(source), "Rokkad Razorpay TEST",
                                     None, None, None, 1, ctypes.byref(target)):
            raise RuntimeError("Encryption failed")
        return ctypes.string_at(target.data, target.size)
    finally:
        ctypes.memset(buffer, 0, len(buffer))
        if target.data:
            kernel.LocalFree(target.data)


def verify(key_id, key_secret):
    if not re.fullmatch(r"rzp_test_[A-Za-z0-9]{1,200}", key_id) or not key_secret or len(key_secret) > 512:
        return False
    try:
        with requests.Session() as session:
            session.trust_env = False
            # Product-specific Plans/Subscriptions access may be unavailable even
            # with valid account keys. Authenticate against the core Payments API.
            response = session.get("https://api.razorpay.com/v1/payments?count=1",
                                   auth=(key_id, key_secret), timeout=(10, 20), allow_redirects=False)
            if response.status_code != 200:
                return False
            payload = response.json()
            return isinstance(payload, dict) and payload.get("entity") == "collection" and isinstance(payload.get("items"), list)
    except (requests.RequestException, ValueError):
        return False


def status(value, **extra):
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps({"status": value, **extra}), encoding="utf-8")


class FormServer(HTTPServer):
    def __init__(self, save):
        super().__init__(("127.0.0.1", 0), Handler)
        self.timeout = 1
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.path = "/setup/" + self.token
        self.save = save
        self.done = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, message="", code=200, form=True):
        content = """<!doctype html><html lang="en"><meta charset="utf-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <title>Rokkad — Razorpay test setup</title><style>
        body{font:18px system-ui;background:#f5f4ef;color:#173d37;max-width:560px;margin:60px auto;padding:24px}
        main{background:white;border:1px solid #ddd;border-radius:14px;padding:30px}
        label{display:block;margin-top:22px}input{box-sizing:border-box;width:100%;font:inherit;padding:12px;margin-top:8px}
        button{background:#173d37;color:white;border:0;border-radius:6px;font:inherit;padding:14px;margin-top:24px}
        .message{font-weight:600}small{display:block;margin-top:24px;line-height:1.5}</style><main>
        <h1>Razorpay test setup</h1><p>Enter your saved test credentials here.</p>
        <p class="message">MESSAGE</p>FORM</main></html>"""
        fields = f"""<form method="post" action="/submit" autocomplete="off">
        <input type="hidden" name="token" value="{self.server.token}">
        <label>Test Key ID<input name="key_id" type="password" required autocomplete="off" spellcheck="false" maxlength="210" placeholder="rzp_test_…"></label>
        <label>Key Secret<input name="key_secret" type="password" required autocomplete="new-password" maxlength="512"></label>
        <button type="submit">Verify and save test credentials</button>
        <small>This local form sends credentials only to Razorpay to check access, then saves them encrypted on this Windows account outside OneDrive. No payment or subscription will be created.</small>
        </form>""" if form else ""
        body = content.replace("MESSAGE", html.escape(message)).replace("FORM", fields).encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        # Chrome can send Origin: null for a form POST under no-referrer.
        # Keep same-origin provenance while withholding it from external sites.
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def allowed_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.allowed_host() or self.path != self.server.path:
            self.reply("This setup link is unavailable.", 404, False)
            return
        self.reply()

    def do_POST(self):
        if (not self.allowed_host() or self.path != "/submit" or
                self.headers.get("Origin") != self.server.origin or
                self.headers.get("Content-Type", "").split(";")[0] != "application/x-www-form-urlencoded"):
            status("request_rejected", host_matches=self.allowed_host(),
                   origin_matches=self.headers.get("Origin") == self.server.origin,
                   origin_is_null=self.headers.get("Origin") == "null",
                   form_content_type=self.headers.get("Content-Type", "").split(";")[0] == "application/x-www-form-urlencoded")
            self.reply("Request rejected. Use the original setup link.", 403, False)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 4096:
                raise ValueError
            data = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True, max_num_fields=3)
            if set(data) != {"token", "key_id", "key_secret"} or any(len(v) != 1 for v in data.values()):
                raise ValueError
            if not secrets.compare_digest(data["token"][0], self.server.token):
                raise ValueError
        except (ValueError, UnicodeError):
            self.reply("Request rejected. Reload the original setup link.", 400, False)
            return
        key_id, key_secret = data["key_id"][0].strip(), data["key_secret"][0].strip()
        if not verify(key_id, key_secret):
            status("verification_failed")
            self.reply("Verification failed. Check that both values are from Test Mode and try again.", 400)
            return
        try:
            self.server.save(key_id, key_secret)
        except Exception:
            status("save_failed")
            self.reply("Test access verified, but encrypted saving failed. Ask for help before retrying.", 500, False)
            return
        status("verified_and_saved")
        self.server.done = True
        self.reply("Saved successfully. Test access is verified. You can close this tab.", form=False)

    def setup(self):
        super().setup()
        self.connection.settimeout(10)


def main():
    target = Path(os.environ["LOCALAPPDATA"]) / "Rokkad" / "private" / "razorpay-test.dpapi"
    if target.exists() or target.with_suffix(".xml").exists():
        status("existing_file_review_required")
        return

    def save(key_id, key_secret):
        protected = protect(json.dumps({"key_id": key_id, "key_secret": key_secret}).encode())
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(protected)

    with FormServer(save) as server:
        status("awaiting_input", url=server.origin + server.path)
        deadline = time.monotonic() + 900
        while not server.done and time.monotonic() < deadline:
            server.handle_request()
        if not server.done:
            status("expired")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        status("setup_failed")
