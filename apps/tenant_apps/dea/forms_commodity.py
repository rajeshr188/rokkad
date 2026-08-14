from django import forms

from .models import Commodity
from apps.tenant_apps.party.models import Party


class _CommodityBaseForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", "form-select")
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check-input")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class CommodityCreateForm(_CommodityBaseForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["is_active"].initial = True

    class Meta:
        model = Commodity
        fields = [
            "code",
            "name",
            "commodity_type",
            "default_uom",
            "is_active",
        ]

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()


class CommodityUpdateForm(_CommodityBaseForm):
    class Meta:
        model = Commodity
        fields = [
            "name",
            "commodity_type",
            "default_uom",
            "is_active",
        ]


class CommodityKarigarCustodyAccountForm(forms.Form):
    party = forms.ModelChoiceField(queryset=Party.objects.none())
    code = forms.CharField(max_length=64, required=False)
    name = forms.CharField(max_length=128, required=False)
    location_label = forms.CharField(max_length=128, required=False)

    def __init__(self, *args, commodity=None, **kwargs):
        self.commodity = commodity
        super().__init__(*args, **kwargs)
        self.fields["party"].queryset = Party.objects.exclude(
            status=Party.PartyStatus.ARCHIVED,
        ).order_by("display_name", "party_code")
        self.fields["party"].widget.attrs.setdefault("class", "form-select")
        self.fields["code"].widget.attrs.setdefault("class", "form-control")
        self.fields["name"].widget.attrs.setdefault("class", "form-control")
        self.fields["location_label"].widget.attrs.setdefault("class", "form-control")
        if commodity is not None:
            self.fields["location_label"].initial = f"{commodity.name} karigar custody"

    def clean_code(self):
        return (self.cleaned_data.get("code") or "").strip().upper()

    def clean_name(self):
        return (self.cleaned_data.get("name") or "").strip()

    def clean_location_label(self):
        return (self.cleaned_data.get("location_label") or "").strip()
