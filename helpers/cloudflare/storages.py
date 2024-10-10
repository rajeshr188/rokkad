from django_tenants.files.storage import TenantFileSystemStorage
from django_tenants.utils import parse_tenant_config_path
from storages.backends.s3 import S3Storage


class StaticFileStorage(S3Storage):
    location = "static"


class MediaFileStorage(S3Storage):
    location = "media"

    @property  # not cached like in parent of S3Boto3Storage class
    def location(self):
        _location = parse_tenant_config_path("media/%s")  # here you can just put '%s'
        return _location
