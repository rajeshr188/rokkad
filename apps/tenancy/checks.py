from __future__ import annotations

from django.core.checks import Error, Tags, register
from django.db import connections
from django.db.migrations.recorder import MigrationRecorder

from .registry import (
    RLS_MIGRATION_BY_APP,
    RLS_MIGRATION_BY_MODEL,
    rls_protected_models,
    workspace_owned_models,
)


@register(Tags.models)
def check_workspace_ownership(app_configs, **kwargs):
    errors = []
    for model in workspace_owned_models():
        try:
            field = model._meta.get_field("workspace")
        except Exception:
            errors.append(
                Error(
                    f"{model._meta.label} has no direct Workspace field.",
                    id="tenancy.E001",
                )
            )
            continue
        if field.null:
            errors.append(
                Error(
                    f"{model._meta.label}.workspace must be non-null.",
                    id="tenancy.E002",
                )
            )
        if field.remote_field.model._meta.label_lower != "orgs.company":
            errors.append(
                Error(
                    f"{model._meta.label}.workspace must reference orgs.Company.",
                    id="tenancy.E003",
                )
            )
    return errors


@register(Tags.database)
def check_workspace_rls(app_configs, databases=None, **kwargs):
    if not databases:
        return []

    errors = []
    for alias in databases:
        connection = connections[alias]
        if connection.vendor != "postgresql":
            errors.append(
                Error(
                    f"Database {alias!r} is not PostgreSQL; Workspace RLS cannot run.",
                    id="tenancy.E010",
                )
            )
            continue
        recorder = MigrationRecorder(connection)
        if not recorder.has_table():
            continue
        applied = set(recorder.applied_migrations())
        protected_models = tuple(
            model
            for model in rls_protected_models()
            if (model._meta.app_label, RLS_MIGRATION_BY_MODEL.get(
                model._meta.label_lower, RLS_MIGRATION_BY_APP[model._meta.app_label]
            ))
            in applied
        )
        with connection.cursor() as cursor:
            for model in protected_models:
                cursor.execute(
                    """
                    SELECT c.relrowsecurity, c.relforcerowsecurity,
                           p.polname, pg_get_expr(p.polqual, p.polrelid),
                           pg_get_expr(p.polwithcheck, p.polrelid)
                    FROM pg_class c
                    LEFT JOIN pg_policy p
                      ON p.polrelid = c.oid AND p.polname = 'workspace_isolation'
                    WHERE c.oid = to_regclass(%s)
                    """,
                    [model._meta.db_table],
                )
                row = cursor.fetchone()
                if not row or row[0:3] != (True, True, "workspace_isolation"):
                    errors.append(
                        Error(
                            f"{model._meta.db_table} lacks enabled, forced Workspace RLS.",
                            id="tenancy.E011",
                        )
                    )
                    continue
                for expression_name, expression in (
                    ("USING", row[3]),
                    ("WITH CHECK", row[4]),
                ):
                    if not expression or "app.workspace_id" not in expression:
                        errors.append(
                            Error(
                                f"{model._meta.db_table} has an invalid {expression_name} policy.",
                                id="tenancy.E012",
                            )
                        )
    return errors


@register(Tags.database, deploy=True)
def check_restricted_runtime_role(app_configs, databases=None, **kwargs):
    if not databases:
        return []

    errors = []
    for alias in databases:
        connection = connections[alias]
        if connection.vendor != "postgresql":
            continue
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.rolsuper, r.rolbypassrls,
                       EXISTS (
                           SELECT 1
                           FROM pg_class c
                           WHERE c.relname = ANY(%s)
                             AND c.relowner = r.oid
                       )
                FROM pg_roles r
                WHERE r.rolname = current_user
                """,
                [[model._meta.db_table for model in rls_protected_models()]],
            )
            is_superuser, bypasses_rls, owns_tenant_table = cursor.fetchone()
        if is_superuser or bypasses_rls or owns_tenant_table:
            errors.append(
                Error(
                    f"Database {alias!r} is not using a restricted runtime role.",
                    hint=(
                        "Use a NOSUPERUSER NOBYPASSRLS role that does not own "
                        "Workspace tables for web requests and workers."
                    ),
                    id="tenancy.E020",
                )
            )
    return errors
