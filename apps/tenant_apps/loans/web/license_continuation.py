"""Explicit, evidence-backed continuation of an imported license."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.models import LoanLicense, LoanNumberSequence
from apps.tenant_apps.loans.services.license_continuation import numbering_review_digest, verify_legacy_license
from apps.tenant_apps.loans.services.license_series import LicenseSeriesError


class LegacyLicenseVerificationForm(forms.Form):
    issued_on = forms.DateField(label=_("Valid from"), widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    expires_on = forms.DateField(label=_("Valid until"), widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    issuing_authority = forms.CharField(label=_("Issuing authority"), max_length=255)
    supporting_document = forms.FileField(label=_("Supporting document"),
        help_text=_("PDF, PNG, or JPEG up to 10 MB. The document must match this license number."),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.png,.jpg,.jpeg"}))
    source_sha256 = forms.RegexField(label=_("Final source SHA-256"), regex=r"^[0-9a-f]{64}$", max_length=64)
    source_as_of = forms.DateField(label=_("Source review date"), widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    source_reference = forms.CharField(label=_("Source review reference"), max_length=255,
        help_text=_("Identify the final frozen dump and the reviewed numbering report."))
    confirmed_complete = forms.BooleanField(label=_("I confirm imports are complete, the old system has stopped issuing numbers, and this review includes closed, cancelled and excluded records."))
    expected_revision_id = forms.IntegerField(widget=forms.HiddenInput())
    expected_numbering_digest = forms.CharField(widget=forms.HiddenInput())

    def __init__(self, *args, license, sequences, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial.update(expected_revision_id=license.revisions.latest("revision_number").pk,
                            expected_numbering_digest=numbering_review_digest(sequences))
        self.counter_names = []
        for sequence in sequences:
            name = f"last_used_{sequence.pk}"
            self.counter_names.append((name, sequence.pk))
            self.fields[name] = forms.IntegerField(
                label=_("Last used counter: %(series)s / %(kind)s") % {"series": sequence.series.code, "kind": _(sequence.get_document_kind_display())},
                min_value=sequence.next_number - 1, max_value=sequence.maximum_number,
                help_text=_("Prefix %(prefix)s; width %(width)s; reserved through %(floor)s. Enter the reviewed numeric counter, including numbers absent from imported loans.") % {
                    "prefix": sequence.prefix or "(empty)", "width": sequence.width, "floor": sequence.next_number - 1})
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field, forms.BooleanField) else "form-control"

    @property
    def counter_fields(self):
        return [self[name] for name, _ in self.counter_names]

    def service_data(self):
        data = dict(self.cleaned_data)
        data["counters"] = {pk: data.pop(name) for name, pk in self.counter_names}
        return data


@loans_setup_required
@never_cache
def license_verify(request, pk):
    license = get_object_or_404(LoanLicense, pk=pk, workspace=request.loans_workspace)
    if not license.is_legacy_reference:
        return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=pk)
    sequences = list(LoanNumberSequence.objects.filter(workspace=request.loans_workspace, series__license=license).select_related("series").order_by("pk"))
    form = LegacyLicenseVerificationForm(request.POST if request.method == "POST" else None,
        request.FILES or None, license=license, sequences=sequences)
    if request.method == "POST" and form.is_valid():
        try:
            verify_legacy_license(workspace_id=request.loans_workspace.pk, license_id=pk,
                                  actor=request.user, request=request, **form.service_data())
        except (LicenseSeriesError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, _("License verified. Review the remaining setup checks before creating a loan."))
            return redirect("workspace_loans:license_detail", workspace_slug=request.loans_workspace.slug, pk=pk)
    return render(request, "loans/setup/license_verification.html", {"license": license, "form": form})
