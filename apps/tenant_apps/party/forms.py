from django import forms
from django.core.validators import URLValidator, validate_email
from phonenumber_field.formfields import PhoneNumberField

from .widgets import PrivateFileInput
from .models import (
    Party,
    PartyAddress,
    PartyContactMethod,
    PartyDocument,
    PartyIdentifier,
    PartyRelationship,
    PartyRole,
    PartyRoleType,
)
from apps.tenancy.context import current_workspace_id


CONTROL_CLASS = "form-control"
SELECT_CLASS = "form-select"
PHONE_CONTACT_TYPES = {
    PartyContactMethod.ContactType.PHONE,
    PartyContactMethod.ContactType.MOBILE,
    PartyContactMethod.ContactType.WHATSAPP,
}


def normalize_phone_number(value):
    phone = PhoneNumberField(region="IN").clean(value)
    if not phone:
        return ""
    return phone.as_e164


class PartyForm(forms.ModelForm):
    party_code = forms.CharField(
        required=False,
        help_text="Leave blank to auto-generate.",
        widget=forms.TextInput(attrs={"class": CONTROL_CLASS}),
    )

    class Meta:
        model = Party
        fields = [
            "party_code",
            "party_type",
            "display_name",
            "legal_name",
            "relation_label",
            "relation_name",
            "primary_phone",
            "primary_email",
            "profile_photo",
            "tax_pan",
            "gstin",
            "risk_level",
            "credit_hold",
            "status",
        ]
        widgets = {
            "party_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "display_name": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "legal_name": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "relation_label": forms.Select(attrs={"class": SELECT_CLASS}),
            "relation_name": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "primary_phone": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "primary_email": forms.EmailInput(attrs={"class": CONTROL_CLASS}),
            "profile_photo": PrivateFileInput(attrs={"class": CONTROL_CLASS}),
            "tax_pan": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "gstin": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "risk_level": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "credit_hold": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def clean_party_code(self):
        return (self.cleaned_data.get("party_code") or "").strip().upper()

    def clean_tax_pan(self):
        return (self.cleaned_data.get("tax_pan") or "").strip().upper()

    def clean_gstin(self):
        return (self.cleaned_data.get("gstin") or "").strip().upper()

    def clean_primary_phone(self):
        value = (self.cleaned_data.get("primary_phone") or "").strip()
        if not value:
            return ""
        return normalize_phone_number(value)

    def clean_relation_name(self):
        return (self.cleaned_data.get("relation_name") or "").strip()

    def clean(self):
        cleaned = super().clean()
        relation_label = cleaned.get("relation_label")
        relation_name = cleaned.get("relation_name")
        if bool(relation_label) != bool(relation_name):
            raise forms.ValidationError(
                "Relation label and related person name must be entered together."
            )
        return cleaned


class PartyRoleForm(forms.ModelForm):
    class Meta:
        model = PartyRole
        fields = [
            "role_type",
            "segment",
            "effective_from",
            "effective_to",
            "status",
        ]
        widgets = {
            "role_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "segment": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "effective_from": forms.DateInput(
                attrs={"class": CONTROL_CLASS, "type": "date"}
            ),
            "effective_to": forms.DateInput(
                attrs={"class": CONTROL_CLASS, "type": "date"}
            ),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace_id = current_workspace_id()
        queryset = PartyRoleType.objects.none()
        if workspace_id is not None:
            queryset = PartyRoleType.objects.filter(
                workspace_id=workspace_id,
                is_active=True,
            )
        self.fields["role_type"].queryset = queryset.order_by("sort_order", "label")


class PartyProfilePhotoForm(forms.ModelForm):
    class Meta:
        model = Party
        fields = ["profile_photo"]
        widgets = {
            "profile_photo": PrivateFileInput(attrs={"class": CONTROL_CLASS}),
        }


class PartyContactMethodForm(forms.ModelForm):
    class Meta:
        model = PartyContactMethod
        fields = ["contact_type", "label", "value", "is_primary"]
        widgets = {
            "contact_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "label": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "value": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean_value(self):
        value = (self.cleaned_data.get("value") or "").strip()
        contact_type = self.cleaned_data.get("contact_type")
        if not value:
            return ""
        if contact_type in PHONE_CONTACT_TYPES:
            return normalize_phone_number(value)
        if contact_type == PartyContactMethod.ContactType.EMAIL:
            validate_email(value)
            return value.lower()
        if contact_type == PartyContactMethod.ContactType.WEBSITE:
            URLValidator()(value)
            return value
        return value


class PartyAddressForm(forms.ModelForm):
    class Meta:
        model = PartyAddress
        fields = [
            "address_type",
            "line1",
            "line2",
            "area",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
        ]
        widgets = {
            "address_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "line1": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "line2": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "area": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "city": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "state": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "postal_code": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "country": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "is_default": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class PartyIdentifierForm(forms.ModelForm):
    class Meta:
        model = PartyIdentifier
        fields = ["identifier_type", "value", "masked_value", "expires_on"]
        widgets = {
            "identifier_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "value": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "masked_value": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "expires_on": forms.DateInput(
                attrs={"class": CONTROL_CLASS, "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        self.party = kwargs.pop("party", None)
        super().__init__(*args, **kwargs)

    def clean_value(self):
        return (self.cleaned_data.get("value") or "").strip().upper()

    def clean(self):
        cleaned = super().clean()
        party = self.party or getattr(self.instance, "party", None)
        identifier_type = cleaned.get("identifier_type")
        if party and identifier_type:
            exists = PartyIdentifier.objects.filter(
                party=party,
                identifier_type=identifier_type,
            )
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                self.add_error(
                    "identifier_type",
                    "This party already has an identifier of this type.",
                )
        return cleaned


class PartyDocumentForm(forms.ModelForm):
    class Meta:
        model = PartyDocument
        fields = ["document_type", "title", "identifier", "file", "expires_on"]
        widgets = {
            "document_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "title": forms.TextInput(attrs={"class": CONTROL_CLASS}),
            "identifier": forms.Select(attrs={"class": SELECT_CLASS}),
            "file": PrivateFileInput(attrs={"class": CONTROL_CLASS}),
            "expires_on": forms.DateInput(
                attrs={"class": CONTROL_CLASS, "type": "date"}
            ),
        }

    def __init__(self, *args, **kwargs):
        party = kwargs.pop("party", None)
        super().__init__(*args, **kwargs)
        if party is not None:
            self.fields["identifier"].queryset = party.identifiers.all()
        self.fields["identifier"].required = False


class PartyRelationshipForm(forms.ModelForm):
    class Meta:
        model = PartyRelationship
        fields = ["relationship_type", "to_party", "notes", "is_active"]
        widgets = {
            "relationship_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "to_party": forms.Select(attrs={"class": SELECT_CLASS}),
            "notes": forms.Textarea(attrs={"class": CONTROL_CLASS, "rows": 2}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        self.from_party = kwargs.pop("from_party", None)
        super().__init__(*args, **kwargs)
        queryset = Party.objects.order_by("display_name", "party_code")
        if self.from_party is not None:
            queryset = queryset.exclude(pk=self.from_party.pk)
        self.fields["to_party"].queryset = queryset

    def clean(self):
        cleaned = super().clean()
        from_party = self.from_party or getattr(self.instance, "from_party", None)
        to_party = cleaned.get("to_party")
        relationship_type = cleaned.get("relationship_type")
        if from_party and to_party and from_party.pk == to_party.pk:
            self.add_error("to_party", "A party cannot be related to itself.")
        if from_party and to_party and relationship_type:
            exists = PartyRelationship.objects.filter(
                from_party=from_party,
                to_party=to_party,
                relationship_type=relationship_type,
            )
            if self.instance.pk:
                exists = exists.exclude(pk=self.instance.pk)
            if exists.exists():
                self.add_error(
                    "relationship_type",
                    "This relationship already exists.",
                )
        return cleaned


class PartyMergeForm(forms.Form):
    source_party = forms.ModelChoiceField(
        queryset=None,
        label="Duplicate Party",
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    confirm = forms.BooleanField(
        label="I understand the duplicate party will be archived after merge.",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        self.target_party = kwargs.pop("target_party")
        super().__init__(*args, **kwargs)
        self.fields["source_party"].queryset = Party.objects.exclude(
            pk=self.target_party.pk
        ).exclude(status=Party.PartyStatus.ARCHIVED).order_by(
            "display_name",
            "party_code",
        )
