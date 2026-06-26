from django import forms

from .models import Commodity


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
