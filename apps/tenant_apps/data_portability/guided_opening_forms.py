from datetime import timedelta

from django import forms
from django.urls import reverse
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanLicenseRevision, LoanSeries
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from apps.tenant_apps.party.models import Party
from . import opening_register as register
from .models import SourceIdentity


class UploadRegisterForm(forms.Form):
    source_key = forms.RegexField(r'^[a-z0-9][a-z0-9-]{0,47}$', max_length=48, label='Source register key',
        help_text='For example old-ledger. Reuse this key for later batches from the same register, even when the filename changes.')
    file = forms.FileField(label='Existing loan register (.xlsx or .csv)',
        help_text='Use the template. Maximum 5 MiB, 20 loans and 200 collateral rows; one licence/series per batch.')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'


class RevisionField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.license_number} — revision {obj.revision_number} ({obj.kind})'


class SeriesField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.license.license_number} — {obj.pawn_display_name}'


class ReviewRegisterForm(forms.Form):
    revision_id = RevisionField(queryset=LoanLicenseRevision.objects.none(), label='Original licence revision',
        help_text='Select the source licence covering the original loan dates, or an explicitly configured legacy licence reference.')
    series_id = SeriesField(queryset=LoanSeries.objects.none(), label='Destination series',
        help_text='Original loan numbers are preserved. Overlaps with future numbering must be resolved in Loan setup first.')
    cutover = forms.DateField(label='Balances as at end of day', widget=forms.DateInput(attrs={'type': 'date'}),
        help_text='Use a completed date before today. Record every payment through this day in the source balance; service these loans in Rokkad from the next day.')
    grace_days = forms.IntegerField(min_value=0, max_value=30, label='Original operational grace days',
        help_text='Use the agreed source terms. This does not change the original maturity date.')
    reference = forms.CharField(max_length=180, label='Source / reconciliation reference',
        help_text='Identify the register and balance check, for example Ledger C, pages 20–25, checked 30/09/2026.')
    rule_confirmed = forms.BooleanField(label='I confirm these are bullet loans with unchanged principal, first-month interest paid upfront and the supported original-anniversary interest rule.',
        help_text='Interest is on original principal; later monthly charges are summed across items, then rounded once to whole rupees using half-even rounding. Partial principal repayments, instalments and other rules need assisted review.')

    def __init__(self, *args, workspace, batch, **kwargs):
        saved = batch.mapping
        initial = dict(saved.get('settings', {}))
        initial.setdefault('cutover', timezone.localdate() - timedelta(days=1))
        kwargs.setdefault('initial', initial)
        super().__init__(*args, **kwargs)
        self.closed_position = batch.document['profile'] == register.CLOSED_PROFILE
        if self.closed_position:
            del self.fields['revision_id'], self.fields['grace_days']
            self.fields['rule_confirmed'].label = 'I checked that every loan is closed with zero principal, interest and fees, and all collateral was returned to the borrower.'
            self.fields['rule_confirmed'].help_text = 'This source confirmation does not invent payments, physical handover events or unknown original terms.'
            self.fields['cutover'].help_text = 'Use a completed date before today at which these loans were already closed with all collateral returned.'
        else:
            self.fields['revision_id'].queryset = LoanLicenseRevision.objects.filter(workspace=workspace).order_by('license_number', '-revision_number')
        if batch.document['profile'] == register.CHECKPOINT_PROFILE:
            self.fields['rule_confirmed'].label = 'I checked the reduced-principal checkpoints and confirm simple full-month interest on each original anniversary, using period-start principal and per-item half-up rounding.'
            self.fields['rule_confirmed'].help_text = 'The sheet supplies the source rounding quantum and current-period bases, recognized/unpaid interest and advance. Future advance coverage must be explicitly zero for this template.'
        self.fields['series_id'].queryset = LoanSeries.objects.filter(workspace=workspace).select_related('license').prefetch_related('number_sequences').order_by('license_id', 'code')
        self.borrower_fields = []
        self.refs = list(register.borrowers(batch.document['rows']).items())
        sources = {s.external_id: s.identity.party for s in SourceIdentity.objects.filter(workspace=workspace,
            source_system=register.source_system(workspace.pk, batch.source_key),
            external_id__in=[ref for ref, _ in self.refs]).select_related('identity__party')}
        for index, (ref, values) in enumerate(self.refs):
            mode, party = f'mode_{index}', f'party_{index}'
            self.fields[mode] = forms.ChoiceField(label='Customer match', choices=[('', 'Choose an action'),
                ('EXISTING', 'Use an existing customer'), ('NEW', 'Create a new customer from this row')])
            query = Party.objects.filter(workspace=workspace).exclude(status='ARCHIVED') if self.closed_position else Party.objects.filter(workspace=workspace, status='ACTIVE')
            from .loan_restore_views import RestoreBorrowerWidget
            self.fields[party] = forms.ModelChoiceField(queryset=query,
                required=False, label='Find existing customer', widget=PartyAutocompleteWidget(
                    attrs={'data-width': '100%'},
                    data_url=reverse('workspace_party:party_autocomplete', kwargs={'workspace_slug': workspace.slug})))
            if self.closed_position:
                self.fields[party].widget = RestoreBorrowerWidget(data_url=reverse('workspace_portability:restore_borrowers', kwargs={'workspace_slug': workspace.slug}), attrs={'data-width': '100%'})
            bound = sources.get(ref)
            choice = saved.get('borrowers', {}).get(ref)
            if bound:
                self.initial.update({mode: 'EXISTING', party: bound.pk})
                self.fields[mode].choices = [('EXISTING', 'Previously matched customer')]
                self.fields[party].queryset = Party.objects.filter(workspace=workspace, pk=bound.pk)
            elif choice:
                self.initial[mode] = 'NEW' if choice == 'NEW' else 'EXISTING'
                if choice != 'NEW':
                    self.initial[party] = Party.objects.filter(workspace=workspace, party_code=choice).values_list('pk', flat=True).first()
            self.borrower_fields.append({'ref': ref, **values, 'bound': bound, 'mode': self[mode], 'party': self[party]})
        for name, field in self.fields.items():
            if not name.startswith('party_'):
                field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'

    def clean(self):
        data = super().clean()
        if data.get('cutover') and data['cutover'] >= timezone.localdate():
            self.add_error('cutover', 'Choose a completed day before today. Servicing begins the following day.')
        revision, series = data.get('revision_id'), data.get('series_id')
        if revision and series and series.license_id != revision.license_id:
            self.add_error('series_id', 'Choose a series belonging to the selected licence.')
        for index, _ in enumerate(self.refs):
            if data.get(f'mode_{index}') == 'EXISTING' and not data.get(f'party_{index}'):
                self.add_error(f'party_{index}', 'Select the customer who owns this source borrower reference.')
        return data

    def mapping(self):
        data = self.cleaned_data
        keys = ('series_id', 'cutover', 'reference', 'rule_confirmed') if self.closed_position else ('revision_id', 'series_id', 'cutover', 'grace_days', 'reference', 'rule_confirmed')
        return {'settings': {key: data[key].pk if key.endswith('_id') else data[key].isoformat() if key == 'cutover' else data[key]
            for key in keys},
            'borrowers': {ref: 'NEW' if data[f'mode_{index}'] == 'NEW' else data[f'party_{index}'].party_code
                         for index, (ref, _) in enumerate(self.refs)}}
