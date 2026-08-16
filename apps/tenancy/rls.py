from __future__ import annotations

from django.db.migrations.operations.base import Operation


POLICY_NAME = "workspace_isolation"
WORKSPACE_SETTING_SQL = (
    "NULLIF(current_setting('app.workspace_id', true), '')::bigint"
)


class EnableWorkspaceRLS(Operation):
    """Enable and force the canonical Workspace policy for one model table."""

    reduces_to_sql = True
    reversible = True

    def __init__(self, model_name: str):
        self.model_name = model_name

    def state_forwards(self, app_label, state):
        return None

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        model = to_state.apps.get_model(app_label, self.model_name)
        table = schema_editor.quote_name(model._meta.db_table)
        policy = schema_editor.quote_name(POLICY_NAME)
        predicate = f"workspace_id = {WORKSPACE_SETTING_SQL}"
        schema_editor.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        schema_editor.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        schema_editor.execute(
            f"CREATE POLICY {policy} ON {table} "
            f"USING ({predicate}) WITH CHECK ({predicate})"
        )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        model = from_state.apps.get_model(app_label, self.model_name)
        table = schema_editor.quote_name(model._meta.db_table)
        policy = schema_editor.quote_name(POLICY_NAME)
        schema_editor.execute(f"DROP POLICY IF EXISTS {policy} ON {table}")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    def describe(self):
        return f"Enable forced Workspace RLS for {self.model_name}"

    @property
    def migration_name_fragment(self):
        return f"enable_{self.model_name.lower()}_workspace_rls"

    def deconstruct(self):
        return (self.__class__.__qualname__, [self.model_name], {})


class EnableWorkspaceRLSForApp(Operation):
    """Enable canonical Workspace RLS for every owned model in one app state."""

    reduces_to_sql = True
    reversible = True

    def state_forwards(self, app_label, state):
        return None

    @staticmethod
    def _model_names(app_label, state):
        app_config = state.apps.get_app_config(app_label)
        names = []
        for model in app_config.get_models():
            if model._meta.abstract or model._meta.proxy:
                continue
            try:
                model._meta.get_field("workspace")
            except Exception:
                continue
            names.append(model.__name__)
        return sorted(names)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        for model_name in self._model_names(app_label, to_state):
            EnableWorkspaceRLS(model_name).database_forwards(
                app_label, schema_editor, from_state, to_state
            )

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        for model_name in reversed(self._model_names(app_label, from_state)):
            EnableWorkspaceRLS(model_name).database_backwards(
                app_label, schema_editor, from_state, to_state
            )

    def describe(self):
        return "Enable forced Workspace RLS for every owned model in this app"

    @property
    def migration_name_fragment(self):
        return "enable_app_workspace_rls"

    def deconstruct(self):
        return (self.__class__.__qualname__, [], {})
