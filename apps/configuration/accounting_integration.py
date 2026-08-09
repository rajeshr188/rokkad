from apps.configuration.services import PreferenceService


ACCOUNTING_INTEGRATION_MODE_KEY = "accounting__integration_mode"
ACCOUNTING_INTEGRATION_MODES = frozenset({"DEFERRED", "DEA"})


def get_accounting_integration_mode(workspace) -> str:
    if workspace is None or not getattr(workspace, "pk", None):
        return "DEFERRED"
    value = str(
        PreferenceService.get_workspace(
            workspace,
            ACCOUNTING_INTEGRATION_MODE_KEY,
            "DEFERRED",
        )
    ).upper()
    return value if value in ACCOUNTING_INTEGRATION_MODES else "DEFERRED"


def is_dea_integration_enabled(workspace) -> bool:
    return get_accounting_integration_mode(workspace) == "DEA"
