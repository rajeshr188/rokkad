from django.core import signing
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

    token_salt = "party.autocomplete.v1"
    token_max_age = 86400

    def render(self, *args, **kwargs):
        self.field_id = signing.dumps(self.get_url(), salt=self.token_salt)
        return super().render(*args, **kwargs)

    def set_to_cache(self):
        # The endpoint reconstructs this fixed widget under request Workspace/RLS.
        # Never serialize a queryset or model data into the token or cache.
        pass

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
