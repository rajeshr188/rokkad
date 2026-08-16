"""Owner-only settings for schema migrations; never use for web/workers."""

from .base import *  # noqa: F403


DATABASES["default"] = {  # noqa: F405
    "ENGINE": "django.db.backends.postgresql",
    "NAME": env("DB_MIGRATION_NAME", default="rokkad_shared_dev"),  # noqa: F405
    "USER": env("DB_MIGRATION_USER", default=env("DB_USER")),  # noqa: F405
    "PASSWORD": env(  # noqa: F405
        "DB_MIGRATION_PASSWORD", default=env("DB_PASSWORD")  # noqa: F405
    ),
    "HOST": env("DB_HOST"),  # noqa: F405
    "PORT": env("DB_PORT"),  # noqa: F405
}

SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]
