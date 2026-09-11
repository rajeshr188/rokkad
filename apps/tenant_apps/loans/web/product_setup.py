"""Loan-product catalog setup views; product rules remain in services."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.forms import LoanProductVersionDraftForm
from apps.tenant_apps.loans.models import LoanProduct
from apps.tenant_apps.loans.services import (
    activate_product_version,
    create_product_version_draft,
    retire_product_version,
    seed_default_loan_products,
)


@loans_setup_required
def loan_product_list(request):
    products = LoanProduct.objects.filter(workspace=request.loans_workspace).prefetch_related("versions", "versions__pawn_loans").order_by("code")
    return render(request, "loans/setup/products/list.html", {"products": products})


@require_POST
@loans_setup_required
def loan_product_seed_defaults(request):
    try:
        versions = seed_default_loan_products(actor=request.user, request=request)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Default product catalog is ready with {len(versions)} version(s). Review and activate each approved draft.")
    return redirect('workspace_loans:loan_product_list', workspace_slug=request.workspace.slug)


@require_POST
@loans_setup_required
def loan_product_version_activate(request, version_pk):
    try:
        version = activate_product_version(version_pk, actor=request.user, request=request)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{version.product.name} v{version.version} is active for new loans.")
    return redirect('workspace_loans:loan_product_list', workspace_slug=request.workspace.slug)


@require_POST
@loans_setup_required
def loan_product_version_retire(request, version_pk):
    try:
        version = retire_product_version(version_pk, actor=request.user, request=request)
    except ValueError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"{version.product.name} v{version.version} is retired from new origination. Existing loans are unchanged.")
    return redirect('workspace_loans:loan_product_list', workspace_slug=request.workspace.slug)


@loans_setup_required
def loan_product_version_create(request, product_pk):
    product = get_object_or_404(LoanProduct, pk=product_pk, workspace=request.loans_workspace)
    active = product.versions.filter(status="ACTIVE").first()
    initial = {}
    if active:
        for name in LoanProductVersionDraftForm.Meta.fields:
            initial[name] = getattr(active, name)
    form = LoanProductVersionDraftForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            version = create_product_version_draft(
                product.pk, actor=request.user, request=request, **form.cleaned_data
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Created {product.name} v{version.version} as a draft. Review it before activation.")
            return redirect('workspace_loans:loan_product_list', workspace_slug=request.workspace.slug)
    return render(request, "loans/setup/products/version_form.html", {"form": form, "product": product, "active_version": active})
