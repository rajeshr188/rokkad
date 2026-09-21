from django import forms

from apps.tenant_apps.party.models import Party, PartyRoleType
from apps.tenancy.context import current_workspace_id
from .mapping import TARGETS
from .contracts import PROFILE
from . import child_contracts

PROFILE_CHOICES = [(PROFILE, "Party master"), (child_contracts.CONTACT, "Contact methods"), (child_contracts.ADDRESS, "Addresses"), (child_contracts.IDENTIFIER, "Identifiers (no documents)"), (child_contracts.ROLE, "Party roles"), (child_contracts.RELATIONSHIP, "Party relationships")]


class UploadForm(forms.Form):
    profile = forms.ChoiceField(choices=PROFILE_CHOICES, initial=PROFILE, required=False)
    source_file = forms.FileField(label="CSV, XLSX or canonical JSONL")
    source_system = forms.CharField(max_length=120, help_text="CSV/XLSX: stable register/source name. JSONL: source Workspace UUID from the export filename.")


class BundleUploadForm(forms.Form):
    bundle_file = forms.FileField(label="Party ZIP bundle", widget=forms.ClearableFileInput(attrs={"accept": ".zip"}))


class MappingForm(forms.Form):
    default_kind = forms.ChoiceField(choices=Party.PartyType.choices, initial="INDIVIDUAL")
    default_status = forms.ChoiceField(choices=Party.PartyStatus.choices, initial="ACTIVE")
    default_credit_hold = forms.ChoiceField(choices=[("false", "No"), ("true", "Yes")], initial="false")
    trim = forms.BooleanField(required=False, initial=True, label="Trim surrounding whitespace in mapped Party values")
    uppercase = forms.BooleanField(required=False, initial=True, label="Uppercase mapped type, status, relation and tax codes")

    def __init__(self, *args, headers, profile=PROFILE, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers = headers
        self.profile = profile
        targets = TARGETS
        if profile != PROFILE:
            for key in ("default_kind", "default_status", "default_credit_hold"):
                del self.fields[key]
            targets = set(child_contracts.fields(profile)) | set(child_contracts.parent_fields(profile)) | {"source.external_id", "source_recorded_at", "source_is_verified"}
            self.fields["source_is_verified"] = forms.ChoiceField(choices=[("false", "No source verification claim"), ("true", "Source claims verified (provenance only)")], initial="false")
            self.fields["primary_default"] = forms.ChoiceField(choices=[("false", "No"), ("true", "Yes")], initial="false", label="Default primary contact / default address flag")
        if profile == child_contracts.IDENTIFIER:
            targets.add("source_verified_at")
            del self.fields["primary_default"]
        if profile in {child_contracts.ROLE, child_contracts.RELATIONSHIP}:
            targets.discard("source_is_verified")
            del self.fields["source_is_verified"]
            del self.fields["primary_default"]
        for index, header in enumerate(headers):
            self.fields[f"column_{index}"] = forms.ChoiceField(label=header, required=False,
                choices=[("", "Do not import")] + [(name, name.replace("_", " ")) for name in sorted(targets)])

    def mapping(self):
        columns = {header: self.cleaned_data[f"column_{i}"] for i, header in enumerate(self.headers)
                   if self.cleaned_data[f"column_{i}"]}
        rules = []
        for field in columns.values():
            if field in {"source.external_id", "role_type_key", *child_contracts.relationship_contracts.REFERENCES}:
                continue
            if self.cleaned_data["trim"]:
                rules.append({"field": field, "rule": "trim", "version": 1})
            if self.cleaned_data["uppercase"] and field in {"kind", "status", "relation_kind", "tax_pan", "gstin", "contact_type", "address_type", "country", "identifier_type", "relationship_type"}:
                rules.append({"field": field, "rule": "upper", "version": 1})
            if field in {"credit_hold", "is_primary", "is_default", "source_is_verified", "is_active"}:
                rules.append({"field": field, "rule": "boolean", "version": 1})
        if self.profile in {child_contracts.ROLE, child_contracts.RELATIONSHIP}:
            return {"columns": columns, "defaults": {}, "normalization": rules}
        if self.profile == child_contracts.IDENTIFIER:
            return {"columns": columns, "defaults": {"source_is_verified": self.cleaned_data["source_is_verified"] == "true"}, "normalization": rules}
        if self.profile != PROFILE:
            return {"columns": columns, "defaults": {"source_is_verified": self.cleaned_data["source_is_verified"] == "true",
                ("is_primary" if self.profile == child_contracts.CONTACT else "is_default"): self.cleaned_data["primary_default"] == "true"}, "normalization": rules}
        return {"columns": columns, "defaults": {"kind": self.cleaned_data["default_kind"],
            "status": self.cleaned_data["default_status"], "credit_hold": self.cleaned_data["default_credit_hold"] == "true"},
            "normalization": rules}


class RoleTypeMappingForm(forms.Form):
    def __init__(self, *args, source_keys, **kwargs):
        super().__init__(*args, **kwargs)
        self.source_keys = sorted(set(source_keys))
        choices = [(obj.key, obj.key + " ? " + obj.label) for obj in PartyRoleType.objects.filter(workspace_id=current_workspace_id(), is_active=True)]
        for index, key in enumerate(self.source_keys):
            self.fields[f"role_type_{index}"] = forms.ChoiceField(label=f"Source role {key}", choices=[("", "Choose destination role type"), *choices])

    def role_map(self):
        return {key: self.cleaned_data[f"role_type_{index}"] for index, key in enumerate(self.source_keys)}
