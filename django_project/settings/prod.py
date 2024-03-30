import os

import environ

from .base import *

env = environ.Env()
environ.Env.read_env()

DEBUG = False

ALLOWED_HOSTS = ["rokkad.com", "www.rokkad.com"]

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
STATICFILES_DIRS = []

SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True

CSRF_COOKIE_SECURE = True

SECURE_BROWSER_XSS_FILTER = True
