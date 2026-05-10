from .base import *

DEBUG = True

ALLOWED_HOSTS = [
    "*",
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": "prod-rehearsal",  # "NAME": "rokkad.com",
        "USER": "postgres",
        "PASSWORD": "kanchan",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

CLOUDFLARE_R2_BUCKET = env("CLOUDFLARE_R2_BUCKET")
CLOUDFLARE_R2_ACCESS_KEY = env("CLOUDFLARE_R2_ACCESS_KEY")
CLOUDFLARE_R2_SECRET_KEY = env("CLOUDFLARE_R2_SECRET_KEY")
CLOUDFLARE_R2_BUCKET_ENDPOINT = env("CLOUDFLARE_R2_BUCKET_ENDPOINT")

CLOUDFLARE_R2_CONFIG_OPTIONS = {
    "bucket_name": CLOUDFLARE_R2_BUCKET,
    "access_key": CLOUDFLARE_R2_ACCESS_KEY,
    "secret_key": CLOUDFLARE_R2_SECRET_KEY,
    "endpoint_url": CLOUDFLARE_R2_BUCKET_ENDPOINT,
    "default_acl": "public-read",  # "private"
    "signature_version": "s3v4",
}

# STORAGES = {
#     "default": {
#         "BACKEND": "helpers.cloudflare.storages.MediaFileStorage",
#         "OPTIONS": CLOUDFLARE_R2_CONFIG_OPTIONS,
#     },# default ->user/image/file fields uploads
#     # "staticfiles": {
#     #     "BACKEND": "helpers.cloudflare.storages.StaticFileStorage",
#     #     "OPTIONS": CLOUDFLARE_R2_CONFIG_OPTIONS,
#     # },# static -> static files
#     "staticfiles": {
#         "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#     },# static -> static files
# }
