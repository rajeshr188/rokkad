"""One review page and explicit POST for paired ticket activation."""

from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _, gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.documents import PrintProfileValidator
from apps.tenant_apps.loans.models import LoanDocumentLayoutRevision, LoanDocumentPrintProfileRevision, LoanSeries
from apps.tenant_apps.loans.services.ticket_template_activation import use_ticket_template


class ProfileChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return _("%(name)s — revision %(version)s (%(state)s)") % {
            "name": obj.profile.name, "version": obj.version, "state": obj.get_state_display()}


class TicketTemplateSelectionForm(forms.Form):
    profile = ProfileChoiceField(queryset=LoanDocumentPrintProfileRevision.objects.none(), label=gettext_lazy("Paper and copies"))
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none(), required=False,
        label=gettext_lazy("Use for"), empty_label=gettext_lazy("Workspace default"),
        help_text=gettext_lazy("Existing licence and series overrides remain in effect. Select a series to replace its own assignment."))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["profile"].queryset = LoanDocumentPrintProfileRevision.objects.filter(
            workspace=workspace, profile__document_type="loan_ticket", state__in=["DRAFT", "PUBLISHED"]
        ).select_related("profile").order_by("profile__name", "-version")
        self.fields["series"].queryset = LoanSeries.objects.filter(workspace=workspace).select_related("license").order_by("license__license_number", "code")
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select"


@loans_setup_required
@never_cache
@require_http_methods(["GET", "POST"])
def ticket_template_use(request, revision_pk):
    revision = get_object_or_404(LoanDocumentLayoutRevision.objects.select_related("layout"),
        pk=revision_pk, workspace=request.loans_workspace, layout__document_type="loan_ticket",
        state__in=["DRAFT", "PUBLISHED"], definition__schema_version__gte=3)
    form = TicketTemplateSelectionForm(
        request.POST if request.method == "POST" else request.GET or None, workspace=request.loans_workspace)
    profile_revision = profile = series = None
    if form.is_bound and form.is_valid():
        profile_revision = form.cleaned_data["profile"]
        series = form.cleaned_data["series"]
        try:
            profile = PrintProfileValidator.load(profile_revision.definition)
            if request.method == "POST":
                use_ticket_template(workspace=request.loans_workspace, revision=revision,
                    profile_revision=profile_revision, series=series, actor=request.user, request=request,
                    layout_hash=request.POST.get("layout_hash"), profile_hash=request.POST.get("profile_hash"))
                messages.success(request, _("Template and paper settings are now assigned together. Previously issued PDFs are unchanged."))
                return redirect("workspace_loans:document_layout_detail", workspace_slug=request.workspace.slug, revision_pk=revision.pk)
        except (ValueError, ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc) if not isinstance(exc, ObjectDoesNotExist) else _("The selection is no longer available. Review it again."))
    surfaces = {"ORIGINAL_FRONT": _("Original"), "DUPLICATE_FRONT": _("Duplicate"),
                "ORIGINAL_TERMS": _("Original reverse: terms"), "DUPLICATE_D3": _("Duplicate reverse: D3")}
    flip = {"LONG_EDGE": _("Flip on long edge"), "SHORT_EDGE": _("Flip on short edge"),
            "VERIFY_ON_PRINTER": _("Verify on the physical printer"), "NOT_APPLICABLE": ""}
    return render(request, "loans/setup/documents/use_template.html", {
        "revision": revision, "form": form, "profile_revision": profile_revision,
        "profile": profile, "series": series,
        "sheets": [[surfaces[surface] for surface in sheet] for sheet in profile.sheets] if profile else [],
        "flip_guidance": flip[profile.flip_edge_guidance] if profile else "",
    })
