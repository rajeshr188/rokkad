"""Private R2 application copies; originals are read-only in this adapter."""
import hashlib
import time
from io import BytesIO

from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError, ReadTimeoutError, SSLError
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from PIL import Image
from urllib3.exceptions import ProtocolError, ReadTimeoutError as HTTPReadTimeoutError


class R2MediaCopies:
    def __init__(self):
        self.storage = default_storage
        self.bucket = self.storage.bucket_name
        self.location = self.storage.location
        if not self.location.startswith("media/application/") or not self.storage.endpoint_url.endswith(".r2.cloudflarestorage.com"):
            raise ValidationError("Select isolated private R2 application storage explicitly.")
        self.client = self.storage.connection.meta.client
        self.verified = set()

    def _request(self, method, **kwargs):
        # Some networks close parallel TLS handshakes. Retry only transport loss;
        # never disable certificate validation or retry certificate trust failures.
        for attempt in range(4):
            try:
                return getattr(self.client, method)(**kwargs)
            except (ConnectionClosedError, EndpointConnectionError, ReadTimeoutError, SSLError) as exc:
                if isinstance(exc, SSLError) and "UNEXPECTED_EOF" not in str(exc):
                    raise
                if attempt == 3:
                    raise
                time.sleep(0.25 * (2 ** attempt))

    def key(self, name):
        if not name.startswith("legacy_import/") or ".." in name or "\\" in name:
            raise ValidationError("Invalid application copy name.")
        return self.location + "/" + name

    def _read(self, key, original):
        # A connection can also fail after headers arrive. Restart the bounded GET
        # and validate the complete bytes; never accept a partial streaming body.
        for attempt in range(4):
            try:
                response = self._request("get_object", Bucket=self.bucket, Key=key)
                with response["Body"] as body:
                    content = body.read(10 * 1024 * 1024 + 1)
                break
            except (ReadTimeoutError, HTTPReadTimeoutError, ProtocolError, ConnectionClosedError):
                if attempt == 3:
                    raise
                time.sleep(0.25 * (2 ** attempt))
        if len(content) != original["byte_size"] or hashlib.sha256(content).hexdigest() != original["sha256"]:
            raise ValidationError("Stored photo bytes differ from preserved evidence.")
        return content

    def verify(self, name, original):
        signature = (name, original["sha256"], original["byte_size"])
        if signature in self.verified:
            return
        self._read(self.key(name), original)
        self.verified.add(signature)

    def prepare(self, names, original):
        if original["bucket"] != self.bucket:
            raise ValidationError("Preservation bucket differs from the selected account configuration.")
        content = self._read(original["object_key"], original)
        with Image.open(BytesIO(content)) as picture:
            if Image.MIME.get(picture.format) != original["content_type"]:
                raise ValidationError("Photograph format differs from source signature evidence.")
            picture.verify()
        for name in names.values():
            try:
                self._request("put_object", Bucket=self.bucket, Key=self.key(name), Body=content,
                    ContentType=original["content_type"], CacheControl="private, no-store", IfNoneMatch="*")
            except ClientError as exc:
                if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                    raise
            self.verify(name, original)
        return names
