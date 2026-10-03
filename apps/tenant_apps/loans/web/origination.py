from decimal import Decimal, InvalidOperation
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.http import Http404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods
from django.utils import timezone
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance, _optional_policy_snapshot
from apps.tenant_apps.loans.selectors.khata_summary import portfolio_summary
from apps.tenant_apps.loans.services.origination_settings import collateral_photos_required, set_collateral_photo_requirement


class PhotoPolicyForm(forms.Form):
    require_collateral_photos = forms.BooleanField(required=False,
        label="Require a photograph for every collateral item before approval",
        help_text="Drafts can always be saved without photos. Existing approvals and issued tickets are unchanged.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))


@loans_setup_required
@never_cache
@require_http_methods(["GET", "POST"])
def origination_settings(request):
    workspace = request.loans_workspace
    form = PhotoPolicyForm(request.POST if request.method == "POST" else None,
        initial={"require_collateral_photos": collateral_photos_required(workspace.pk)})
    if request.method == "POST" and form.is_valid():
        set_collateral_photo_requirement(workspace=workspace, actor=request.user,
            required=form.cleaned_data["require_collateral_photos"])
        messages.success(request, "Collateral photo rule saved.")
        return redirect("workspace_loans:origination_settings", workspace_slug=workspace.slug)
    return render(request, "loans/setup/origination.html", {"form": form})


@loans_workspace_required
@never_cache
@require_GET
def borrower_outstanding(request):
    if not request.loans_workspace_access.can("data.edit"):
        request.loans_workspace_access.require("data.create")
    try:
        borrower_id = int(request.GET.get("borrower", ""))
        if borrower_id < 1:
            raise ValueError
    except (ValueError, TypeError):
        raise Http404("Choose a borrower.")
    party = get_object_or_404(Party, workspace=request.loans_workspace, pk=borrower_id)
    totals = {"principal": Decimal(0), "interest": Decimal(0), "fees": Decimal(0), "total": Decimal(0)}
    unavailable = count = 0
    today = timezone.localdate()
    loans = PawnLoan.objects.filter(workspace=request.loans_workspace, borrower=party, state="ACTIVE").select_related("policy_snapshot").prefetch_related("loan_events", "collateral_items")
    for loan in loans:
        count += 1
        try:
            balance = calculate_pawn_loan_balance(loan, events=tuple(loan.loan_events.all()),
                collateral_items=tuple(loan.collateral_items.all()), policy_snapshot=_optional_policy_snapshot(loan),
                as_of_date=today, pending_delivery_blocks=False)
            values = dict(principal=balance.principal_outstanding, interest=balance.interest_outstanding,
                          fees=balance.fees_outstanding, total=balance.total_due)
            if not all(value.is_finite() for value in values.values()):
                raise ValueError("Invalid balance")
            for key, value in values.items(): totals[key] += value
        except (ValueError, InvalidOperation):
            unavailable += 1
    khata = portfolio_summary(workspace=request.loans_workspace, borrower=party, include_rows=False)
    count += khata["active_count"]
    unavailable += khata["unavailable"]
    if not unavailable:
        totals["principal"] += khata["principal"]
        totals["total"] += khata["principal"] + khata["interest"]
    return render(request, "loans/pawn/_borrower_outstanding.html",
        {"party": party, "totals": totals, "count": count, "khata": khata, "unavailable": unavailable, "as_of": today})
