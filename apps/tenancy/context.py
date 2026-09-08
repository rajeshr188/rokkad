from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from django.core.exceptions import ImproperlyConfigured
from django.db import connection, transaction


_workspace_id: ContextVar[int | None] = ContextVar("workspace_id", default=None)


def current_workspace_id() -> int | None:
    """Return the explicit Workspace context for the current execution flow."""

    return _workspace_id.get()


@contextmanager
def workspace_context(workspace_id: int):
    """Run one atomic unit with a transaction-local PostgreSQL Workspace id."""

    try:
        normalized_id = int(workspace_id)
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured("A numeric workspace_id is required.") from exc
    if normalized_id <= 0:
        raise ImproperlyConfigured("workspace_id must be positive.")

    active_id = current_workspace_id()
    if active_id is not None and active_id != normalized_id:
        raise ImproperlyConfigured(
            "A conflicting Workspace context is already active."
        )

    token = _workspace_id.set(normalized_id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.workspace_id', true)")
                previous_database_id = cursor.fetchone()[0] or ""
                cursor.execute(
                    "SELECT set_config('app.workspace_id', %s, true)",
                    [str(normalized_id)],
                )
            try:
                yield
            except Exception:
                # The atomic block rolls back its SET LOCAL along with the
                # failed work, restoring any surrounding transaction value.
                raise
            else:
                if active_id is None:
                    # Deferred projection guards read RLS-owned rows. Settle
                    # them before restoring the surrounding Workspace context.
                    connection.check_constraints()
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT set_config('app.workspace_id', %s, true)",
                        [previous_database_id],
                    )
    finally:
        _workspace_id.reset(token)


@contextmanager
def without_workspace_context():
    """Temporarily suspend Workspace identity for fail-closed tests/operations."""

    previous_id = current_workspace_id()
    token = _workspace_id.set(None)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SELECT set_config('app.workspace_id', '', true)")
            try:
                yield
            except Exception:
                raise
            else:
                if previous_id is not None:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT set_config('app.workspace_id', %s, true)",
                            [str(previous_id)],
                        )
    finally:
        _workspace_id.reset(token)
