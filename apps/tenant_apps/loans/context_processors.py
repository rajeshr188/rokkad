from apps.orgs.tenant_context import resolve_request_workspace
from apps.tenant_apps.loans.feature_flags import is_new_loans_enabled


def loan_module_feature_context(request):
    workspace = resolve_request_workspace(
        request,
        include_public=False,
        allow_profile_fallback=False,
    )
    return {
        "loans_new_module_enabled": is_new_loans_enabled(workspace),
    }
