from django import forms
from django.db.models import Prefetch
from .models import Party, PartyAddress, PartyContactMethod
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
    active_only = True

    def build_attrs(self, base_attrs, extra_attrs=None):
        attrs = super().build_attrs(base_attrs, extra_attrs)
        # Select2 creates its cache token in build_attrs. Replace it afterwards
        # so the browser receives our stateless, Workspace-URL-bound token.
        self.field_id = signing.dumps(self.get_url(), salt=self.token_salt)
        attrs["data-field_id"] = self.field_id
        return attrs

    def set_to_cache(self):
        # The endpoint reconstructs this fixed widget under request Workspace/RLS.
        # Never serialize a queryset or model data into the token or cache.
        pass

    def get_queryset(self):
        parties = active_parties() if self.active_only else Party.objects.all()
        return parties.prefetch_related(
            Prefetch("addresses", queryset=PartyAddress.objects.filter(is_default=True).order_by("pk"), to_attr="search_default_addresses"),
            Prefetch("contact_methods", queryset=PartyContactMethod.objects.filter(is_primary=True,
                contact_type__in=["PHONE", "MOBILE", "WHATSAPP"]).order_by("pk"), to_attr="search_default_contacts"),
        ).order_by("display_name", "party_code")

    def label_from_instance(self, obj):
        parts = [obj.display_name]
        if obj.relation_display:
            parts.append(obj.relation_display)
        phone = obj.primary_phone
        if not phone:
            contacts = getattr(obj, "search_default_contacts", None)
            if contacts is None:
                contacts = list(obj.contact_methods.filter(is_primary=True,
                    contact_type__in=["PHONE", "MOBILE", "WHATSAPP"]).order_by("pk"))
            phone = contacts[0].value if contacts else ""
        if phone:
            parts.append(phone)
        addresses = getattr(obj, "search_default_addresses", None)
        if addresses is None:
            addresses = list(obj.addresses.filter(is_default=True).order_by("pk"))
        address = next((a for a in addresses if a.address_type == "HOME"), addresses[0] if addresses else None)
        if address:
            parts.append(str(address))
        if obj.party_code:
            parts.append(obj.party_code)
        return " | ".join(parts)


class PrivateFileInput(forms.ClearableFileInput):
    """Keep replacement/clear controls without publishing a storage URL."""

    template_name = "party/widgets/private_file_input.html"

    def is_initial(self, value):
        return bool(value and getattr(value, "name", None))
