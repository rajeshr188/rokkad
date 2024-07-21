import os

from .base import *

DEBUG = False

ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
]

DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": "rokkad",
        "USER": "postgres",
        "PASSWORD": "kanchan",
        "HOST": "localhost",
        "PORT": "5432",
    }
}

# INSTALLED_APPS += [
#     # 'slick_reporting',
#     # 'crispy_bootsrap4',
# ]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
