"""Read-only opening illustration over KHATA-1, with no draft or financial writes."""
from copy import deepcopy

from django import forms
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.selectors.khata_workflow import opening_illustration
from .khata_forms import TermsForm
from .khata_views import _private


class IllustrationForm(forms.Form):
    agreed_limit = deepcopy(TermsForm.base_fields["agreed_limit"])
    monthly_rate = deepcopy(TermsForm.base_fields["monthly_rate"])
    frequency = deepcopy(TermsForm.base_fields["frequency"])
    clean_agreed_limit = TermsForm.clean_agreed_limit


@loans_workspace_required
@never_cache
@require_GET
def estimate(request):
    request.loans_workspace_access.require("data.create")
    form = IllustrationForm(request.GET)
    values = opening_illustration(**form.cleaned_data) if form.is_valid() else None
    return _private(render(request, "loans/khata/_opening_estimate.html", dict(opening_estimate=values), status=200 if values else 400))
