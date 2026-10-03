"""Explicit forms for manual statutory notice handling, separate from Notify."""
from django import forms


class DateInput(forms.DateInput):
    input_type = 'date'


class CatalogueForm(forms.Form):
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)
    business_name = forms.CharField(max_length=255, label='Licensed pawnbroker / business name')
    business_address = forms.CharField(max_length=1500, widget=forms.Textarea(attrs={'rows': 3}))
    borrower_address = forms.CharField(max_length=1500, label='Pawner’s last-known postal address', widget=forms.Textarea(attrs={'rows': 3}))
    auctioneer_name = forms.CharField(max_length=255, label='Responsible approved auctioneer')
    auctioneer_reference = forms.CharField(max_length=255, label='Auctioneer approval reference')
    sale_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Auction time (local time)')
    sale_place = forms.CharField(max_length=1500, widget=forms.Textarea(attrs={'rows': 3}))
    reviewed = forms.BooleanField(label='I have checked the particulars and the applicable notice requirements with the responsible auctioneer.')


class HandlingForm(forms.Form):
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)
    occurred_on = forms.DateField(widget=DateInput, label='Actual event date')
    notes = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={'rows': 3}))
    attachment = forms.FileField(required=False, help_text='PDF, JPEG or PNG; maximum 10 MB. Upload only the relevant evidence.')


class PrintedForm(HandlingForm):
    notes = forms.CharField(max_length=2000, label='Printed/signed by and handling note')


class PostedForm(HandlingForm):
    article_number = forms.CharField(max_length=100, label='Postal article / consignment number')
    postal_service = forms.ChoiceField(choices=[('SPEED_REGISTERED_POD', 'Speed Post with Registration and acknowledgement / POD'), ('RPAD', 'Registered Post acknowledgement due')])
    posted_by = forms.CharField(max_length=255, label='Auctioneer / person who actually posted it')
    attachment = forms.FileField(label='Postal booking receipt')


class AcknowledgedForm(HandlingForm):
    delivered_on = forms.DateField(widget=DateInput, label='Delivery date shown on acknowledgement / POD')
    attachment = forms.FileField(label='Acknowledgement / POD')


class ReturnedForm(HandlingForm):
    attachment = forms.FileField(label='Returned cover and postal endorsement')


class ReferredForm(HandlingForm):
    officer = forms.CharField(max_length=255, label='Village Administrative Officer / Village Officer and jurisdiction')
    reference = forms.CharField(max_length=255, label='Requisition reference')
    attachment = forms.FileField(label='Requisition, two catalogue copies and receipt evidence')


class OfficerReceiptForm(HandlingForm):
    attachment = forms.FileField(label='Evidence of the officer receiving the requisition')


class CertifiedForm(HandlingForm):
    affixed_on = forms.DateField(widget=DateInput, label='Official affixture and proclamation date')
    certified_on = forms.DateField(widget=DateInput, label='Certificate issue date')
    attachment = forms.FileField(label='Official affixture and proclamation certificate')


class ReviewForm(HandlingForm):
    authority_reference = forms.CharField(max_length=255, label='Auction permission and applicable schedule / deviation authority')
    permission_expires_on = forms.DateField(widget=DateInput, label='Last permitted auction date')
    first_publication_on = forms.DateField(widget=DateInput, label='First newspaper publication date')
    second_publication_on = forms.DateField(widget=DateInput, label='Second publication date (same approved newspaper)')
    police_sent_on = forms.DateField(widget=DateInput, label='Catalogue copies sent to the relevant police stations')
    legal_review_reference = forms.CharField(max_length=500, label='Current-rule / local-authority review reference')
    permission_checked = forms.BooleanField(label='Permission, approved auctioneer, permitted schedule and any deviation authority checked.')
    publication_checked = forms.BooleanField(label='Approved newspaper publications, required display and catalogue distribution checked.')
    authority_checked = forms.BooleanField(label='Tahsildar notification, Revenue officer attendance arrangements and pending objections checked.')
    valuation_checked = forms.BooleanField(label='Applicable approved appraisal and upset-price requirements checked.')
    service_checked = forms.BooleanField(label='Recipient, complete catalogue, registration and acknowledgement / official service evidence checked; a digital reminder is not service proof.')
    attachment = forms.FileField(label='Supporting permission, publication and readiness dossier (PDF or image)')


FORMS = {
    'PRINTED': PrintedForm, 'POSTED': PostedForm, 'ACKNOWLEDGED': AcknowledgedForm,
    'RETURNED': ReturnedForm, 'REFERRED': ReferredForm, 'CERTIFIED': CertifiedForm,
    'OFFICER_RECEIVED': OfficerReceiptForm,
    'REVIEWED': ReviewForm, 'WITHDRAWN': HandlingForm,
}
