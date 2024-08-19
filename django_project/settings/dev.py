import os

from .base import *

DEBUG = True

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

# INSTALLED_APPS += [
#     # 'slick_reporting',
#     # 'crispy_bootsrap4',
# ]

MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
