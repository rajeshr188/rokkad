import environ

from .base import *

env = environ.Env()
environ.Env.read_env()

DEBUG = False
BILLING_ALLOW_TRIAL_START = False

ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("Production requires explicit DJANGO_ALLOWED_HOSTS without '*'.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME"),
        "USER": env("DB_RUNTIME_USER"),
        "PASSWORD": env("DB_RUNTIME_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}
if not DATABASES["default"]["USER"] or not DATABASES["default"]["PASSWORD"]:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured("DB_RUNTIME_USER and DB_RUNTIME_PASSWORD must be nonempty.")

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
    "default_acl": None,  # Do not request public ACLs; the bucket must remain private.
    "querystring_auth": True,
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
