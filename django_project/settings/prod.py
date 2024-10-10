import os

import environ

from .base import *

env = environ.Env()
environ.Env.read_env()

DEBUG = False

ALLOWED_HOSTS = ["*", "rokkad.com", "www.rokkad.com"]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}

STATIC_ROOT = "/var/www/rokkad/static"
MEDIA_ROOT = "/var/www/rokkad/media"
STATICFILES_DIRS = [BASE_DIR / "static"]

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
#     "staticfiles": {
#         "BACKEND": "helpers.cloudflare.storages.StaticFileStorage",
#         "OPTIONS": CLOUDFLARE_R2_CONFIG_OPTIONS,
#     },# static -> static files
#     # "staticfiles": {
#     #     "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
#     # },# static -> static files
# }

# SECURE_SSL_REDIRECT = True

# SESSION_COOKIE_SECURE = True

# CSRF_COOKIE_SECURE = True

# SECURE_BROWSER_XSS_FILTER = True
