"""Settings for isolated migration-baseline rehearsals.

The explicit name guard prevents rehearsal commands from targeting the normal
development database accidentally.
"""

import os

from .dev import *  # noqa: F403


REHEARSAL_DATABASE_NAME = os.environ.get("ROKKAD_REHEARSAL_DB_NAME", "")
if not REHEARSAL_DATABASE_NAME.startswith("rokkad_baseline_rehearsal_"):
    raise RuntimeError(
        "ROKKAD_REHEARSAL_DB_NAME must start with "
        "'rokkad_baseline_rehearsal_'."
    )

DATABASES["default"] = {  # noqa: F405
    **DATABASES["default"],  # noqa: F405
    "NAME": REHEARSAL_DATABASE_NAME,
}
