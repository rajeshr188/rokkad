import logging
from types import SimpleNamespace

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse, HttpResponseGone, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from dynamic_preferences.views import PreferenceFormView
from render_block import render_block_to_string

from apps.onboarding.services import build_workspace_setup_display_state

from .audit import AuditLog, audit_log
from .decorators_v2 import permission_required
from .forms import ArchiveWorkspaceForm, CompanyInvitationForm, MembershipForm, company_preference_form_builder
from .models import Company, CompanyInvitation, Membership, Role
from .permissions import get_effective_permissions, is_platform_admin
from .registries import company_preference_registry
from .services import control_plane
from .services.membership_capacity import get_workspace_seat_capacity_snapshot
from .services import role_policy
from .services.dashboard_selectors import get_workspace_dashboard_context
from .tenant_context import resolve_preferred_workspace, resolve_request_workspace
from apps.subscriptions.billing import effective_billing_state

from apps.orgs.web.workspace_settings import (
    workspace_create,
    workspace_list,
    workspace_detail,
    workspace_setup,
    workspace_setup_state,
    workspace_modules,
    workspace_security,
    workspace_update,
    _workspace_module_statuses,
    WORKSPACE_MODULE_REGISTRY,
)
from apps.orgs.web.role_settings import (
    workspace_role_permissions,
)
from apps.orgs.web.access_helpers import (
    _assert_workspace_access,
    _assert_owner_access,
)

# Compatibility imports above preserve existing URLs and Python callers.
logger = logging.getLogger(__name__)
User = get_user_model()

def has_permission(user, tenant, permission_codename):
    return permission_codename in get_effective_permissions(user, tenant)


def has_role(user, tenant, role_name):
    if is_platform_admin(user) and role_name == "Superuser":
        return True
    return Membership.objects.filter(
        user=user,
        company=tenant,
        role__name__iexact=role_name,
    ).exists()


def _is_owner_membership(membership):
    return role_policy.is_owner_membership(membership)


def _owner_membership_count(workspace):
    return role_policy.owner_membership_count(workspace)


def _get_workspace_from_query(request):
    workspace_id = request.GET.get("workspace_id")
    if not workspace_id:
        return None
    if not workspace_id.isdigit():
        raise Http404("Invalid workspace ID")
    return get_object_or_404(Company, id=workspace_id)


def _get_workspace_from_slug(workspace_slug, *, include_inactive=False):
    if workspace_slug == "public":
        raise Http404("Workspace not found")
    manager = Company.all_objects if include_inactive else Company.objects
    return get_object_or_404(
        manager,
        slug=workspace_slug,
    )


@login_required
def workspace_slug_dashboard(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_dashboard(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_home(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_detail(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_setup(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_setup(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_setup_state(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_setup_state(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_preferences(request, workspace_slug):
    from apps.configuration.views import WorkspacePreferenceBuilder

    workspace = _get_workspace_from_slug(workspace_slug)
    return WorkspacePreferenceBuilder.as_view()(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_team(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return membership_list(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_invitations(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return companyinvitations_list(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_invite(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return team_invite(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_profile(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_update(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_billing(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return redirect(
        "workspace_subscriptions:dashboard",
        workspace_slug=workspace.slug,
    )


@login_required
def workspace_slug_settings_accounting(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect("dea_chart_of_accounts")


@login_required
def workspace_slug_settings_roles(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return membership_list(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_numbering(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import license_list

    return license_list(request)


@login_required
def workspace_slug_settings_modules(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_modules(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_security(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_security(request, workspace_id=workspace.id)


@login_required
def workspace_slug_settings_archive(request, workspace_slug):
    workspace = _get_workspace_from_slug(workspace_slug)
    return workspace_delete(request, workspace_id=workspace.id)


@login_required
def workspace_slug_parties(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.party.views import party_list

    return party_list(request)


@login_required
def workspace_slug_party_create(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.party.views import party_create

    return party_create(request)


@login_required
def workspace_slug_party_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.party.views import party_detail

    return party_detail(request, pk=pk)


@login_required
def workspace_slug_party_update(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.party.views import party_update

    return party_update(request, pk=pk)


@login_required
def workspace_slug_party_merge(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.party.views import party_merge

    return party_merge(request, pk=pk)


@login_required
def workspace_slug_loans(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return render(request, "company/loan_application_choice.html")


@login_required
def workspace_slug_loans_dispatch(request, workspace_slug, loans_path):
    """Retain the old URL-builder name; all supported paths resolve before this."""
    _get_workspace_from_slug(workspace_slug)
    from django.http import Http404

    raise Http404("Unknown Loans route")


@login_required
def workspace_slug_loan_list(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import pawn_loan_list

    return pawn_loan_list(request)


@login_required
def workspace_slug_loan_create(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import pawn_loan_create

    return pawn_loan_create(request)


@login_required
def workspace_slug_loan_table(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect("workspace_slug_loan_list", workspace_slug=workspace_slug)


@login_required
def workspace_slug_loan_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import pawn_loan_detail

    return pawn_loan_detail(request, pk=pk)


@login_required
def workspace_slug_loan_detail_items(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect(f"{reverse('workspace_slug_loan_detail', kwargs={'workspace_slug': workspace_slug, 'pk': pk})}#collateral")


@login_required
def workspace_slug_loan_detail_payments(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect(f"{reverse('workspace_slug_loan_detail', kwargs={'workspace_slug': workspace_slug, 'pk': pk})}#financial-events")


@login_required
def workspace_slug_loan_detail_transactions(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect(f"{reverse('workspace_slug_loan_detail', kwargs={'workspace_slug': workspace_slug, 'pk': pk})}#financial-events")


@login_required
def workspace_slug_loan_detail_statement(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect("workspace_slug_loan_detail", workspace_slug=workspace_slug, pk=pk)


@login_required
def workspace_slug_loan_detail_notices(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect(f"{reverse('workspace_loans:pawn_loan_detail', args=[workspace_slug, pk])}#notices")


@login_required
def workspace_slug_loan_detail_release(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect(f"{reverse('workspace_loans:pawn_loan_detail', args=[workspace_slug, pk])}#release")


@login_required
def workspace_slug_loan_pdf(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import pawn_loan_ticket_pdf

    return pawn_loan_ticket_pdf(request, pk=pk)


@login_required
def workspace_slug_loan_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.loans.views import pawn_loan_reports

    return pawn_loan_reports(request)


@login_required
def workspace_slug_loan_by_customer_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect('workspace_loans:pawn_loan_reports', workspace_slug=workspace_slug)


@login_required
def workspace_slug_loan_crosstab_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect('workspace_loans:pawn_loan_reports', workspace_slug=workspace_slug)


@login_required
def workspace_slug_loan_list_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect('workspace_loans:pawn_loan_reports', workspace_slug=workspace_slug)


@login_required
def workspace_slug_loan_reconciliation_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect('workspace_loans:pawn_operations_console', workspace_slug=workspace_slug)


@login_required
def workspace_slug_loan_operational_controls_report(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect('workspace_loans:pawn_operations_console', workspace_slug=workspace_slug)


@login_required
def workspace_slug_inventory(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_products(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_product_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_stock(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_stock_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_stock_audit(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_transactions(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_inventory_statements(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return HttpResponseGone("Product and inventory have been retired from Rokkad.")


@login_required
def workspace_slug_rates(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.rates.views import rate_list

    return rate_list(request)


@login_required
def workspace_slug_rate_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.rates.views import rate_detail

    return rate_detail(request, pk=pk)


@login_required
def workspace_slug_rate_sources(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.rates.views import ratesource_list

    return ratesource_list(request)


@login_required
def workspace_slug_rate_source_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.rates.views import ratesource_detail

    return ratesource_detail(request, pk=pk)


@login_required
def workspace_slug_notifications(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    from apps.tenant_apps.notify_v2.views import batch_list

    return batch_list(request)


@login_required
def workspace_slug_notification_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect("workspace_notify:notify_v2_batch_list", workspace_slug=workspace_slug)


@login_required
def workspace_slug_notice_groups(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug)
    return redirect("workspace_notify:notify_v2_batch_list", workspace_slug=workspace_slug)


@login_required
def workspace_slug_notice_group_detail(request, workspace_slug, pk):
    _get_workspace_from_slug(workspace_slug)
    return redirect("workspace_notify:notify_v2_batch_list", workspace_slug=workspace_slug)


@login_required
def workspace_slug_data_tools_export(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug, include_inactive=True)
    from apps.tenant_apps.utils.importing.views import export_form

    return export_form(request)


@login_required
def workspace_slug_data_tools_import(request, workspace_slug):
    _get_workspace_from_slug(workspace_slug, include_inactive=True)
    from apps.tenant_apps.utils.importing.views import import_data

    return import_data(request)


@login_required
def workspace_slug_data_tools_export_data(
    request,
    workspace_slug,
    model_name,
    export_format,
):
    _get_workspace_from_slug(workspace_slug, include_inactive=True)
    from apps.tenant_apps.utils.importing.views import export_data

    return export_data(
        request,
        model_name=model_name,
        export_format=export_format,
    )


@login_required
def retired_accounting_surface(request, *args, **kwargs):
    """Return an explicit retirement response for old accounting bookmarks."""

    return HttpResponseGone("Accounting has been retired from Rokkad.")


# Keep old workspace bookmarks deterministic while the tenancy URL baseline is
# rebuilt. None of these routes import or execute a retired accounting app.
workspace_slug_settings_accounting = retired_accounting_surface
workspace_slug_accounting = retired_accounting_surface
workspace_slug_accounting_chart_of_accounts = retired_accounting_surface
workspace_slug_accounting_accounts = retired_accounting_surface
workspace_slug_accounting_account_detail = retired_accounting_surface
workspace_slug_accounting_ledgers = retired_accounting_surface
workspace_slug_accounting_ledger_detail = retired_accounting_surface
workspace_slug_accounting_transactions = retired_accounting_surface
workspace_slug_accounting_trial_balance = retired_accounting_surface
workspace_slug_accounting_balance_sheet = retired_accounting_surface
workspace_slug_accounting_profit_loss = retired_accounting_surface
workspace_slug_accounting_income_statement = retired_accounting_surface
workspace_slug_accounting_cash_flow = retired_accounting_surface
workspace_slug_accounting_ar_aging = retired_accounting_surface
workspace_slug_accounting_ap_aging = retired_accounting_surface
workspace_slug_accounting_financial_ratios = retired_accounting_surface
workspace_slug_accounting_vouchers = retired_accounting_surface
workspace_slug_accounting_voucher_detail = retired_accounting_surface
workspace_slug_accounting_payments = retired_accounting_surface
workspace_slug_accounting_payment_detail = retired_accounting_surface
workspace_slug_accounting_expenses = retired_accounting_surface
workspace_slug_accounting_expense_detail = retired_accounting_surface
workspace_slug_accounting_journal_entry_vouchers = retired_accounting_surface
workspace_slug_accounting_journal_entry_voucher_detail = retired_accounting_surface
workspace_slug_accounting_periods = retired_accounting_surface
workspace_slug_accounting_period_detail = retired_accounting_surface
workspace_slug_accounting_reconciliation = retired_accounting_surface
workspace_slug_accounting_reconciliation_detail = retired_accounting_surface
workspace_slug_operations = retired_accounting_surface
workspace_slug_sales = retired_accounting_surface
workspace_slug_purchase = retired_accounting_surface
workspace_slug_commodity = retired_accounting_surface
workspace_slug_commodity_detail = retired_accounting_surface
workspace_slug_commodity_metal_balance_report = retired_accounting_surface
workspace_slug_commodity_exposure_report = retired_accounting_surface
workspace_slug_commodity_valuation_report = retired_accounting_surface
workspace_slug_reports = retired_accounting_surface


@login_required
def workspace_delete(request, workspace_id=None, company_id=None):
    """
    Archive a workspace while preserving its tenant schema and all business data.

    The legacy route name is retained for compatibility. Requires the
    workspace_delete permission and Owner access.
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"workspace_delete"},
        allow_platform_admin=True,
    )

    _assert_owner_access(request, company, allow_platform_admin=True)
    form = ArchiveWorkspaceForm(
        request.POST if request.method == "POST" else None,
        workspace=company,
    )
    if request.method == "POST" and form.is_valid():
        control_plane.archive_workspace(
            company=company,
            actor=request.user,
            request=request,
            reason=f"Owner confirmed archive of {company.name}",
        )

        # Do not leave the actor's profile pointing at an inaccessible tenant.
        if getattr(request.user.profile, "workspace", None) == company:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        messages.success(
            request,
            f"{company.name} was archived. Its schema and business records were preserved.",
        )
        return redirect("archived_workspaces")

    return render(
        request,
        "company/company_delete_confirm.html",
        {"company": company, "workspace": company, "form": form},
    )


@login_required
def archived_workspaces(request):
    """List archived workspaces that the actor is allowed to restore."""
    workspaces = Company.all_objects.filter(
        lifecycle_state=Company.LifecycleState.ARCHIVED
    ).exclude(
        schema_name="public"
    )
    if not is_platform_admin(request.user):
        workspaces = workspaces.filter(owner=request.user)
    workspaces = workspaces.select_related("owner").order_by("-updated_at", "name")
    return render(
        request,
        "company/archived_workspaces.html",
        {"archived_workspaces": workspaces},
    )


@require_POST
@login_required
def workspace_restore(request, workspace_id):
    """Restore one archived workspace; only its Owner or platform admin may act."""
    company = get_object_or_404(
        Company.all_objects,
        id=workspace_id,
        lifecycle_state=Company.LifecycleState.ARCHIVED,
    )
    if request.user != company.owner and not is_platform_admin(request.user):
        raise PermissionDenied("Only the workspace owner can restore this workspace")

    control_plane.restore_workspace(
        company=company,
        actor=request.user,
        request=request,
    )
    messages.success(request, f"{company.name} was restored.")
    return redirect("archived_workspaces")


@require_POST
@login_required
def workspace_lifecycle_transition(request, workspace_id, target_state):
    """Apply an explicitly authorized operational lifecycle transition."""
    company = get_object_or_404(Company.all_objects, id=workspace_id)
    reason = (request.POST.get("reason") or "").strip()
    try:
        updated = control_plane.transition_workspace_lifecycle(
            workspace=company,
            target_state=target_state.upper(),
            actor=request.user,
            reason=reason,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
        return redirect("archived_workspaces")

    messages.success(
        request,
        f"{updated.name} is now {updated.get_lifecycle_state_display().lower()}.",
    )
    return redirect("archived_workspaces")


@login_required
def companyinvitations_list(request, workspace_id=None):
    workspace = None
    if workspace_id is not None:
        workspace = get_object_or_404(Company, id=workspace_id)
    if workspace is None:
        workspace = _get_workspace_from_query(request)
    if workspace is None:
        workspace = resolve_request_workspace(request, include_public=False)

    if workspace is not None:
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_invite"},
            allow_platform_admin=True,
        )

    seat_capacity = None
    if isinstance(workspace, Company):
        seat_capacity = get_workspace_seat_capacity_snapshot(workspace=workspace)

    invitations = CompanyInvitation.objects.select_related(
        "company", "role", "inviter"
    ).order_by("-created")

    if workspace is not None:
        invitations = invitations.filter(company=workspace)
    else:
        invitations = invitations.filter(inviter=request.user)

    invitations_with_state = []
    for invitation in invitations:
        invitations_with_state.append(
            {
                "invitation": invitation,
                "state": invitation.lifecycle_state(),
            }
        )

    return render(
        request,
        "company/company_invitations_list.html",
        {
            "invitations": invitations_with_state,
            "current_workspace": workspace,
            "workspace": workspace,
            "seat_capacity": seat_capacity,
        },
    )


@login_required
@permission_required("team_invite")
@audit_log("TEAM_INVITE", description="Send team invitation")
def team_invite(request, workspace_id=None, company_id=None):
    """
    Send team invitation to new member.
    Requires team_invite permission (Owner/Admin).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_invite"},
        allow_platform_admin=True,
    )
    seat_capacity = get_workspace_seat_capacity_snapshot(workspace=company)

    if request.method == "POST":
        form = CompanyInvitationForm(
            request.POST, inviter=request.user, request=request, company=company
        )
        if form.is_valid():
            try:
                control_plane.send_team_invitation(
                    form=form,
                    actor=request.user,
                    company=company,
                    request=request,
                )
                messages.success(request, "Invitation sent successfully")
                return redirect(
                    "workspace_slug_settings_invitations",
                    workspace_slug=company.slug,
                )
            except (ValidationError, ValueError) as exc:
                form.add_error(None, str(exc))
                messages.error(request, "Unable to send invitation. Please review errors.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CompanyInvitationForm(inviter=request.user, company=company)
    return render(
        request,
        "company/invitation_form.html",
        {
            "form": form,
            "company": company,
            "workspace": company,
            "seat_capacity": seat_capacity,
            "url": reverse("team_invite", kwargs={"workspace_id": workspace_id}),
        },
    )


@login_required
def invite_success(request):
    workspace = None
    sent_invitations_url = reverse("team_invitations_list")
    workspace = _get_workspace_from_query(request)
    if workspace is not None:
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_invite"},
            allow_platform_admin=True,
        )
        sent_invitations_url = reverse(
            "workspace_slug_settings_invitations",
            kwargs={"workspace_slug": workspace.slug},
        )

    return render(
        request,
        "company/invite_success.html",
        {
            "workspace": workspace,
            "current_workspace": workspace,
            "sent_invitations_url": sent_invitations_url,
        },
    )


def team_accept_invitation(request, key):
    if not request.user.is_authenticated:
        accept_url = reverse("team_accept_invitation", kwargs={"key": key})
        return redirect(f"{reverse('account_login')}?next={accept_url}")

    invitation = (
        CompanyInvitation.objects.select_related("company", "role")
        .filter(key=key.lower())
        .first()
    )
    if invitation is None:
        messages.error(request, "Invitation not found.")
        return redirect("team_invitations")

    if invitation.email.casefold() != request.user.email.casefold():
        messages.error(request, "This invitation was sent to a different email address.")
        return redirect("team_invitations")

    current_state = invitation.lifecycle_state()
    if current_state == "expired":
        messages.error(request, f"Invitation from {invitation.company.name} has expired.")
        return redirect("team_invitations")

    if current_state != CompanyInvitation.Status.PENDING:
        messages.info(request, f"Invitation is already {current_state}.")
        return redirect("team_invitations")

    if request.method != "POST":
        return render(
            request,
            "company/invitation_accept_confirm.html",
            {"invitation": invitation},
        )

    try:
        control_plane.accept_invitation(
            invitation=invitation,
            user=request.user,
            request=request,
        )
    except ValidationError as exc:
        messages.error(request, str(exc))
        return redirect("team_invitations")

    if hasattr(request.user, "profile"):
        request.user.profile.workspace = invitation.company
        request.user.profile.save()

    messages.success(
        request,
        f"Added to {invitation.company.name} as {invitation.role.name}",
    )
    return redirect(
        "workspace_slug_dashboard",
        workspace_slug=invitation.company.slug,
    )


@method_decorator(login_required, name="dispatch")
@method_decorator(permission_required("workspace_settings"), name="dispatch")
class CompanyPreferenceBuilder(PreferenceFormView):
    template_name = "company/company_preferences.html"
    title = "Company Preferences"

    def dispatch(self, request, *args, **kwargs):
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            raise Http404("Workspace ID is required")

        workspace = get_object_or_404(Company, id=workspace_id)
        _assert_workspace_access(
            request,
            workspace,
            required_permissions={"workspace_settings"},
            allow_platform_admin=True,
        )
        return super().dispatch(request, *args, **kwargs)

    def get_section(self):
        """Get section from URL parameter, default to showing all"""
        return self.request.GET.get("section", None)

    def get_success_url(self):
        section = self.get_section()
        workspace_id = self.kwargs.get("workspace_id")

        if workspace_id:
            base_url = reverse_lazy(
                "workspace_preferences", kwargs={"workspace_id": workspace_id}
            )
        else:
            base_url = reverse_lazy("company-preferences")

        if section:
            return f"{base_url}?section={section}"
        return base_url

    def get_form_class(self):
        section = self.get_section()
        preferences = []

        if section:
            # Filter preferences by section
            registry = company_preference_registry
            if section in registry:
                preferences = list(registry[section].values())

        return company_preference_form_builder(
            instance=resolve_request_workspace(self.request), Preferences=preferences
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get all available sections
        registry = company_preference_registry
        context["sections"] = [
            {"name": section, "obj": registry.section_objects.get(section)}
            for section in registry.sections()
        ]
        context["current_section"] = self.get_section()
        context["workspace_id"] = self.kwargs.get("workspace_id")
        return context

    def render_to_response(self, context, **response_kwargs):
        # Check if the request is made via HTMX
        if self.request.headers.get("HX-Request", False):
            # Render only the specific block content for HTMX requests
            content = render_block_to_string(
                "company/company_preferences.html", "content", context, self.request
            )
            return HttpResponse(content)
        else:
            # Proceed with the normal flow for non-HTMX requests
            return super().render_to_response(context, **response_kwargs)


@login_required
@permission_required("team_remove")
@require_POST
def team_remove_member(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Remove team member from workspace.
    Requires team_remove permission (Owner only).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_remove"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)

    is_self_leave = membership.user == request.user
    try:
        control_plane.remove_membership(
            membership=membership,
            actor=request.user,
            request=request,
        )
    except PermissionDenied as exc:
        messages.error(request, str(exc))
        return redirect("workspace_detail", workspace_id=workspace_id)

    # If removed member had this workspace selected, clear stale selection.
    if hasattr(membership.user, "profile") and membership.user.profile.workspace == company:
        membership.user.profile.workspace = None
        membership.user.profile.save(update_fields=["workspace"])

    if is_self_leave:
        messages.success(request, "You have left the workspace.")
        return redirect("workspace_selector")

    return redirect("workspace_list")  # Redirect to the list of workspaces


@login_required
@permission_required("team_change_role")
def team_change_role(request, workspace_id=None, membership_id=None, company_id=None):
    """
    Change team member's role.
    Requires team_change_role permission (Owner only).
    """
    workspace_id = workspace_id or company_id
    if workspace_id is None:
        raise Http404("Workspace ID is required")

    company = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(
        request,
        company,
        required_permissions={"team_change_role"},
        allow_platform_admin=True,
    )

    membership = get_object_or_404(Membership, id=membership_id, company=company)
    roles = role_policy.allowed_invitation_roles(actor=request.user, workspace=company)

    if request.method in ["POST", "PATCH"]:
        role_id = request.POST.get("role")
        role = get_object_or_404(Role, id=role_id)

        try:
            control_plane.change_membership_role(
                membership=membership,
                new_role=role,
                actor=request.user,
                request=request,
            )
        except ValidationError as exc:
            messages.error(request, str(exc))
            if request.htmx:
                return JsonResponse(
                    {"success": False, "error": str(exc)},
                    status=400,
                )
            return redirect("workspace_detail", workspace_id=workspace_id)
        except PermissionDenied as exc:
            messages.error(request, str(exc))
            if request.htmx:
                return JsonResponse(
                    {"success": False, "error": str(exc)},
                    status=400,
                )
            return redirect("workspace_detail", workspace_id=workspace_id)

        if request.htmx:
            return JsonResponse({"success": True, "role": role.name})
        return redirect("workspace_detail", workspace_id=workspace_id)
    else:
        form = MembershipForm(instance=membership)
    return render(
        request,
        "company/partials/role_form.html",
        {"form": form, "membership": membership, "company": company, "roles": roles},
    )


@login_required
def membership_list(request, workspace_id=None):
    if workspace_id is not None:
        workspace = get_object_or_404(Company, id=workspace_id)
    else:
        workspace = resolve_request_workspace(request, include_public=False)

    if not workspace:
        messages.info(request, "Select a workspace to view team members.")
        return redirect("workspace_selector")

    try:
        access = _assert_workspace_access(
            request,
            workspace,
            required_permissions={"team_list"},
            allow_platform_admin=True,
        )
    except PermissionDenied:
        messages.error(request, "You do not have permission to view team members.")
        return redirect("workspace_selector")

    memberships = (
        Membership.objects.select_related("user", "role", "company")
        .filter(company=workspace)
        .order_by("role__name", "user__username")
    )

    context = {
        "workspace": workspace,
        "memberships": memberships,
        "workspace_count": memberships.count(),
        "seat_capacity": get_workspace_seat_capacity_snapshot(workspace=workspace),
        "can_change_role": (workspace.owner_id == request.user.pk or access["access"].platform_override),
        "can_remove_member": (workspace.owner_id == request.user.pk or access["access"].platform_override),
    }
    return render(request, "company/membership_list.html", context)


@login_required
def my_memberships(request):
    return redirect("workspace_selector")


@login_required
def workspace_leave(request, workspace_id):
    """
    Allow any workspace member to leave a workspace themselves.
    Owners must transfer ownership before leaving.
    """
    company = get_object_or_404(Company, id=workspace_id)
    membership = get_object_or_404(Membership, user=request.user, company=company)

    if request.method == "GET":
        return render(request, "company/workspace_leave_confirm.html", {
            "company": company,
            "workspace": company,
            "membership": membership,
        })

    if request.method == "POST":
        if _is_owner_membership(membership):
            if _owner_membership_count(company) <= 1:
                messages.error(
                    request,
                    "You are the only owner. Transfer ownership to another member before leaving.",
                )
                return redirect("workspace_detail", workspace_id=workspace_id)
            messages.error(
                request,
                "Owner must transfer ownership before leaving the workspace.",
            )
            return redirect("workspace_detail", workspace_id=workspace_id)

        try:
            control_plane.remove_membership(
                membership=membership,
                actor=request.user,
                request=request,
            )
        except PermissionDenied as exc:
            messages.error(request, str(exc))
            return redirect("workspace_detail", workspace_id=workspace_id)

        if request.user.profile.workspace == company:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        messages.success(request, f"You have left {company.name}.")
        return redirect("workspace_selector")


@login_required
def profile(request):
    user = request.user
    workspace = resolve_preferred_workspace(request.user)

    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__lifecycle_state=Company.LifecycleState.ACTIVE)
        .order_by("company__name")
    )
    pending_invitations = CompanyInvitation.pending_queryset().filter(
        email=user.email
    ).count()

    context = {
        "workspace": workspace,
        "memberships": memberships,
        "workspace_count": memberships.count(),
        "pending_invitation_count": pending_invitations,
    }
    return render(request, "company/profile.html", context)


@login_required
def account_settings(request):
    return render(request, "company/account_settings.html")


@login_required
@require_POST
def invitation_delete(request, invitation_id):
    invitation = get_object_or_404(CompanyInvitation, id=invitation_id)

    # Inviter can always revoke. Workspace admins/owners can also revoke.
    can_revoke = request.user == invitation.inviter
    if not can_revoke:
        try:
            _assert_workspace_access(
                request,
                invitation.company,
                required_permissions={"team_invite"},
                allow_platform_admin=True,
            )
            can_revoke = True
        except PermissionDenied:
            can_revoke = False

    if not can_revoke:
        messages.error(request, "You do not have permission to revoke this invitation.")
        return redirect("workspace_selector")

    control_plane.revoke_invitation(
        invitation=invitation,
        actor=request.user,
        request=request,
    )

    messages.success(request, "Invitation revoked successfully")

    if request.headers.get("HX-Request"):
        return HttpResponse("Invitation revoked successfully")

    return redirect(
        reverse(
            "workspace_slug_settings_invitations",
            kwargs={"workspace_slug": invitation.company.slug},
        )
    )


from io import StringIO

from django.core.management import call_command
from django.views import View


class BackupSchemaView(View):
    def get(self, request, *args, **kwargs):
        schema_name = request.GET.get("schema_name")
        if not schema_name:
            return JsonResponse(
                {"status": "error", "message": "schema_name parameter is required"},
                status=400,
            )

        out = StringIO()
        try:
            call_command("backup", schema_name, stdout=out)
            response = {"status": "success", "message": out.getvalue()}
        except Exception as e:
            response = {"status": "error", "message": str(e)}
        return JsonResponse(response)


class BackupDatabaseView(View):
    def get(self, request, *args, **kwargs):
        out = StringIO()
        try:
            call_command("backup", stdout=out)
            response = {"status": "success", "message": out.getvalue()}
        except Exception as e:
            response = {"status": "error", "message": str(e)}
        return JsonResponse(response)


# ============================================================================
# WORKSPACE SELECTION & MANAGEMENT VIEWS
# ============================================================================


@login_required
def workspace_selector(request):
    """
    Workspace selection page - shows user's available workspaces.

    Displays:
    - User's available workspaces with membership info
    - Pending invitations
    - Quick actions (create workspace)

    Always displays the list, independently of the saved navigation preference.
    """
    user = request.user
    profile = user.profile

    # Get user's workspace memberships
    memberships = (
        user.memberships.select_related("company", "role")
        .filter(company__lifecycle_state=Company.LifecycleState.ACTIVE)
        .order_by("-company__updated_at")
    )

    selected_workspace = resolve_preferred_workspace(user)

    # Get pending invitations
    pending_invitations = (
        CompanyInvitation.pending_queryset().filter(
            email=user.email,
        )
        .select_related("company", "role")
        .order_by("-created")
    )

    # Filter out expired invitations
    valid_invitations = [inv for inv in pending_invitations if not inv.key_expired()]

    # Count outgoing pending invitations sent by this user
    sent_invitations_count = CompanyInvitation.objects.filter(
        inviter=user,
        status=CompanyInvitation.Status.PENDING,
    ).count()

    context = {
        "workspaces": memberships,
        "pending_invitations": valid_invitations,
        "current_workspace": selected_workspace,
        "workspace_count": memberships.count(),
        "invitation_count": len(valid_invitations),
        "has_workspaces": memberships.exists(),
        "sent_invitations_count": sent_invitations_count,
    }

    return render(request, "company/workspace_home.html", context)


@login_required
def team_invitations(request):
    """
    Manage pending invitations to workspaces.
    Allow user to accept or decline invitations.
    """
    user = request.user

    # Get pending invitations
    pending_invitations = CompanyInvitation.objects.filter(
        email=user.email,
        status=CompanyInvitation.Status.PENDING,
        accepted=False,
    ).select_related("company", "role")

    # Filter valid (not expired)
    invitations_data = []
    for inv in pending_invitations:
        if not inv.key_expired():
            invitations_data.append(
                {
                    "invitation": inv,
                    "is_expired": False,
                }
            )

    if request.method == "POST":
        action = request.POST.get("action")
        invitation_id = request.POST.get("invitation_id")

        try:
            invitation = CompanyInvitation.objects.get(
                id=invitation_id, email__iexact=user.email
            )

            current_state = invitation.lifecycle_state()
            if current_state == "expired":
                messages.error(
                    request,
                    f"Invitation from {invitation.company.name} has expired.",
                )
                return redirect("team_invitations")

            if current_state != CompanyInvitation.Status.PENDING:
                messages.info(
                    request,
                    f"Invitation is already {current_state}.",
                )
                return redirect("team_invitations")

            if action == "accept":
                try:
                    control_plane.accept_invitation(
                        invitation=invitation,
                        user=user,
                        request=request,
                    )
                except ValidationError as exc:
                    messages.error(request, str(exc))
                    return redirect("team_invitations")

                # Set as active workspace
                user.profile.workspace = invitation.company
                user.profile.save()

                messages.success(
                    request,
                    f"✅ Added to {invitation.company.name} as {invitation.role.name}",
                )

                return redirect(
                    "workspace_slug_dashboard",
                    workspace_slug=invitation.company.slug,
                )

            elif action == "decline":
                control_plane.decline_invitation(
                    invitation=invitation,
                    actor=user,
                    request=request,
                )

                messages.info(
                    request, f"Declined invitation from {invitation.company.name}"
                )

                return redirect("team_invitations")

        except CompanyInvitation.DoesNotExist:
            messages.error(request, "Invitation not found")
            return redirect("workspace_list")

    context = {
        "invitations": invitations_data,
        "invitation_count": len(invitations_data),
    }

    return render(request, "company/workspace_invitations.html", context)


@login_required
@require_POST
def workspace_select(request, workspace_id):
    """
    Select a workspace to work in.
    Sets the selected workspace in UserProfile and redirects to company dashboard.
    """
    user = request.user

    workspace = Company.objects.filter(id=workspace_id).first()
    if workspace is None:
        messages.error(request, "Workspace not found")
        return redirect("workspace_selector")

    try:
        _assert_workspace_access(request, workspace, allow_platform_admin=True)
    except PermissionDenied:
        messages.error(request, "Workspace not found or access denied")
        return redirect("workspace_selector")

    # Set as active workspace
    user.profile.set_workspace(workspace)

    AuditLog.log(
        "WORKSPACE_SWITCH",
        user=user,
        company=workspace,
        description=f"Switched to workspace: {workspace.name}",
        request=request,
        success=True,
    )

    messages.success(request, f"Switched to {workspace.name}")

    next_url = request.POST.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect(
        "workspace_slug_dashboard",
        workspace_slug=workspace.slug,
    )


def subscription_required(view_func):
    """
    Decorator to ensure workspace has active subscription.
    Redirects to subscription dashboard if subscription missing or expired.
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")

        workspace = resolve_request_workspace(request)
        if not workspace:
            return redirect("workspace_list")

        try:
            subscription = workspace.subscription
            decision = effective_billing_state(subscription)
        except Exception:
            subscription = None
            decision = None

        if decision is None or not decision.commercially_available:
            messages.warning(request, "Subscription access is unavailable.")
            return redirect(
                "workspace_subscriptions:dashboard",
                workspace_slug=workspace.slug,
            )

        if subscription and getattr(subscription, "end_date", None):
            days_left = (subscription.end_date - timezone.now()).days
            if 0 <= days_left <= 7:
                messages.warning(
                    request,
                    f"Subscription renews in {days_left} days",
                )

        return view_func(request, *args, **kwargs)

    return wrapper


# ============================================================================
# WORKSPACE DASHBOARD
# ============================================================================


@login_required
def workspace_dashboard(request, workspace_id):
    """
    Main workspace dashboard - shows key metrics and activity.

    Displays:
    - Loan statistics (unreleased, sunken, today's activity)
    - Customer statistics
    - Financial metrics
    - Team information

    Requires: User must be a member of the workspace (Owner/Admin/Member)

    """
    # Get workspace and validate access policy.
    workspace = get_object_or_404(Company, id=workspace_id)

    try:
        access_context = _assert_workspace_access(
            request,
            workspace,
            allow_platform_admin=True,
        )
    except PermissionDenied:
        messages.error(request, "Access denied to this workspace")
        return redirect("workspace_list")

    membership = access_context["membership"]
    role_name = access_context["role_name"]
    if membership is None:
        membership = SimpleNamespace(role=SimpleNamespace(name=role_name))

    # Set as active workspace if not already
    if request.user.profile.workspace != workspace:
        request.user.profile.workspace = workspace
        request.user.profile.save()

    # Redirect to public if somehow in public schema
    if workspace.slug == "public":
        return redirect("dashboard")

    context = {}
    context["workspace"] = workspace
    context["membership"] = membership
    context["role"] = role_name

    # Check if user can view detailed metrics (Owner/Admin)
    context["can_view"] = role_name in ["Owner", "Admin", "Superuser"]
    access = access_context["access"]
    context.update(get_workspace_dashboard_context(workspace=workspace, access=access))
    context["can_use_counter"] = access.can("data.view")
    context["can_create_loan"] = access.can("data.view") and access.can("data.create")
    if context["can_use_counter"]:
        from django.core.paginator import Paginator
        from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work

        work = get_workspace_counter_work(workspace=workspace)
        default_queue = next((key for key in ("overdue", "due", "approved", "draft", "review") if work["queues"][key]["count"]), "draft")
        selected = work["queues"].get(request.GET.get("queue"), work["queues"][default_queue])
        context["counter_work"] = work
        context["work_queues"] = work["queues"].values()
        context["selected_queue"] = selected
        context["work_page"] = Paginator(selected["rows"], 20).get_page(request.GET.get("page"))
    if context.get("setup_checklist") is not None:
        context["setup_state"] = build_workspace_setup_display_state(
            user=request.user,
            workspace=workspace,
            checklist=context["setup_checklist"],
        )

    return render(request, "company/workspace_dashboard.html", context)
