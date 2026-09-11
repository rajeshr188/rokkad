"""Workspace settings; existing control-plane policy remains authoritative."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.onboarding.services import (
    build_workspace_setup_checklist,
    build_workspace_setup_display_state,
    dismiss_workspace_setup,
    mark_workspace_setup_complete,
    reopen_workspace_setup,
)
from apps.orgs.audit import (
    AuditLog,
    audit_log,
)
from apps.orgs.decorators_v2 import permission_required
from apps.orgs.forms import CompanyForm
from apps.orgs.models import (
    Company,
    Role,
)
from apps.orgs.services import control_plane
from apps.subscriptions import entitlements
from apps.subscriptions.billing import effective_billing_state
from apps.orgs.web.access_helpers import (
    _assert_owner_access,
    _assert_workspace_access,
)


WORKSPACE_MODULE_REGISTRY = [
    {
        "name": "Parties",
        "description": "Customer, supplier, broker, employee, KYC, and relationship records.",
        "route_name": "workspace_slug_parties",
        "default_status": "Active",
    },
    {
        "name": "Loans",
        "description": "PawnLoan workflows, collateral custody, releases, repayments, and notices.",
        "route_name": "workspace_slug_loan_list",
        "default_status": "Active",
    },
    {
        "name": "Notifications",
        "description": "Operational notification batches and delivery settings.",
        "route_name": "workspace_slug_notifications",
        "default_status": "Active",
    },
    {
        "name": "Rates",
        "description": "Workspace-owned reference rates and rate sources.",
        "route_name": "workspace_slug_rates",
        "default_status": "Active",
    },
    {
        "name": "Customer Portal",
        "description": "Future customer-facing loans, invoices, payments, documents, and statements.",
        "route_name": "",
        "default_status": "Planned",
    },
    {
        "name": "API Access",
        "description": "Programmatic API integration access for this workspace.",
        "route_name": "",
        "feature_code": "api.access",
        "default_status": "Active",
    },
    {
        "name": "Custom Fields",
        "description": "Custom fields for advanced workflow and data capture scenarios.",
        "route_name": "",
        "feature_code": "workspace.custom_fields",
        "default_status": "Active",
    },
]


@login_required
@audit_log("COMPANY_CREATE", description="Create new company")
def workspace_create(request):
    """
    Create a new workspace.
    User becomes Owner with full permissions.
    """
    if request.method == "POST":
        form = CompanyForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                company = control_plane.create_workspace_from_form(
                    form=form,
                    user=request.user,
                    request=request,
                )
            except ValidationError as exc:
                form.add_error(None, exc)
                return render(request, "company/company_form.html", {"form": form})
            request.user.profile.set_workspace(company)
            return redirect("workspace_slug_settings_setup", workspace_slug=company.slug)
        else:
            # Handle form errors
            return render(request, "company/company_form.html", {"form": form})
    else:
        form = CompanyForm()
    return render(request, "company/company_form.html", {"form": form})


@login_required
def workspace_list(request):
    """
    Legacy workspace listing endpoint.

    Canonical entrypoint is workspace_selector. Keep this route as a
    compatibility alias to avoid breaking old links.
    """
    return redirect("workspace_selector")


@login_required
def workspace_detail(request, workspace_id=None, company_id=None):
    """
    Display workspace details including team members and invitations.
    Requires workspace_view permission.
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    if company.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise Http404("Company not found")

    access_context = _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_view"},
        allow_platform_admin=True,
    )

    roles = Role.objects.all()
    return render(
        request,
        "company/company_detail.html",
        {
            "company": company,
            "roles": roles,
            "workspace": company,
            "can_archive_workspace": access_context["access"].can(
                "workspace.archive"
            ),
        },
    )


@login_required
def workspace_setup(request, workspace_id=None, company_id=None):
    """Display the read-only workspace setup checklist."""
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    access_context = _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_settings"},
        allow_platform_admin=True,
    )
    from apps.onboarding.services.setup_checklist import build_business_setup

    business_setup = build_business_setup(workspace=company)
    setup_checklist = build_workspace_setup_checklist(workspace=company)
    setup_state = build_workspace_setup_display_state(
        user=request.user,
        workspace=company,
        checklist=setup_checklist,
    )

    return render(
        request,
        "company/workspace_setup.html",
        {
            "company": company,
            "workspace": company,
            "setup_checklist": setup_checklist,
            "business_setup": business_setup,
            "can_create_loan": access_context["access"].can("data.create") and access_context["access"].can("data.view"),
            "setup_state": setup_state,
            "user_role": access_context["role_name"],
        },
    )


@login_required
@require_POST
def workspace_setup_state(request, workspace_id=None, company_id=None):
    """Update user-specific workspace setup checklist display state."""
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_settings"},
        allow_platform_admin=True,
    )

    action = request.POST.get("action")
    if action == "dismiss":
        dismiss_workspace_setup(user=request.user, workspace=company)
        messages.info(request, "Workspace setup card dismissed.")
    elif action == "complete":
        mark_workspace_setup_complete(user=request.user, workspace=company)
        messages.success(request, "Workspace setup marked complete.")
    elif action == "reopen":
        reopen_workspace_setup(user=request.user, workspace=company)
        messages.info(request, "Workspace setup reopened.")
    else:
        messages.error(request, "Unknown workspace setup action.")

    next_url = request.POST.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect("workspace_settings_setup", workspace_id=company.id)


@login_required
def workspace_modules(request, workspace_id=None, company_id=None):
    """Display the workspace-owned module availability map."""
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    access_context = _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_settings"},
        allow_platform_admin=True,
    )

    return render(
        request,
        "company/workspace_modules.html",
        {
            "company": company,
            "workspace": company,
            "modules": _workspace_module_statuses(
                workspace=company,
                user=request.user,
            ),
            "user_role": access_context["role_name"],
        },
    )


@login_required
def workspace_security(request, workspace_id=None, company_id=None):
    """Display workspace security and audit activity."""
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    access_context = _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_settings"},
        allow_platform_admin=True,
    )
    audit_events = (
        AuditLog.objects.for_company(company)
        .select_related("user")
        .order_by("-timestamp")[:50]
    )
    security_actions = [
        "LOGIN",
        "LOGOUT",
        "LOGIN_FAILED",
        "PERMISSION_DENIED",
        "UNAUTHORIZED_ACCESS",
    ]
    security_events = AuditLog.objects.for_company(company).filter(
        action__in=security_actions
    )

    return render(
        request,
        "company/workspace_security.html",
        {
            "company": company,
            "workspace": company,
            "audit_events": audit_events,
            "security_event_count": security_events.count(),
            "failed_event_count": AuditLog.objects.for_company(company)
            .filter(success=False)
            .count(),
            "user_role": access_context["role_name"],
        },
    )


@login_required
@permission_required("workspace_edit")
@audit_log("COMPANY_UPDATE", description="Update company settings")
def workspace_update(request, workspace_id=None, company_id=None):
    """
    Update workspace settings.
    Requires workspace_edit permission (Owner/Admin).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_edit"},
        allow_platform_admin=True,
    )
    _assert_owner_access(request, company, allow_platform_admin=True)

    if request.method == "POST":
        form = CompanyForm(request.POST, instance=company)
        if form.is_valid():
            control_plane.save_workspace_update_form(
                form=form,
                actor=request.user,
                request=request,
            )
            return redirect("workspace_list")
    else:
        form = CompanyForm(instance=company)
    return render(
        request, "company/company_form.html", {"form": form, "company": company, "workspace": company}
    )


def _workspace_module_statuses(*, workspace, user):
    evaluated_modules = []
    for module_config in WORKSPACE_MODULE_REGISTRY:
        module = {
            "name": module_config["name"],
            "description": module_config["description"],
            "route_name": module_config.get("route_name", ""),
            "status": module_config.get("default_status", "Active"),
            "lock_reason": "",
            "is_openable": False,
            "upgrade_url": "",
        }

        feature_code = module_config.get("feature_code")
        route_name = module.get("route_name")

        if feature_code:
            try:
                subscription = workspace.subscription
                billing = effective_billing_state(subscription)
            except Exception:
                billing = None
            if entitlements.enabled(workspace, feature_code):
                module["status"] = "Active"
                module["is_openable"] = bool(route_name)
            elif billing is None or not billing.commercially_available:
                module["status"] = "Billing Required"
                module["lock_reason"] = "An active commercial subscription is required."
                module["upgrade_url"] = reverse(
                    "workspace_subscriptions:dashboard",
                    kwargs={"workspace_slug": workspace.slug},
                )
            else:
                module["status"] = "Locked"
                module["lock_reason"] = "This capability is not included in the Workspace entitlement grant."
                module["upgrade_url"] = reverse(
                    "workspace_subscriptions:dashboard",
                    kwargs={"workspace_slug": workspace.slug},
                )
        else:
            module["is_openable"] = bool(route_name) and module["status"] == "Active"

        evaluated_modules.append(module)

    return evaluated_modules
