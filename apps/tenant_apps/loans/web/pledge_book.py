"""Read-only Form E review with selectable A4 layout, before book allocation."""
from django import forms
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries
from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report
from apps.tenant_apps.loans.documents.pledge_book import LAYOUT_CHOICES, render_pledge_book
from .statutory_notices import _private


class SeriesChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.license.license_number} / {obj.pawn_display_name}'


class PledgeBookFilter(forms.Form):
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none(), label='Licence')
    series = SeriesChoice(queryset=LoanSeries.objects.none(), required=False, empty_label='All series for this licence')
    start = forms.DateField(label='Loan dates from', widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(label='Loan dates to', widget=forms.DateInput(attrs={'type': 'date'}))
    cutoff = forms.DateField(label='Include activity through', widget=forms.DateInput(attrs={'type': 'date'}))
    layout = forms.ChoiceField(label='Print layout', choices=LAYOUT_CHOICES, required=False,
        initial='facing_a4', help_text='Same entries and evidence in either layout. Choose before opening the PDF.')

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['license'].queryset = LoanLicense.objects.filter(workspace=workspace)
        series = LoanSeries.objects.filter(workspace=workspace).select_related('license').prefetch_related('number_sequences')
        license_id = self.data.get('license') if self.is_bound else None
        if str(license_id).isdigit():
            series = series.filter(license_id=license_id)
        self.fields['series'].queryset = series
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field, (forms.ModelChoiceField, forms.ChoiceField)) else 'form-control'

    def clean_layout(self):
        # Existing bookmarked queries predate the layout selector.
        return self.cleaned_data['layout'] or 'facing_a4'

    def clean(self):
        values = super().clean()
        if all(values.get(k) for k in ('start', 'end', 'cutoff')) and not values['start'] <= values['end'] <= values['cutoff'] <= timezone.localdate():
            raise forms.ValidationError('Loan dates must end on or before the activity cutoff; future dates are unavailable.')
        if values.get('series') and values.get('license') and values['series'].license_id != values['license'].pk:
            self.add_error('series', 'Select a series belonging to this licence.')
        return values


@loans_workspace_required
@require_GET
def preview(request):
    today = timezone.localdate()
    form = PledgeBookFilter(request.GET or None, workspace=request.loans_workspace,
        initial={'start': today.replace(day=1), 'end': today, 'cutoff': today})
    report = None
    if form.is_bound and form.is_valid():
        values = form.cleaned_data
        try:
            report = pledge_book_report(workspace=request.loans_workspace, actor=request.user,
                license_id=values['license'].pk, series_id=values['series'].pk if values['series'] else None,
                start=values['start'], end=values['end'], cutoff=values['cutoff'], exporting=request.GET.get('format') == 'pdf')
            if request.GET.get('format') == 'pdf':
                response = HttpResponse(render_pledge_book(report, layout=values['layout']), content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="form-e-{values["layout"]}-working-preview.pdf"'
                return _private(response)
        except (ValueError, LoanLicense.DoesNotExist, LoanSeries.DoesNotExist) as exc:
            form.add_error(None, str(exc) if isinstance(exc, ValueError) else 'Selected licence or series is unavailable.')
    return _private(render(request, 'loans/statutory/pledge_book.html', {
        'form': form, 'report': report,
        'can_export': request.loans_workspace_access.can('data.export'),
    }))
