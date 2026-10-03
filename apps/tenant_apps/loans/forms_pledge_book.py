from django import forms
from django.utils import timezone

from apps.tenant_apps.loans.documents.pledge_book import LAYOUT_CHOICES
from apps.tenant_apps.loans.models import LoanSeries

SUPPLEMENT_FIELDS = ('borrower', 'address', 'owner', 'tenure', 'descriptions', 'valuations', 'rates')


class SeriesChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.license.license_number} / {obj.pawn_display_name}'


class BookForm(forms.Form):
    series = SeriesChoice(queryset=LoanSeries.objects.none())
    title = forms.CharField(max_length=100, label='Physical book label')
    layout = forms.ChoiceField(choices=LAYOUT_CHOICES)
    starts_on = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}), label='Include pledges from')
    first_page = forms.IntegerField(min_value=1, max_value=999999, initial=1, label='First physical page number')
    opening_note = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}),
        label='Opening scope and earlier paper-book reference', help_text='Explain where earlier pledges are recorded. This date does not recreate or certify earlier books.')
    reviewed = forms.BooleanField(label='I checked the printed sample, handwriting space, scope and starting number. This book layout will be fixed.')

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['series'].queryset = LoanSeries.objects.filter(workspace=workspace).select_related('license').prefetch_related('number_sequences')

    def clean_starts_on(self):
        value = self.cleaned_data['starts_on']
        if value > timezone.localdate():
            raise forms.ValidationError('The opening date cannot be in the future.')
        return value


class EvidenceReviewForm(forms.Form):
    basis_sha256 = forms.CharField(max_length=64, widget=forms.HiddenInput)
    request_key = forms.CharField(max_length=64, widget=forms.HiddenInput)
    source_reference = forms.CharField(max_length=300, label='Original document / physical book reference')
    borrower = forms.CharField(required=False, max_length=300, label='Missing original pawner name')
    address = forms.CharField(required=False, max_length=1000, widget=forms.Textarea(attrs={'rows': 2}), label='Missing original pawner address')
    owner = forms.CharField(required=False, max_length=1000, label='Ownership declaration (same pawner, or other owner name/address)')
    tenure = forms.CharField(required=False, max_length=300, label='Missing original agreed redemption period')
    descriptions = forms.CharField(required=False, max_length=2000, widget=forms.Textarea(attrs={'rows': 2}), label='Supplement for missing article particulars (identify each item)')
    valuations = forms.CharField(required=False, max_length=1000, label='Supplement for missing original article values (identify each item)')
    rates = forms.CharField(required=False, max_length=1000, label='Supplement for missing original interest terms (identify each item)')
    notes = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}), label='Review result, unresolved gaps and follow-up')
    reviewed = forms.BooleanField(label='I reviewed the original evidence. Supplements describe original facts; unresolved gaps remain explicit and are not certified complete.')


class BatchForm(forms.Form):
    cutoff = forms.DateField(widget=forms.HiddenInput)
    mode = forms.ChoiceField(choices=[('full', 'Full pages only'), ('partial', 'Include last partial page')], widget=forms.HiddenInput)
    request_key = forms.CharField(max_length=64, widget=forms.HiddenInput)
    review_sha256 = forms.CharField(max_length=64, widget=forms.HiddenInput)
    reviewed = forms.BooleanField(label='I reviewed these entries, page numbers and evidence notes. Save this batch permanently for printing.')
