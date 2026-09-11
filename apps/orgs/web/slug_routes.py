"""Slug routes; existing routes and policy remain compatible."""

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.orgs.models import Company
from apps.orgs.web.workspace_settings import (
    workspace_detail,
    workspace_setup,
    workspace_setup_state,
    workspace_modules,
    workspace_security,
    workspace_update,
)
from apps.orgs.web.team_members import membership_list
from apps.orgs.web.invitations import companyinvitations_list, team_invite
from apps.orgs.web.workspace_lifecycle import workspace_delete
from apps.orgs.web.workspace_navigation import workspace_dashboard


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


# Preserve explicit retirement responses for old bookmarks.
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
