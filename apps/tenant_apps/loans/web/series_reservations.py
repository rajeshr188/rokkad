from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.models import LoanSeries, LoanNumberSequence
from apps.tenant_apps.loans.services.series_reservations import preview_register_reservation, confirm_register_reservation
from apps.tenant_apps.loans.services.license_series import LicenseSeriesError


class RegisterReservationForm(forms.Form):
    kind = forms.ChoiceField(label="Numbering to reserve")
    last_used = forms.IntegerField(min_value=0, label="Last number already used in this register",
        help_text="Enter the counter only: for AA05000 enter 5000. Include old loans still outside Rokkad.")
    reference = forms.CharField(max_length=255, label="Original register / book reference")
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False,
        label="I checked this register range. Its earlier numbers must remain available for recording the original loans.")

    def __init__(self, *args, sequences, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["kind"].choices = [(row.document_kind, row.get_document_kind_display()) for row in sequences]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field, forms.BooleanField) else "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


@loans_setup_required
@never_cache
def reserve_register(request, pk):
    series = get_object_or_404(LoanSeries.objects.select_related("license"), pk=pk, workspace=request.loans_workspace)
    sequences = list(LoanNumberSequence.objects.filter(series=series).order_by("document_kind"))
    form = RegisterReservationForm(request.POST if request.method == "POST" else None, sequences=sequences)
    review = None
    if request.method == "POST" and form.is_valid():
        values = {key: form.cleaned_data[key] for key in ("kind", "last_used", "reference")}
        try:
            if request.POST.get("action") == "confirm":
                changed = confirm_register_reservation(series.pk, actor=request.user, **values,
                    review_token=form.cleaned_data["review_token"], confirmed=form.cleaned_data["confirmed"])
                messages.success(request, "Existing register range reserved." if changed else "This register range is already reserved.")
                return redirect("workspace_loans:license_detail", workspace_slug=request.workspace.slug, pk=series.license_id)
            review, token = preview_register_reservation(series.pk, actor=request.user, **values)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except LicenseSeriesError as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/setup/register_reservation.html", dict(series=series, sequences=sequences, form=form, review=review))
