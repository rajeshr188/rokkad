from dynamic_preferences.exceptions import NotFoundInRegistry
from dynamic_preferences.registries import global_preferences_registry
from dynamic_preferences.settings import preferences_settings
from dynamic_preferences.users.models import UserPreferenceModel
from dynamic_preferences.users.registries import user_preferences_registry

from .models import PreferenceAuditLog, WorkspacePreferenceModel
from .registries import workspace_preferences_registry


class PreferenceService:
    USER_OVERRIDABLE_KEYS = frozenset(
        {
            "ui__theme",
            "ui__sidebar_collapsed",
            "ui__dashboard_widgets",
            "ui__table_page_size",
            "ui__date_display_format",
            "ui__default_landing_page",
        }
    )

    BUSINESS_CRITICAL_KEYS = frozenset(
        {
            "accounting__financial_year_start_month",
            "accounting__financial_year_start_day",
            "accounting__default_currency",
            "accounting__voucher_prefix",
            "accounting__invoice_prefix",
            "accounting__numbering_strategy",
            "accounting__default_cash_ledger",
            "accounting__default_bank_ledger",
            "accounting__default_receivable_ledger",
            "accounting__default_payable_ledger",
            "accounting__default_sales_ledger",
            "accounting__default_purchase_ledger",
            "accounting__rounding_policy",
            "loan__notice_timing_days",
            "loan__auction_timing_days",
            "loan__new_module_enabled",
            "accounting__successor_enabled",
            "accounting__workflow_mode",
            "accounting__integration_mode",
        }
    )

    @classmethod
    def normalize_key(cls, key):
        if key is None:
            raise ValueError("Preference key is required.")
        return str(key).replace(".", preferences_settings.SECTION_KEY_SEPARATOR)

    @classmethod
    def parse_key(cls, key):
        normalized_key = cls.normalize_key(key)
        try:
            return normalized_key.split(preferences_settings.SECTION_KEY_SEPARATOR, 1)
        except ValueError as exc:
            raise ValueError(
                "Preference key must include a section and name."
            ) from exc

    @classmethod
    def _registry_contains(cls, registry, key):
        section, name = registry.manager().parse_lookup(cls.normalize_key(key))
        try:
            registry.get(section=section, name=name)
            return True
        except NotFoundInRegistry:
            return False

    @classmethod
    def _safe_get(cls, manager, key, default=None):
        try:
            return manager[cls.normalize_key(key)]
        except Exception:
            return default

    @classmethod
    def _invalidate_manager_cache(cls, manager, key):
        section, name = manager.parse_lookup(cls.normalize_key(key))
        manager.cache.delete(manager.get_cache_key(section, name))

    @classmethod
    def _audit(
        cls,
        *,
        scope,
        key,
        old_value,
        new_value,
        workspace=None,
        subject_user=None,
        changed_by=None,
    ):
        PreferenceAuditLog.objects.create(
            scope=scope,
            key=cls.normalize_key(key),
            old_value="" if old_value is None else str(old_value),
            new_value="" if new_value is None else str(new_value),
            workspace=workspace,
            subject_user=subject_user,
            changed_by=changed_by,
        )

    @classmethod
    def get_global(cls, key, default=None):
        return cls._safe_get(global_preferences_registry.manager(), key, default)

    @classmethod
    def set_global(cls, key, value, user=None):
        normalized_key = cls.normalize_key(key)
        manager = global_preferences_registry.manager()
        old_value = cls._safe_get(manager, normalized_key, None)
        manager[normalized_key] = value
        cls._invalidate_manager_cache(manager, normalized_key)
        cls._audit(
            scope=PreferenceAuditLog.Scope.GLOBAL,
            key=normalized_key,
            old_value=old_value,
            new_value=value,
            changed_by=user,
        )
        return value

    @classmethod
    def get_workspace(cls, workspace, key, default=None):
        if workspace is None:
            return cls.get_global(key, default)

        normalized_key = cls.normalize_key(key)
        section, name = cls.parse_key(normalized_key)
        has_override = WorkspacePreferenceModel.objects.filter(
            instance=workspace,
            section=section,
            name=name,
        ).exists()
        if not has_override:
            return cls.get_global(normalized_key, default)

        manager = workspace_preferences_registry.manager(instance=workspace)
        return cls._safe_get(manager, normalized_key, default)

    @classmethod
    def get_workspace_from_registry(
        cls,
        *,
        workspace,
        key,
        workspace_registry,
        workspace_preference_model,
        global_registry=None,
        default=None,
    ):
        """Resolve a workspace preference from a supplied registry pair.

        This is used for compatibility registries while runtime code is moved
        toward the central `PreferenceService` boundary. It preserves the same
        semantics as the old Girvi helper: explicit workspace row first, then
        global registry fallback, then caller-supplied code default.
        """
        normalized_key = cls.normalize_key(key)
        section, name = cls.parse_key(normalized_key)

        if workspace is not None:
            has_override = workspace_preference_model.objects.filter(
                instance=workspace,
                section=section,
                name=name,
            ).exists()
            if has_override:
                manager = workspace_registry.manager(instance=workspace)
                return cls._safe_get(manager, normalized_key, default)

        if global_registry is not None:
            return cls._safe_get(global_registry.manager(), normalized_key, default)
        return default

    @classmethod
    def set_workspace(cls, workspace, key, value, user=None):
        if workspace is None:
            raise ValueError("Workspace is required to set a workspace preference.")

        normalized_key = cls.normalize_key(key)
        manager = workspace_preferences_registry.manager(instance=workspace)
        old_value = cls._safe_get(manager, normalized_key, None)
        manager[normalized_key] = value
        cls._invalidate_manager_cache(manager, normalized_key)
        cls._audit(
            scope=PreferenceAuditLog.Scope.WORKSPACE,
            key=normalized_key,
            old_value=old_value,
            new_value=value,
            workspace=workspace,
            changed_by=user,
        )
        return value

    @classmethod
    def get_user(cls, user, key, default=None):
        if user is None or not getattr(user, "is_authenticated", True):
            return default
        normalized_key = cls.normalize_key(key)
        section, name = cls.parse_key(normalized_key)
        has_override = UserPreferenceModel.objects.filter(
            instance=user,
            section=section,
            name=name,
        ).exists()
        if not has_override:
            return default
        manager = user_preferences_registry.manager(instance=user)
        return cls._safe_get(manager, normalized_key, default)

    @classmethod
    def set_user(cls, user, key, value):
        if user is None or not getattr(user, "is_authenticated", True):
            raise ValueError("Authenticated user is required to set a user preference.")

        normalized_key = cls.normalize_key(key)
        if normalized_key not in cls.USER_OVERRIDABLE_KEYS:
            raise ValueError(f"Preference '{normalized_key}' is not user-overridable.")

        manager = user_preferences_registry.manager(instance=user)
        old_value = cls._safe_get(manager, normalized_key, None)
        manager[normalized_key] = value
        cls._invalidate_manager_cache(manager, normalized_key)
        cls._audit(
            scope=PreferenceAuditLog.Scope.USER,
            key=normalized_key,
            old_value=old_value,
            new_value=value,
            subject_user=user,
            changed_by=user,
        )
        return value

    @classmethod
    def get_effective(cls, user=None, workspace=None, key=None, default=None):
        normalized_key = cls.normalize_key(key)

        if normalized_key in cls.USER_OVERRIDABLE_KEYS:
            user_value = cls.get_user(user, normalized_key, None)
            if user_value is not None:
                return user_value

        return cls.get_workspace(workspace, normalized_key, default)

    @classmethod
    def is_user_overridable(cls, key):
        return cls.normalize_key(key) in cls.USER_OVERRIDABLE_KEYS

    @classmethod
    def is_business_critical(cls, key):
        return cls.normalize_key(key) in cls.BUSINESS_CRITICAL_KEYS
