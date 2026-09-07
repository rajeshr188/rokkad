"""Owner-backed test database setup; RLS tests assume restricted roles explicitly."""

from .migration import *  # noqa: F403


CACHES = {
    **CACHES,  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rokkad-tests",
    },
    "select2": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rokkad-select2-tests",
    },
}
