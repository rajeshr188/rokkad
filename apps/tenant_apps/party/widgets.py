from django_select2 import forms as s2forms

from .selectors import active_parties


class PartyAutocompleteWidget(s2forms.ModelSelect2Widget):
    """Search active parties without rendering the full tenant party list."""

    search_fields = [
        "party_code__icontains",
        "display_name__icontains",
        "relation_name__icontains",
        "primary_phone__icontains",
        "primary_email__icontains",
    ]

    def get_queryset(self):
        return active_parties().order_by("display_name", "party_code")

    def label_from_instance(self, obj):
        parts = [obj.display_name]
        if obj.relation_display:
            parts.append(obj.relation_display)
        if obj.primary_phone:
            parts.append(obj.primary_phone)
        if obj.party_code:
            parts.append(obj.party_code)
        return " | ".join(parts)
