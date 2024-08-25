import os

from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    '*',
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": "rokkad.com",
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
